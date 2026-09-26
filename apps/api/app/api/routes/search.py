from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_project_member
from app.db.session import get_db
from app.models.project import Project
from app.schemas.document import SearchRequest, SearchResponse, SearchResult
from app.services.embeddings import embed_text
from app.services.retrieval import search_chunks

router = APIRouter(prefix="/projects/{project_id}", tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> SearchResponse:
    query_vector = embed_text(payload.query)
    rows = search_chunks(
        db, project.id, query_vector, payload.content_type, payload.limit,
        query_text=payload.query, use_reranker=True,
    )

    results = [
        SearchResult(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            content_type=chunk.content_type,
            text=chunk.text,
            score=score,
            source_metadata=chunk.source_metadata,
        )
        for chunk, filename, score in rows
    ]
    return SearchResponse(results=results)
