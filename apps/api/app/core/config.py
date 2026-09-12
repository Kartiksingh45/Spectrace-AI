from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    frontend_origin: str = "http://localhost:3000"

    # Reserved for later phases (ingestion / agent) - not used yet.
    groq_api_key: str = ""
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"


settings = Settings()
