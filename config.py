from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # Application
    app_name: str = "AI RAG System"
    environment: str = "development"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    log_level: str = "INFO"

    # LLM
    openai_api_key: str
    openai_base_url: str
    chat_model: str
    openai_temperature: float = 0.1
    openai_max_tokens: int = 1024

    # RAG
    embedding_model: str = "BAAI/bge-m3"
    vector_dimension: int = 1024
    chunk_size: int = 350
    chunk_overlap: int = 50
    recall_top_k: int = 10
    rerank_top_k: int = 3
    rerank_score_threshold: float = 0.25

    # Reranker
    reranker_api_url: str = "https://api.siliconflow.cn/v1/rerank"
    reranker_api_key: str
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # PostgreSQL
    db_host: str
    db_port: int = 5432
    db_user: str
    db_password: str
    db_name: str
    database_url: str

    @property
    def DB_URL(self) -> str:
        """Compatibility property used by database.py."""
        return self.database_url

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Runtime
    max_upload_size: int = 10_485_760
    allowed_extensions: str = "txt,md,pdf,docx,xlsx"

    log_file: str = "./logs/app.log"
    log_rotation: str = "500MB"
    log_retention: str = "7 days"
    weather_api_timeout: int = 10
    cors_allow_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://127.0.0.1:8000"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
