"""Cross-encoder reranker: a second, more expensive relevance pass over an already-retrieved
candidate pool. Unlike the embedding similarity used for initial retrieval (which scores the
query and each chunk independently, then compares vectors), a cross-encoder scores the query and
a candidate TOGETHER, which can catch relevance a purely independent comparison misses.
"""
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(_MODEL_NAME)


def rerank_scores(query: str, candidates: list[str]) -> list[float] | None:
    """Relevance score per candidate, same order as `candidates`. Returns None (caller should
    fall back to its existing ranking) if the reranker can't be loaded or run for any reason - a
    missing optional enhancement should never break retrieval.
    """
    if not candidates:
        return []
    try:
        pairs = [(query, c) for c in candidates]
        return [float(s) for s in _get_model().predict(pairs)]
    except Exception:
        logger.warning("Reranker unavailable, falling back to the existing ranking", exc_info=True)
        return None
