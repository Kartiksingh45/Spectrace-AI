"""Local embedding generation via sentence-transformers - no external API call."""
from functools import lru_cache

from app.core.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model_name)


def embed_text(text: str) -> list[float]:
    return _get_model().encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _get_model().encode(texts, normalize_embeddings=True).tolist()
