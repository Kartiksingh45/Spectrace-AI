"""Jina AI-backed embedding generation - replaces Gemini's embedding API, whose free-tier daily
quota proved too tight for real ingestion traffic (a single codebase ZIP upload, or even a
handful of agent search steps, could exhaust it - see git history on this file for the earlier
sentence-transformers/PyTorch -> Gemini -> Jina progression and why each prior step wasn't
enough). The LLM (classification, plan generation, the agent's tool loop) still runs on Gemini
via langchain-google-genai - only embeddings moved, since Gemini's chat quota was never the
bottleneck. Jina's `task` parameter asks for a query- or passage-tuned embedding, which the
underlying model actually optimizes differently (unlike Gemini's embedding API, which had no such
distinction) - retrieval quality benefits from using the right one at each call site.
"""
import logging
import time
from typing import Callable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.jina.ai/v1/embeddings"
# Jina's endpoint accepts far more than this per call (published limit is in the thousands) - the
# real constraint in practice turned out to be *request frequency*, not payload size (observed in
# production: a batch succeeds, then the very next one gets a 429 almost immediately, regardless
# of how big either one was). So the fix is fewer, bigger requests, not smaller ones - a large
# codebase that needed dozens of 100-text calls (each its own chance to collide with the rate
# limit) needs only a handful at this size, cutting total ingestion time roughly proportionally.
_MAX_BATCH_SIZE = 500
# A daily-exhausted quota won't be fixed by retrying (see the module docstring's history) - this
# budget is sized to ride out a brief per-minute rate limit, not a longer-window cap.
_MAX_RETRIES = 5
_BASE_RETRY_DELAY_SECONDS = 5
# embed_text() backs interactive, user-facing calls (agent tool calls during a live run, the
# direct semantic search endpoint) - a user is synchronously waiting on the request, so it fails
# fast with one short retry rather than blocking for the full multi-minute budget above, which is
# only appropriate for the backgrounded bulk-ingestion path (embed_batch, called directly).
_INTERACTIVE_MAX_RETRIES = 1
# A large codebase produces many back-to-back batches - observed in production firing them with
# no pacing collided with Jina's per-request rate limit on nearly every single batch, burning
# retries (and multiple minutes) that a small proactive gap between batches mostly avoids.
_INTER_BATCH_DELAY_SECONDS = 1.5


def embed_text(text: str, task: str = "retrieval.query") -> list[float]:
    return embed_batch([text], task=task, max_retries=_INTERACTIVE_MAX_RETRIES)[0]


def _post_with_retry(payload: dict, max_retries: int, timeout: float) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Content-Type": "application/json",
    }
    for attempt in range(max_retries + 1):
        try:
            response = httpx.post(_API_URL, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == max_retries:
                # Jina's response body names the actual rejection reason (bad param, input too
                # long, etc.) but raise_for_status()'s own message omits it entirely - without
                # this, a non-429 failure shows up in logs as a bare "400 Bad Request" with no way
                # to tell what was wrong with the request short of reproducing it.
                raise httpx.HTTPStatusError(
                    f"{exc}: {exc.response.text}", request=exc.request, response=exc.response
                ) from exc
            delay = _BASE_RETRY_DELAY_SECONDS * (2**attempt)
            logger.warning(
                "Jina embedding quota hit (429), retrying in %ss (attempt %s/%s)",
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # loop always returns or raises


def embed_batch(
    texts: list[str],
    task: str = "retrieval.passage",
    max_retries: int = _MAX_RETRIES,
    on_batch_done: Callable[[int], None] | None = None,
) -> list[list[float]]:
    """on_batch_done, if given, is called with the running total of embedded texts after each
    batch completes - bulk ingestion uses it to persist live progress a client can poll, since a
    large codebase can take minutes (see _INTER_BATCH_DELAY_SECONDS) with no other signal
    otherwise that anything is happening."""
    if not texts:
        return []

    vectors: list[list[float]] = []
    for i in range(0, len(texts), _MAX_BATCH_SIZE):
        if i > 0:
            time.sleep(_INTER_BATCH_DELAY_SECONDS)
        batch = texts[i : i + _MAX_BATCH_SIZE]
        payload = {
            "model": settings.embedding_model_name,
            "task": task,
            "dimensions": settings.embedding_dimensions,
            "normalized": True,
            "embedding_type": "float",
            "input": batch,
        }
        # Scales with batch size - a 500-text bulk-ingestion batch takes proportionally longer for
        # Jina to compute server-side than the single-text interactive path needs to wait for.
        timeout = 20 + len(batch) * 0.15
        result = _post_with_retry(payload, max_retries, timeout)
        vectors.extend(item["embedding"] for item in sorted(result["data"], key=lambda d: d["index"]))
        if on_batch_done:
            on_batch_done(len(vectors))
    return vectors
