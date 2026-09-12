from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_project_member
from app.core.config import settings
from app.db.session import get_db
from app.models.content_chunk import ContentChunk
from app.models.document import Document
from app.models.enums import ContentKind
from app.models.project import Project
from app.schemas.document import SearchRequest, SearchResponse, SearchResult
from app.services.embeddings import embed_text

router = APIRouter(prefix="/projects/{project_id}", tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> SearchResponse:
    query_vector = embed_text(payload.query)
    distance = ContentChunk.embedding.cosine_distance(query_vector)
    max_distance = 1 - settings.min_relevance_score

    query = (
        db.query(ContentChunk, Document.filename, distance.label("distance"))
        .join(Document, Document.id == ContentChunk.document_id)
        .filter(ContentChunk.project_id == project.id)
        .filter(distance <= max_distance)
    )
    if payload.content_type != "all":
        query = query.filter(ContentChunk.content_type == ContentKind(payload.content_type))

    rows = query.order_by(distance.asc()).limit(payload.limit).all()

    results = [
        SearchResult(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            content_type=chunk.content_type,
            text=chunk.text,
            score=round(1 - dist, 4),
            source_metadata=chunk.source_metadata,
        )
        for chunk, filename, dist in rows
    ]
    return SearchResponse(results=results)
