from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    frontend_origin: str = "http://localhost:3000"

    groq_api_key: str = ""
    groq_model_name: str = "openai/gpt-oss-120b"
    agent_max_steps: int = 8
    agent_review_max_retries: int = 2

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    chunk_size: int = 1000
    chunk_overlap: int = 150

    max_document_size_mb: int = 20
    max_zip_files: int = 2000
    max_zip_uncompressed_mb: int = 200

    min_relevance_score: float = 0.2


settings = Settings()
