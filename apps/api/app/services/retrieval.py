import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.content_chunk import ContentChunk
from app.models.document import Document
from app.models.enums import ContentKind
from app.services.embeddings import embed_text


def search_chunks(
    db: Session,
    project_id: uuid.UUID,
    query_vector: list[float],
    content_type: str,
    limit: int,
    min_score: float | None = None,
) -> list[tuple[ContentChunk, str, float]]:
    """Return (chunk, filename, score) tuples ranked by cosine similarity, project + type scoped."""
    distance = ContentChunk.embedding.cosine_distance(query_vector)
    max_distance = 1 - (settings.min_relevance_score if min_score is None else min_score)

    query = (
        db.query(ContentChunk, Document.filename, distance.label("distance"))
        .join(Document, Document.id == ContentChunk.document_id)
        .filter(ContentChunk.project_id == project_id)
        .filter(distance <= max_distance)
    )
    if content_type != "all":
        query = query.filter(ContentChunk.content_type == ContentKind(content_type))

    rows = query.order_by(distance.asc()).limit(limit).all()
    return [(chunk, filename, round(1 - dist, 4)) for chunk, filename, dist in rows]


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
