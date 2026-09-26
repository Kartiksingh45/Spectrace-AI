from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    frontend_origin: str = "http://localhost:3000"
    # Local dev: frontend/API are on the same site (different localhost ports), so "lax" +
    # insecure works over plain http. A cross-site deployment (different registrable domains,
    # e.g. Cloudflare Pages + Render) needs "none" + secure=True, or the browser silently drops
    # the session cookie on every cross-origin request after login.
    cookie_samesite: str = "lax"
    cookie_secure: bool = False

    gemini_api_key: str = ""
    gemini_model_name: str = "gemini-3.5-flash-lite"
    # Without an explicit timeout a hung network call (observed in production - two independent
    # runs each stuck indefinitely on the agent's tool-calling call, past classify) blocks forever
    # with no ceiling, orphaning the run at "running" - a background task that raises is at least
    # caught by _invoke_and_sync and marks the run "failed" instead of stuck forever.
    gemini_request_timeout_seconds: int = 30
    agent_max_steps: int = 8
    agent_review_max_retries: int = 2

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    chunk_size: int = 1000
    chunk_overlap: int = 150

    max_document_size_mb: int = 20
    max_zip_files: int = 2000
    max_zip_uncompressed_mb: int = 200
    github_import_max_download_mb: int = 50

    min_relevance_score: float = 0.2


settings = Settings()
