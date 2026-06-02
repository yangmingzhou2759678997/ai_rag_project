# 文件路径: config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


# =================================================================
# 全局配置中心类：利用 Pydantic 自动从 .env 文件提取变量
# =================================================================
class Settings(BaseSettings):
    # 1. 基础应用配置 (设置了默认值的，表示哪怕 .env 里没写，系统也不会崩)
    app_name: str = "AI RAG System"
    environment: str = "development"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    log_level: str = "INFO"

    # 2. 大模型 API 配置
    # 🚨 极其重要：只声明类型(如 str)，坚决不写 = "sk-xxx"。
    # 这样 Pydantic 启动时，如果没在 .env 找到这些机密信息，就会直接拦截报错，保证绝不带病启动！
    openai_api_key: str
    openai_base_url: str
    chat_model: str
    openai_temperature: float = 0.1
    openai_max_tokens: int = 1024

    # 3. 核心 RAG 向量化与切片配置
    embedding_model: str = "BAAI/bge-m3"
    vector_dimension: int = 1024
    chunk_size: int = 350
    chunk_overlap: int = 50
    recall_top_k: int = 10
    rerank_top_k: int = 3
    rerank_score_threshold: float = 0.5

    # 4. Reranker 线上高性能重排接口配置
    reranker_api_url: str = "https://api.siliconflow.cn/v1/rerank"
    reranker_api_key: str
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # 5. 关系型向量数据库配置
    db_host: str
    db_port: int = 5432
    db_user: str
    db_password: str
    db_name: str
    database_url: str  # 接收完整的带密码转义的异步连接字符串

    # 6. 【完美向下兼容垫片】
    # 因为你之前的 database.py 习惯了调用 settings.DB_URL (大写)
    # 我在这里写了一个属性代理，只要有人叫 DB_URL，我就把 database_url 给他。
    # 这样可以确保你以前的代码绝对不报错！
    @property
    def DB_URL(self) -> str:
        return self.database_url

    # 7. 安全鉴权 JWT 配置
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # 8. 系统防御矩阵配置
    ratelimit_chat: str = "15/minute"
    ratelimit_upload: str = "10/minute"
    upload_dir: str = "./uploads"
    max_upload_size: int = 10485760
    allowed_extensions: str = "txt,md,docx,pdf"

    log_file: str = "./logs/app.log"
    log_rotation: str = "500MB"
    log_retention: str = "7 days"
    weather_api_timeout: int = 10
    max_tool_calls: int = 3
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:8000"

    # =================================================================
    # Pydantic 核心行为指令：去哪里找配置文件？
    # =================================================================
    model_config = SettingsConfigDict(
        env_file=".env",  # 指示：请去项目根目录读取 .env 文件
        env_file_encoding="utf-8",  # 指示：使用 utf-8 读取，防止中文注释乱码报错
        extra="ignore"  # 核心防锅设计：自动忽略 .env 文件里我们用不到的废旧/多余变量
    )


# 9. 实例化出全局唯一单例对象 (Singleton)。整个项目所有人，全用这一个 settings！
settings = Settings()