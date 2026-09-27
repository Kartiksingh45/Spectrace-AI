"""Gemini-backed embedding generation - replaces a local sentence-transformers/PyTorch model,
which pushed peak memory past a constrained host's limit (observed in production: the deployed
API was repeatedly OOM-killed at >512MB on Render's free tier once real ingestion/search traffic
touched it). Embeddings are truncated to settings.embedding_dimensions via Gemini's
output_dimensionality parameter, matching the existing pgvector column width - no migration
needed for chunks embedded under the old model's same dimension.
"""
import math
from functools import lru_cache

from app.core.config import settings

# Google's batch embed endpoint caps a single request at 100 inputs.
_MAX_BATCH_SIZE = 100


@lru_cache(maxsize=1)
def _get_client():
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


def _normalize(vector: list[float]) -> list[float]:
    """Gemini only unit-normalizes its native (full-width) output - a truncated
    output_dimensionality result is NOT pre-normalized, but the rest of this codebase (the manual
    dot-product "cosine" shortcut in retrieval.py's find_similar_stories) assumes it is.
    """
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


def embed_text(text: str) -> list[float]:
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    from google.genai import types

    client = _get_client()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH_SIZE):
        batch = texts[i : i + _MAX_BATCH_SIZE]
        result = client.models.embed_content(
            model=settings.embedding_model_name,
            contents=batch,
            config=types.EmbedContentConfig(output_dimensionality=settings.embedding_dimensions),
        )
        vectors.extend(_normalize(list(e.values)) for e in result.embeddings)
    return vectors
