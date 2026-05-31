from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 应用配置
    app_name: str = "AI RAG System"
    debug: bool = True

    # 数据库配置
    database_url: str = "postgresql+asyncpg://ai_user:%40Ymz3838437890@pgm-uf69uxw5f70j1940vo.pg.rds.aliyuncs.com:5432/ai_chat_db"

    # JWT配置
    secret_key = "bd61eacac24b1ba8bf23d3406385f7218ebaa9695b8bff30f4ca7e5fcf9031e5"
    algorithm = "HS256"
    access_token_expire_minutes = 1440

    # OpenAI配置
    openai_api_key: str = "sk-ldhaiklzafalnajdjwcaxzrjmprorsezoxauhpzbbjxcjsmx"
    openai_base_url: str | None = "https://api.siliconflow.cn/v1"

    # RAG配置
    embedding_model: str = "BAAI/bge-m3"
    vector_dimension: int = 1024
    chunk_size: int = 350
    chunk_overlap: int = 50
    recall_top_k: int = 10
    rerank_top_k: int = 3

    # Reranker配置（硅基流动免费API）
    reranker_api_url: str = "https://api.siliconflow.cn/v1/rerank"
    reranker_api_key: str = "sk-ldhaiklzafalnajdjwcaxzrjmprorsezoxauhpzbbjxcjsmx"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()