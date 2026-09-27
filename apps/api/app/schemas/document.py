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
    duration_ms: int | None
    version: int
    previous_version_id: uuid.UUID | None
    chunks_total: int | None
    chunks_embedded: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GithubImportRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=100)
    repo: str = Field(min_length=1, max_length=100)
    branch: str = Field(default="main", min_length=1, max_length=200)


class DocumentDiffOut(BaseModel):
    from_document_id: uuid.UUID
    from_version: int
    to_document_id: uuid.UUID
    to_version: int
    diff_lines: list[str]


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
