from typing import List, Dict, AsyncGenerator, Optional, Callable
import aiohttp
import json
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(service="ollama")

class OllamaService:
    def __init__(self, model: Optional[str] = None):
        logger.info("Initializing Ollama Service")
        self.base_url = settings.OLLAMA_BASE_URL
        self.chat_model = settings.OLLAMA_CHAT_MODEL
        self.reason_model = settings.OLLAMA_REASON_MODEL
        # 由 LLMFactory 按用途注入具体模型：问答走 chat_model，深度思考走 reason_model。
        # 不传时回退到问答模型，保持与旧调用方式的兼容。
        self.model = model or self.chat_model

    async def generate_stream(
        self, 
        messages: List[Dict],
        user_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        on_complete: Optional[Callable] = None
    ) -> AsyncGenerator[str, None]:
        """流式生成回复"""
        try:
            # 使用构造时注入的模型，避免问答接口误用推理模型
            model = self.model
            logger.info(f"Using model: {model}")
            
            full_response = []
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True,
                        "keep_alive": -1,
                        "options": {
                            "temperature": 0.7,
                        }
                    }
                ) as response:
                    async for line in response.content:
                        if line:
                            try:
                                chunk = json.loads(line)
                                if content := chunk.get("message", {}).get("content"):
                                    full_response.append(content)
                                    # 使用 json.dumps 确保内容格式正确
                                    content = json.dumps(content, ensure_ascii=False)
                                    yield f"data: {content}\n\n"
                            except json.JSONDecodeError as e:
                                logger.error(f"JSON decode error: {str(e)}")
                                continue

            # 如果有回调函数，调用它
            if on_complete and user_id is not None and conversation_id is not None:
                complete_response = "".join(full_response)
                await on_complete(user_id, conversation_id, messages, complete_response)

        except Exception as e:
            logger.error(f"Stream generation error: {str(e)}")
            error_msg = json.dumps(f"生成回复时出错: {str(e)}", ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
            raise

    async def generate(self, messages: List[Dict]) -> str:
        """非流式生成回复"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "keep_alive": -1,
                        "options": {
                            "temperature": 0.7,
                        }
                    }
                ) as response:
                    result = await response.json()
                    return result["message"]["content"]

        except Exception as e:
            print(f"Generation error: {str(e)}")
            raise 
