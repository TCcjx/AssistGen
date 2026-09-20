from typing import Dict, List, Optional
import redis
import hashlib
import numpy as np
import json
import time
import aiohttp
from app.core.config import settings
from app.core.logger import get_logger
import asyncio
from datetime import datetime

logger = get_logger(service="redis_cache")


_cleanup_tasks: Dict[str, asyncio.Task] = {}
_cleanup_lock = asyncio.Lock()

class RedisSemanticCache:
    """基于语义的 Redis 缓存实现"""
    
    def __init__(
        self,
        redis_url: str = None,
        model_name: str = None,
        score_threshold: float = None,
        prefix: str = "cache",
        user_id: Optional[int] = None,  # 添加用户ID
        max_cache_size: int = 1000,  # 每个用户最大缓存条数
        cleanup_interval: int = 3600  # 清理间隔(秒)
    ):
        self.redis = redis.from_url(redis_url or settings.REDIS_URL)
        self.model_name = model_name or settings.OLLAMA_EMBEDDING_MODEL
        self.score_threshold = score_threshold or settings.REDIS_CACHE_THRESHOLD
        self.base_prefix = prefix
        self.prefix = f"{prefix}:{user_id}" if user_id else prefix
        self.max_cache_size = max_cache_size
        self.cleanup_interval = cleanup_interval
        
        self._cleanup_started = False

    async def start_cleanup(self) -> None:
        """启动当前缓存前缀的共享清理任务。

        缓存实例会按用户创建，如果每个实例都在构造函数中启动后台任务，
        高频请求会不断堆积永久运行的协程。这里以 prefix 为键复用任务，
        并在实例第一次异步使用时惰性启动，兼容原有调用方式。
        """
        if self._cleanup_started:
            return
        async with _cleanup_lock:
            current = _cleanup_tasks.get(self.base_prefix)
            if current and not current.done():
                self._cleanup_started = True
                return
            task = asyncio.create_task(self._auto_cleanup(), name=f"cache-cleanup:{self.base_prefix}")
            _cleanup_tasks[self.base_prefix] = task
            self._cleanup_started = True

    async def close(self) -> None:
        """停止当前实例对应的共享清理任务。

        正常情况下由应用关闭时调用；若清理任务已经退出也会安全返回。
        """
        task = _cleanup_tasks.get(self.base_prefix)
        if task is None:
            return
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if _cleanup_tasks.get(self.base_prefix) is task:
            _cleanup_tasks.pop(self.base_prefix, None)
        
    async def _get_ollama_embedding(self, text: str) -> List[float]:
        """使用Ollama生成文本向量"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embed",
                    json={
                        "model": self.model_name,
                        "input": text  # 使用 input 而不是 prompt
                    }
                ) as response:
                    result = await response.json()
                    # Ollama embed API 返回格式为 {"embeddings": [[...], ...]}
                    return result["embeddings"][0]  # 返回第一个向量
        except Exception as e:
            logger.error(f"Error getting Ollama embedding: {str(e)}", exc_info=True)
            raise

    async def _get_embedding(self, text: str) -> List[float]:
        """获取文本向量"""
        try:
            # 直接使用 ollama 的 embedding 接口
            embedding = await self._get_ollama_embedding(text)
            if not embedding:
                raise ValueError("Failed to get embedding")
            return embedding
        except Exception as e:
            logger.error(f"Error in get_embedding: {str(e)}", exc_info=True)
            raise
        
    def _get_vector_key(self, message: str) -> str:
        """生成向量存储的键名"""
        message_hash = hashlib.md5(message.encode()).hexdigest()
        return f"{self.prefix}:vec:{message_hash}"
        
    def _get_response_key(self, message: str) -> str:
        """生成响应存储的键名"""
        message_hash = hashlib.md5(message.encode()).hexdigest()
        return f"{self.prefix}:resp:{message_hash}"
        
    def _get_metadata_key(self, message: str) -> str:
        """生成元数据存储的键名"""
        message_hash = hashlib.md5(message.encode()).hexdigest()
        return f"{self.prefix}:meta:{message_hash}"

    def _get_last_user_message(self, messages: List[Dict]) -> str:
        """获取最后一条用户消息"""
        for msg in reversed(messages):
            if msg["role"] == "user":
                return msg["content"]
        return ""

    async def _auto_cleanup(self):
        """自动清理过期和超量的缓存"""
        while True:
            try:
                # 共享任务覆盖该前缀下所有用户，按用户分别执行容量限制。
                pattern = f"{self.base_prefix}:*:meta:*"
                all_keys = [key.decode('utf-8') for key in self.redis.keys(pattern)]
                grouped: Dict[str, List[tuple[str, float]]] = {}
                for key in all_keys:
                    raw = self.redis.get(key.encode('utf-8'))
                    if not raw:
                        continue
                    try:
                        metadata = json.loads(raw.decode('utf-8'))
                    except (TypeError, ValueError, UnicodeDecodeError):
                        logger.warning(f"Skipping malformed cache metadata: {key}")
                        continue
                    item_prefix = key.rsplit(":meta:", 1)[0]
                    grouped.setdefault(item_prefix, []).append((key, metadata.get("last_access", 0)))

                for item_prefix, cache_items in grouped.items():
                    if len(cache_items) <= self.max_cache_size:
                        continue
                    cache_items.sort(key=lambda item: item[1])
                    items_to_remove = len(cache_items) - self.max_cache_size
                    for key, _ in cache_items[:items_to_remove]:
                        hash_id = key.rsplit(":", 1)[-1]
                        await self._remove_cache_item(hash_id, item_prefix)
                        
                logger.info(f"Cache cleanup completed for prefix {self.prefix}")
                
            except Exception as e:
                logger.error(f"Error in cache cleanup: {str(e)}", exc_info=True)
                
            await asyncio.sleep(self.cleanup_interval)

    async def _remove_cache_item(self, hash_id: str, prefix: Optional[str] = None):
        """删除一个缓存项的所有相关键"""
        try:
            target_prefix = prefix or self.prefix
            # 所有key都需要编码
            self.redis.delete(
                f"{target_prefix}:vec:{hash_id}".encode('utf-8'),
                f"{target_prefix}:resp:{hash_id}".encode('utf-8'),
                f"{target_prefix}:meta:{hash_id}".encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Error removing cache item: {str(e)}", exc_info=True)

    async def _update_metadata(self, message: str):
        """更新缓存项的元数据"""
        try:
            meta_key = self._get_metadata_key(message)
            # 从Redis读取的是bytes,需要解码
            current_meta = self.redis.get(meta_key)
            if current_meta:
                current_meta = json.loads(current_meta.decode('utf-8'))
            else:
                current_meta = {"access_count": 0}
                
            metadata = {
                "last_access": datetime.now().timestamp(),
                "access_count": current_meta["access_count"] + 1
            }
            self.redis.set(meta_key, json.dumps(metadata), ex=settings.REDIS_CACHE_EXPIRE)
        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}", exc_info=True)

    async def lookup(self, messages: List[Dict]) -> Optional[str]:
        """查找缓存的响应"""
        try:
            await self.start_cleanup()
            user_message = self._get_last_user_message(messages)
            if not user_message:
                return None

            current_vector = await self._get_embedding(user_message)
            
            # 获取当前用户的所有缓存向量
            pattern = f"{self.prefix}:vec:*"
            all_vectors = [key.decode('utf-8') for key in self.redis.keys(pattern)]  # 解码key
            max_similarity = 0
            most_similar_key = None
            
            for vec_key in all_vectors:
                cached_vector = json.loads(self.redis.get(vec_key.encode('utf-8')).decode('utf-8'))  # 编码key再获取
                similarity = np.dot(current_vector, cached_vector) / (
                    np.linalg.norm(current_vector) * np.linalg.norm(cached_vector)
                )
                
                if similarity > max_similarity:
                    max_similarity = similarity
                    most_similar_key = vec_key
            
            if max_similarity >= self.score_threshold and most_similar_key:
                hash_id = most_similar_key.split(":")[-1]
                resp_key = f"{self.prefix}:resp:{hash_id}"
                cached_response = self.redis.get(resp_key.encode('utf-8'))  # 编码key
                
                if cached_response:
                    # 更新访问元数据
                    await self._update_metadata(user_message)
                    logger.info(f"Cache hit with similarity: {max_similarity:.4f}")
                    return cached_response.decode('utf-8')
                    
            return None
            
        except Exception as e:
            logger.error(f"Error in lookup: {str(e)}", exc_info=True)
            return None

    async def update(self, messages: List[Dict], response: str, expire: int = None):
        """更新缓存"""
        try:
            await self.start_cleanup()
            user_message = self._get_last_user_message(messages)
            if not user_message:
                return

            vector = await self._get_embedding(user_message)
            
            vec_key = self._get_vector_key(user_message)
            resp_key = self._get_response_key(user_message)
            meta_key = self._get_metadata_key(user_message)
            
            expire = expire or settings.REDIS_CACHE_EXPIRE
            
            # 存储向量、响应和元数据 - 确保存储为字符串
            self.redis.set(vec_key, json.dumps(vector), ex=expire)
            # response 必须是纯文本；SSE 层负责 JSON 编码，避免缓存命中时
            # 返回带双引号的字符串，导致前端显示成 "回答内容"。
            self.redis.set(resp_key, response.encode('utf-8'), ex=expire)
            
            metadata = {
                "created_at": datetime.now().timestamp(),
                "last_access": datetime.now().timestamp(),
                "access_count": 1
            }
            self.redis.set(meta_key, json.dumps(metadata), ex=expire)
            
            logger.info(f"Cache updated for message: {user_message[:50]}...")
            
        except Exception as e:
            logger.error(f"Error in update: {str(e)}", exc_info=True) 


async def shutdown_all_cache_cleanup() -> None:
    """取消所有共享缓存清理任务，供 FastAPI 关闭钩子调用。"""
    tasks = list(_cleanup_tasks.values())
    _cleanup_tasks.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
