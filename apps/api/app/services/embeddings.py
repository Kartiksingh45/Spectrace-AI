"""Gemini-backed embedding generation - replaces a local sentence-transformers/PyTorch model,
which pushed peak memory past a constrained host's limit (observed in production: the deployed
API was repeatedly OOM-killed at >512MB on Render's free tier once real ingestion/search traffic
touched it). Embeddings are truncated to settings.embedding_dimensions via Gemini's
output_dimensionality parameter, matching the existing pgvector column width - no migration
needed for chunks embedded under the old model's same dimension.
"""
import logging
import math
import time
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

# Google's batch embed endpoint caps a single request at 100 inputs.
_MAX_BATCH_SIZE = 100
# The free tier's embedding quota is tight enough that even one real codebase upload (many
# chunks -> many batchEmbedContents calls in quick succession) can trip a per-minute rate limit -
# observed in production as a 429 RESOURCE_EXHAUSTED. Retrying with backoff recovers from that
# burst; it does NOT help if the quota is exhausted for a longer window (e.g. daily) - that
# surfaces as the same 429 after retries are exhausted, and needs waiting for the quota to reset
# or a higher Gemini API quota, not a code fix.
_MAX_RETRIES = 5
_BASE_RETRY_DELAY_SECONDS = 5


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


def _embed_with_retry(client, batch: list[str], config):
    from google.genai.errors import ClientError

    for attempt in range(_MAX_RETRIES + 1):
        try:
            return client.models.embed_content(
                model=settings.embedding_model_name,
                contents=batch,
                config=config,
            )
        except ClientError as exc:
            if exc.code != 429 or attempt == _MAX_RETRIES:
                raise
            delay = _BASE_RETRY_DELAY_SECONDS * (2**attempt)
            logger.warning(
                "Gemini embedding quota hit (429), retrying in %ss (attempt %s/%s)",
                delay,
                attempt + 1,
                _MAX_RETRIES,
            )
            time.sleep(delay)


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    from google.genai import types

    client = _get_client()
    config = types.EmbedContentConfig(output_dimensionality=settings.embedding_dimensions)
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH_SIZE):
        batch = texts[i : i + _MAX_BATCH_SIZE]
        result = _embed_with_retry(client, batch, config)
        vectors.extend(_normalize(list(e.values)) for e in result.embeddings)
    return vectors
