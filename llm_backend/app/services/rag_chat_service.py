"""基于本地向量知识库的问答服务（RAG）

职责划分：本服务只负责「检索 + 拼装提示词」，真正的流式生成复用
LLMFactory 产出的对话服务，这样 /chat-rag 与 /api/chat 的 SSE 输出格式、
缓存策略、落库回调都能保持一致。
"""
from typing import AsyncGenerator, Callable, Dict, List, Optional
import asyncio
import json

from app.core.logger import get_logger
from app.prompts.rag_prompts import RAG_SYSTEM_PROMPT, format_rag_context
from app.services.embedding_service import EmbeddingService
from app.services.llm_factory import LLMFactory

logger = get_logger(service="rag_chat")

# EmbeddingService 持有 SentenceTransformer 模型，加载成本高，进程内复用一个实例
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """获取进程内共享的 EmbeddingService 实例"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


class RAGChatService:
    """本地知识库问答服务"""

    def __init__(self, top_k: int = 3):
        logger.info("Initializing RAGChatService...")
        self.top_k = top_k
        self.embedding_service = get_embedding_service()

    @staticmethod
    def _last_user_query(messages: List[Dict]) -> str:
        """取出最后一条用户消息作为检索 query"""
        for message in reversed(messages or []):
            if message.get("role") == "user":
                return (message.get("content") or "").strip()
        return ""

    async def retrieve(self, index_id: str, query: str) -> List[dict]:
        """按 index_id 加载向量索引并检索相关片段"""
        embedding_service = get_embedding_service()
        await asyncio.to_thread(embedding_service.load_index, index_id)
        return await embedding_service.search(query, top_k=self.top_k)

    async def generate_stream(
        self,
        messages: List[Dict],
        index_id: str,
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        on_complete: Optional[Callable] = None,
    ) -> AsyncGenerator[str, None]:
        """流式生成基于文档内容的回复

        输出格式与 DeepseekService / OllamaService 保持一致：
        每条消息形如 ``data: "<json 编码的文本片段>"\\n\\n``。
        """
        query = self._last_user_query(messages)
        if not query:
            yield f"data: {json.dumps('没有收到有效的提问内容，请重新描述您的问题。', ensure_ascii=False)}\n\n"
            return

        if not index_id:
            yield f"data: {json.dumps('还没有可用的知识库索引，请先上传文档。', ensure_ascii=False)}\n\n"
            return

        try:
            results = await self.retrieve(index_id, query)
        except Exception as e:
            logger.error(f"RAG retrieve failed for index {index_id}: {str(e)}", exc_info=True)
            error_msg = json.dumps(f"知识库检索失败: {str(e)}", ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
            return

        logger.info(f"RAG retrieved {len(results)} chunks from index {index_id}")

        # 把检索到的片段作为 system 提示前置，其余历史消息原样保留
        system_prompt = RAG_SYSTEM_PROMPT.format(
            context=format_rag_context(results),
            query=query,
        )
        rag_messages = [{"role": "system", "content": system_prompt}] + list(messages)

        chat_service = LLMFactory.create_chat_service()
        async for chunk in chat_service.generate_stream(
            messages=rag_messages,
            user_id=user_id,
            conversation_id=conversation_id,
            on_complete=on_complete,
        ):
            yield chunk
