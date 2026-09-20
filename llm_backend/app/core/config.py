from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from enum import Enum
from pathlib import Path

# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

class ServiceType(str, Enum):
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"

class Settings(BaseSettings):
    # Deepseek settings
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_MODEL: str
    # 深度思考使用的模型。DeepSeek 的推理模型与问答模型是两个不同的名字，
    # 不能共用 DEEPSEEK_MODEL，否则 /api/reason 会退化成普通问答。
    DEEPSEEK_REASON_MODEL: str = "deepseek-reasoner"
    
    # Vision Model settings (独立配置)
    VISION_API_KEY: str
    VISION_BASE_URL: str
    VISION_MODEL: str
    
    # Ollama settings
    OLLAMA_BASE_URL: str
    OLLAMA_CHAT_MODEL: str
    OLLAMA_REASON_MODEL: str
    OLLAMA_EMBEDDING_MODEL: str
    OLLAMA_AGENT_MODEL: str
    # Service selection
    CHAT_SERVICE: ServiceType = ServiceType.DEEPSEEK
    REASON_SERVICE: ServiceType = ServiceType.OLLAMA
    AGENT_SERVICE: ServiceType = ServiceType.DEEPSEEK
    
    # Search settings
    SERPAPI_KEY: str
    SEARCH_RESULT_COUNT: int = 3
    
    # Database settings
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    
    # Neo4j settings
    NEO4J_URL: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
    
    # JWT settings
    SECRET_KEY: str = "your-secret-key"  # 在生产环境中使用安全的密钥
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis settings
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_CACHE_EXPIRE: int = 3600
    REDIS_CACHE_THRESHOLD: float = 0.8
    
    # Embedding settings 
    EMBEDDING_TYPE: str = "ollama"  # ollama 或 sentence_transformer
    EMBEDDING_MODEL: str = "bge-m3"  # ollama embedding模型
    EMBEDDING_THRESHOLD: float = 0.90  # 语义相似度阈值
    
    # GraphRAG settings
    # 留空即可，_resolve_graphrag_dir 会自动指向内置的 app/graphrag。
    # validate_default=True 是必需的：pydantic v2 默认不拿校验器处理字段默认值，
    # 若 .env 中完全没有 GRAPHRAG_PROJECT_DIR 这一项，兜底逻辑就不会触发。
    # 注意该参数属于 Field()，field_validator() 并不接受它。
    GRAPHRAG_PROJECT_DIR: str = Field(default="", validate_default=True)  # GraphRAG项目目录
    GRAPHRAG_DATA_DIR: str = "data"                         # 数据目录名称
    GRAPHRAG_QUERY_TYPE: str = "local"                      # 查询类型
    GRAPHRAG_RESPONSE_TYPE: str = "text"                    # 响应类型
    GRAPHRAG_COMMUNITY_LEVEL: int = 3                       # 社区级别
    GRAPHRAG_DYNAMIC_COMMUNITY: bool = False                # 是否动态选择社区
    
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def REDIS_URL(self) -> str:
        """构建Redis URL"""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def NEO4J_CONN_URL(self) -> str:
        """构建Neo4j连接URL"""
        return f"{self.NEO4J_URL}"
    
    @field_validator("GRAPHRAG_PROJECT_DIR", mode="after")
    @classmethod
    def _resolve_graphrag_dir(cls, value: str) -> str:
        """把 GraphRAG 项目目录统一解析成本机可用的绝对路径。

        .env 里很容易残留别人机器上的绝对路径（换机器后该目录并不存在），
        这里做三层兜底：留空、相对路径、指向不存在的目录，都回退到内置的
        app/graphrag，避免索引和查询因为路径问题整体失效。
        """
        bundled = str((ROOT_DIR / "app" / "graphrag").resolve())
        raw = (value or "").strip()
        if not raw:
            return bundled

        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT_DIR / candidate
        candidate = candidate.resolve()
        return str(candidate) if candidate.is_dir() else bundled

    class Config:
        env_file = str(ENV_FILE)  # 使用绝对路径
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings() 
