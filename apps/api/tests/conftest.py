import hashlib
import math
import os
import random

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


def _deterministic_vector(text: str, dimensions: int) -> list[float]:
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)
    vec = [rng.uniform(-1, 1) for _ in range(dimensions)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch):
    """Embeddings now call the real Jina AI API (see app/services/embeddings.py) - tests must
    never hit that for real, or the suite becomes slow, flaky, quota-limited, and non-free to run.
    A deterministic hash-based vector stands in; nothing in this suite asserts on actual semantic
    similarity from real embeddings (search_chunks itself can't run on SQLite anyway - pgvector's
    cosine_distance has no SQLite equivalent, see test_retrieval_service.py), so this is safe.
    A test that explicitly patches one of these targets itself (e.g. with its own @patch/fixture)
    overrides this default for its own duration, same as any other monkeypatch.
    """

    def fake_embed_batch(texts, **kwargs):
        return [_deterministic_vector(t, settings.embedding_dimensions) for t in texts]

    def fake_embed_text(text, **kwargs):
        return _deterministic_vector(text, settings.embedding_dimensions)

    monkeypatch.setattr("app.api.routes.documents.embed_batch", fake_embed_batch)
    monkeypatch.setattr("app.api.routes.search.embed_text", fake_embed_text)
    monkeypatch.setattr("app.agent.tools.embed_text", fake_embed_text)
    monkeypatch.setattr("app.services.retrieval.embed_text", fake_embed_text)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
