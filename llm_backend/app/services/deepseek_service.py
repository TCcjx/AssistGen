from typing import Awaitable, Callable, Dict, List, AsyncGenerator, Optional
from functools import lru_cache
from openai import AsyncOpenAI
from app.core.config import settings
import json
from app.core.logger import get_logger
from app.core.database import AsyncSessionLocal
from app.models.conversation import Conversation, DialogueType
from app.models.message import Message
from app.services.redis_semantic_cache import RedisSemanticCache
import time
import asyncio

logger = get_logger(service="deepseek")


@lru_cache(maxsize=256)
def _get_semantic_cache(user_id: Optional[int]) -> RedisSemanticCache:
    """按用户复用缓存对象，避免每个请求重复创建 Redis 客户端。

    后台清理任务由 RedisSemanticCache 按基础前缀共享，因此这里缓存实例不会
    导致每个用户堆积一个永久任务。
    """
    return RedisSemanticCache(prefix="deepseek", user_id=user_id)

class DeepseekService:
    def __init__(self, model: Optional[str] = None):
        logger.info("Initializing Deepseek Service")
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        # 明确传入的模型优先；未传入时使用配置中的问答模型。
        self.model = model or settings.DEEPSEEK_MODEL

    async def _stream_cached_response(self, response: str, delay: float = 0.05) -> AsyncGenerator[str, None]:
        """模拟流式返回缓存的响应"""
        # 每次返回4个字符
        chunks = [response[i:i + 4] for i in range(0, len(response), 4)]
        for chunk in chunks:
            await asyncio.sleep(delay)  # 50ms延迟
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    async def generate_stream(
        self, 
        messages: List[Dict],
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        on_complete: Optional[Callable[[int, int, List[Dict], str], Awaitable[None]]] = None
    ) -> AsyncGenerator[str, None]:
        """流式生成回复"""
        try:
            # 按用户复用缓存对象；键前缀隔离不同用户，清理任务按基础前缀共享。
            cache = _get_semantic_cache(user_id)
            
            start_time = time.time()
            
            # 检查缓存
            cached_response = await cache.lookup(messages)
            if cached_response:
                response_time = time.time() - start_time
                logger.info(f"Cache hit! Response time: {response_time:.4f} seconds")
                
                # 模拟流式返回，因为速率太快了
                async for chunk in self._stream_cached_response(cached_response):
                    yield chunk
                
                if on_complete and user_id is not None and conversation_id is not None:
                    await on_complete(user_id, conversation_id, messages, cached_response)
                return

            # 缓存未命中,调用API
            full_response: List[str] = []
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    # 使用 ensure_ascii=False 来保持中文字符
                    content = chunk.choices[0].delta.content
                    full_response.append(content)
                    yield f"data: {json.dumps(content, ensure_ascii=False)}\n\n"
            
            # 完整响应
            complete_response = "".join(full_response)
            
            # 更新缓存
            await cache.update(messages, complete_response)
            
            response_time = time.time() - start_time
            logger.info(f"Cache miss. Response time: {response_time:.4f} seconds")
            
            # 如果有回调，执行回调
            if on_complete and user_id is not None and conversation_id is not None:
                await on_complete(user_id, conversation_id, messages, complete_response)
                
        except Exception as e:
            logger.error(f"Error in generate_stream: {str(e)}", exc_info=True)
            error_msg = json.dumps(f"生成回复时出错: {str(e)}", ensure_ascii=False)
            yield f"data: {error_msg}\n\n"

    async def generate(self, messages: List[Dict]) -> str:
        """非流式生成回复"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Generation error: {str(e)}")
            raise 
