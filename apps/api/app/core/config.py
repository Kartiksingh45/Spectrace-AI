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
    # Defensive ceiling on a call that could otherwise hang indefinitely - not the cause of the
    # "stuck forever" issue actually observed in production (that was the host running out of
    # memory and getting OOM-killed, not a hung network call), but still worth having.
    gemini_request_timeout_seconds: int = 30
    agent_max_steps: int = 8
    agent_review_max_retries: int = 2

    # Embeddings run through Jina AI, not Gemini (which the LLM calls above still use) - Gemini's
    # free-tier embedding quota proved too tight for real ingestion traffic (see embeddings.py).
    jina_api_key: str = ""
    embedding_model_name: str = "jina-embeddings-v3"
    embedding_dimensions: int = 384
    # The cross-encoder reranker loads a second PyTorch model on top of the embedding model - on a
    # memory-constrained host (e.g. Render's free 512MB tier, which was observed to OOM-kill this
    # process) that second model can be the difference between fitting and not. It's optional
    # (BRD: "a reranker that improves ordering") - set to false to skip loading it entirely.
    enable_reranker: bool = True

    chunk_size: int = 1000
    chunk_overlap: int = 150

    # Forgot-password emails, sent via Resend's HTTP API (free tier, no card required - see
    # https://resend.com). Left blank, forgot-password silently no-ops (still returns 204, since
    # that response must never reveal whether an email exists either way) rather than erroring.
    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"
    password_reset_token_expire_minutes: int = 30

    max_document_size_mb: int = 20
    max_zip_files: int = 2000
    max_zip_uncompressed_mb: int = 200
    github_import_max_download_mb: int = 50

    min_relevance_score: float = 0.2


settings = Settings()
