import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import ContentKind, DocumentStatus


class DocumentOut(BaseModel):
    id: uuid.UUID
    kind: ContentKind
    filename: str
    status: DocumentStatus
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    content_type: Literal["requirement", "code", "all"] = "all"
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    content_type: ContentKind
    text: str
    score: float
    source_metadata: dict[str, Any]


class SearchResponse(BaseModel):
    results: list[SearchResult]
