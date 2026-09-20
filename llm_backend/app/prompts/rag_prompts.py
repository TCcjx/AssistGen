"""本地知识库（RAG）问答的提示词管理"""

# RAG 系统提示：要求模型只依据检索到的文档片段作答
RAG_SYSTEM_PROMPT = """你是一个电商领域的智能客服，需要依据用户提供的文档内容来回答问题。

下面是从用户文档中检索到的相关片段，用 <context> 标签包裹。这些内容不是对话的一部分，只作为你回答的依据：

<context>
{context}
</context>

回答时请遵循以下规则：
1. 只能使用 <context> 中的信息作答，不要编造文档里没有的内容。
2. 如果 <context> 中没有能回答用户问题的信息，请坦诚说明没有找到相关内容，并引导用户补充说明或重新上传文档。
3. 语气亲切、专业，可以使用"亲～"等称呼，适当使用 emoji。
4. 答案要简洁清晰，必要时分点说明，避免冗长。
5. 涉及操作步骤、参数、保修条款等关键信息时，请如实引用文档中的表述。

用户问题：{query}"""


def format_rag_context(results: list) -> str:
    """将检索结果格式化为提示词上下文

    Args:
        results: EmbeddingService.search 返回的结果列表，
                 每项包含 content / score / metadata 字段。

    Returns:
        拼接后的上下文字符串，每个片段带有来源与页码标注。
    """
    if not results:
        return "（未检索到相关文档片段）"

    blocks = []
    for i, item in enumerate(results, start=1):
        metadata = item.get("metadata") or {}
        source = metadata.get("source", "未知来源")
        page = metadata.get("page")
        location = f"第 {page} 页" if page else ""
        content = (item.get("content") or "").strip()
        blocks.append(f"[片段 {i}] 来源：{source} {location}\n{content}")
    return "\n\n".join(blocks)
