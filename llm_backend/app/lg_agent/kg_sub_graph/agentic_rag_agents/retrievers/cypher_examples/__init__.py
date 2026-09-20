from typing import TYPE_CHECKING, Any

from .base import BaseCypherExampleRetriever
from .northwind_retriever import NorthwindCypherRetriever

__all__ = [
    "BaseCypherExampleRetriever",
    "NorthwindCypherRetriever",
    "Neo4jVectorSearchCypherExampleRetriever",
]

if TYPE_CHECKING:  # pragma: no cover - 仅供类型检查器使用
    from .vector_store import Neo4jVectorSearchCypherExampleRetriever


def __getattr__(name: str) -> Any:
    """惰性导出 Neo4jVectorSearchCypherExampleRetriever。

    该检索器依赖可选包 neo4j-graphrag。lg_builder 导入本包下的
    northwind_retriever 时会触发这个 __init__，如果在此处直接导入
    vector_store，未安装 neo4j-graphrag 的环境连主链路都会起不来。
    """
    if name == "Neo4jVectorSearchCypherExampleRetriever":
        from .vector_store import Neo4jVectorSearchCypherExampleRetriever

        return Neo4jVectorSearchCypherExampleRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
