import re
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.content_chunk import ContentChunk
from app.models.document import Document
from app.models.enums import ContentKind
from app.services.embeddings import embed_text
from app.services.reranker import rerank_scores

_WORD_PATTERN = re.compile(r"[a-zA-Z0-9_]+")

# How much a chunk's cosine-similarity score counts vs. its lexical keyword-overlap score in the
# final ranking - weighted toward the embedding since it's the more reliable general-purpose
# signal, but keyword overlap still pulls exact identifier/error-code matches back up when a
# purely semantic ranking would under-rank them relative to a paraphrased-but-less-relevant chunk.
HYBRID_VECTOR_WEIGHT = 0.7


def _keyword_overlap_score(query: str, text: str) -> float:
    """Fraction of the query's distinct terms (len > 2) that appear literally in `text`."""
    terms = {t for t in _WORD_PATTERN.findall(query.lower()) if len(t) > 2}
    if not terms:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for term in terms if term in text_lower)
    return hits / len(terms)


def _hybrid_rerank(
    rows: list[tuple[ContentChunk, str, float]], query_text: str
) -> list[tuple[ContentChunk, str, float]]:
    """Blend each row's vector-similarity score with a lexical keyword-overlap score against the
    same query, then re-sort by the blended score (implements BRD's optional "hybrid search").
    """
    if not query_text:
        return rows
    scored = [
        (chunk, filename, round(HYBRID_VECTOR_WEIGHT * vector_score + (1 - HYBRID_VECTOR_WEIGHT) * _keyword_overlap_score(query_text, chunk.text), 4))
        for chunk, filename, vector_score in rows
    ]
    scored.sort(key=lambda row: row[2], reverse=True)
    return scored


def _apply_reranker(
    rows: list[tuple[ContentChunk, str, float]], query_text: str, top_n: int = 20
) -> list[tuple[ContentChunk, str, float]]:
    """Reorders (but does not rescore) the top `top_n` rows using the cross-encoder reranker -
    the displayed score stays the hybrid vector+keyword score; only the ordering changes. Falls
    back to the existing order untouched if the reranker model isn't available.
    """
    if not query_text or not rows:
        return rows
    head, tail = rows[:top_n], rows[top_n:]
    scores = rerank_scores(query_text, [chunk.text for chunk, _, _ in head])
    if scores is None:
        return rows
    reranked_head = [row for _, row in sorted(zip(scores, head), key=lambda pair: pair[0], reverse=True)]
    return reranked_head + tail


def search_chunks(
    db: Session,
    project_id: uuid.UUID,
    query_vector: list[float],
    content_type: str,
    limit: int,
    min_score: float | None = None,
    query_text: str = "",
    use_reranker: bool = False,
) -> list[tuple[ContentChunk, str, float]]:
    """Return (chunk, filename, score) tuples, project + type scoped.

    Ranking is hybrid when `query_text` is given: a wider candidate pool is pulled by cosine
    similarity first, then re-ranked by a blend of that similarity and lexical keyword overlap
    with `query_text` (see `_hybrid_rerank`). With `use_reranker=True` on top of that, the leading
    candidates are additionally reordered by a cross-encoder relevance pass (see `_apply_reranker`)
    before truncating to `limit`. Without `query_text` (existing callers that only have an
    embedding, not the original text) it's pure vector search, unchanged from before.
    """
    distance = ContentChunk.embedding.cosine_distance(query_vector)
    max_distance = 1 - (settings.min_relevance_score if min_score is None else min_score)
    pool_size = min(limit * 4, 100) if query_text else limit

    query = (
        db.query(ContentChunk, Document.filename, distance.label("distance"))
        .join(Document, Document.id == ContentChunk.document_id)
        .filter(ContentChunk.project_id == project_id)
        .filter(distance <= max_distance)
    )
    if content_type != "all":
        query = query.filter(ContentChunk.content_type == ContentKind(content_type))

    rows = query.order_by(distance.asc()).limit(pool_size).all()
    scored_rows = [(chunk, filename, round(1 - dist, 4)) for chunk, filename, dist in rows]

    if query_text:
        scored_rows = _hybrid_rerank(scored_rows, query_text)
        if use_reranker:
            scored_rows = _apply_reranker(scored_rows, query_text)
        scored_rows = scored_rows[:limit]
    return scored_rows


def get_chunk_context(db: Session, chunk_id: uuid.UUID, window: int = 1) -> list[ContentChunk]:
    """Return the target chunk plus its nearest neighbors within the same document."""
    target = db.get(ContentChunk, chunk_id)
    if not target:
        return []

    siblings = (
        db.query(ContentChunk)
        .filter(ContentChunk.document_id == target.document_id)
        .order_by(ContentChunk.created_at.asc())
        .all()
    )
    index = next((i for i, c in enumerate(siblings) if c.id == target.id), None)
    if index is None:
        return [target]

    lo = max(0, index - window)
    hi = min(len(siblings), index + window + 1)
    return siblings[lo:hi]


def find_similar_stories(
    db: Session, project_id: uuid.UUID, query: str, limit: int = 3, candidate_pool: int = 20
) -> list[tuple[str, float]]:
    """Rank the project's most recent approved plan summaries by cosine similarity to the query.

    No dedicated embedding index for stories yet - embeds the (small) candidate pool on the fly,
    which is fine at this scale and avoids a new pgvector column for a first cut of this tool.
    """
    from app.models.approval import Approval, ApprovalDecision
    from app.models.change_request import ChangeRequest
    from app.models.generated_plan import GeneratedPlan

    rows = (
        db.query(GeneratedPlan)
        .join(ChangeRequest, ChangeRequest.id == GeneratedPlan.change_request_id)
        .join(Approval, Approval.plan_id == GeneratedPlan.id)
        .filter(ChangeRequest.project_id == project_id)
        .filter(Approval.decision.in_([ApprovalDecision.approved, ApprovalDecision.edit_approved]))
        .order_by(GeneratedPlan.created_at.desc())
        .limit(candidate_pool)
        .all()
    )
    if not rows:
        return []

    summaries = [(plan, plan.content.get("summary", "")) for plan in rows]
    query_vec = embed_text(query)

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))  # both already L2-normalized by embed_text

    scored = []
    for plan, summary in summaries:
        if not summary:
            continue
        vec = embed_text(summary)
        scored.append((summary, cosine(query_vec, vec)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]
