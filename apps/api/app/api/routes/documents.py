import difflib
import logging
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_project_member
from app.core.config import settings
from app.db.session import get_db
from app.models.content_chunk import ContentChunk
from app.models.document import Document
from app.models.enums import ContentKind, DocumentStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.document import DocumentDiffOut, DocumentOut, GithubImportRequest
from app.services.archive import UnsafeArchiveError, extract_safe
from app.services.chunking import (
    DocumentParseError,
    chunk_code_file,
    extract_requirement_text,
    parse_requirement_file,
)
from app.services.embeddings import embed_batch
from app.services.github_import import GithubImportError, download_repo_zip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}", tags=["documents"])


def _embed_and_finish(
    db: Session,
    document_id: uuid.UUID,
    project_id: uuid.UUID,
    content_type: ContentKind,
    candidates: list,
    started: float,
) -> None:
    """Runs as a BackgroundTask: the slow, network-bound part of ingestion (embedding, which can
    take anywhere from seconds to minutes once Gemini's free-tier rate limit forces retries with
    backoff). Kept out of the request/response cycle so a big upload can't block past a proxy's
    timeout - the document is already visible to the client with status=processing by the time
    this runs."""
    document = db.get(Document, document_id)
    try:
        vectors = embed_batch([c.text for c in candidates])
        for candidate, vector in zip(candidates, vectors):
            db.add(
                ContentChunk(
                    project_id=project_id,
                    document_id=document_id,
                    content_type=content_type,
                    text=candidate.text,
                    embedding=vector,
                    source_metadata=candidate.metadata,
                )
            )
        document.status = DocumentStatus.ready
    except Exception:
        db.rollback()
        logger.exception("Document ingestion failed for document %s", document_id)
        document.status = DocumentStatus.failed
        document.error = "Ingestion failed due to an internal error"

    document.duration_ms = int((time.monotonic() - started) * 1000)
    db.commit()
    logger.info(
        "document_ingested document_id=%s project_id=%s status=%s duration_ms=%s",
        document_id, project_id, document.status.value, document.duration_ms,
    )


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_requirement_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> Document:
    started = time.monotonic()
    content = await file.read()
    max_bytes = settings.max_document_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds the {settings.max_document_size_mb} MB limit",
        )

    filename = file.filename or "untitled"
    previous_version = (
        db.query(Document)
        .filter(
            Document.project_id == project.id,
            Document.kind == ContentKind.requirement,
            Document.filename == filename,
        )
        .order_by(Document.version.desc())
        .first()
    )
    version = previous_version.version + 1 if previous_version else 1
    previous_version_id = previous_version.id if previous_version else None

    try:
        full_text = extract_requirement_text(filename, content)
        candidates = parse_requirement_file(filename, content, settings.chunk_size, settings.chunk_overlap)
    except DocumentParseError as exc:
        document = Document(
            project_id=project.id,
            kind=ContentKind.requirement,
            filename=filename,
            version=version,
            previous_version_id=previous_version_id,
            status=DocumentStatus.failed,
            error=str(exc),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    document = Document(
        project_id=project.id,
        kind=ContentKind.requirement,
        filename=filename,
        version=version,
        previous_version_id=previous_version_id,
        full_text=full_text,
        status=DocumentStatus.processing,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(
        _embed_and_finish, db, document.id, project.id, ContentKind.requirement, candidates, started
    )
    return document


def _ingest_codebase_zip(
    db: Session,
    project: Project,
    filename: str,
    zip_bytes: bytes,
    background_tasks: BackgroundTasks,
) -> Document:
    """Shared by both a direct ZIP upload and a GitHub import - everything from safe extraction
    onward is identical regardless of where the archive's bytes came from."""
    started = time.monotonic()

    try:
        entries = extract_safe(
            zip_bytes,
            max_files=settings.max_zip_files,
            max_uncompressed_bytes=settings.max_zip_uncompressed_mb * 1024 * 1024,
        )
    except UnsafeArchiveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    candidates = []
    for relpath, file_bytes in entries:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            continue  # not actually a text source file despite its extension; skip it
        candidates.extend(chunk_code_file(text, relpath))

    if not candidates:
        document = Document(
            project_id=project.id,
            kind=ContentKind.code,
            filename=filename,
            status=DocumentStatus.failed,
            error="No supported source files found in archive",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    document = Document(project_id=project.id, kind=ContentKind.code, filename=filename, status=DocumentStatus.processing)
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(
        _embed_and_finish, db, document.id, project.id, ContentKind.code, candidates, started
    )
    return document


@router.post("/codebases", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_codebase(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> Document:
    content = await file.read()
    return _ingest_codebase_zip(db, project, file.filename or "untitled.zip", content, background_tasks)


@router.post("/github-import", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def import_github_repo(
    payload: GithubImportRequest,
    background_tasks: BackgroundTasks,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> Document:
    """Read-only import: downloads a public repo's ZIP from GitHub's codeload endpoint (no git
    binary, no OAuth token, no write access ever requested) and runs it through the same safe
    extraction + chunking pipeline as a directly-uploaded codebase ZIP."""
    try:
        zip_bytes = download_repo_zip(
            payload.owner, payload.repo, payload.branch,
            max_bytes=settings.github_import_max_download_mb * 1024 * 1024,
        )
    except GithubImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    filename = f"{payload.owner}/{payload.repo}@{payload.branch}"
    return _ingest_codebase_zip(db, project, filename, zip_bytes, background_tasks)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    project: Project = Depends(require_project_member), db: Session = Depends(get_db)
) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.project_id == project.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.get("/documents/{document_id}/diff", response_model=DocumentDiffOut)
def diff_document_versions(
    document_id: uuid.UUID,
    against: uuid.UUID,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> DocumentDiffOut:
    to_doc = db.get(Document, document_id)
    from_doc = db.get(Document, against)
    if (
        not to_doc
        or not from_doc
        or to_doc.project_id != project.id
        or from_doc.project_id != project.id
        or to_doc.kind != ContentKind.requirement
        or from_doc.kind != ContentKind.requirement
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if from_doc.full_text is None or to_doc.full_text is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both documents must be ready before they can be compared")

    diff_lines = list(
        difflib.unified_diff(
            from_doc.full_text.splitlines(),
            to_doc.full_text.splitlines(),
            fromfile=f"{from_doc.filename} (v{from_doc.version})",
            tofile=f"{to_doc.filename} (v{to_doc.version})",
            lineterm="",
        )
    )
    return DocumentDiffOut(
        from_document_id=from_doc.id,
        from_version=from_doc.version,
        to_document_id=to_doc.id,
        to_version=to_doc.version,
        diff_lines=diff_lines,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    document = db.get(Document, document_id)
    if not document or document.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # A newer version may still point back at this one via previous_version_id - null that out
    # first so deleting an older version doesn't hit a foreign-key violation.
    db.query(Document).filter(Document.previous_version_id == document.id).update({"previous_version_id": None})
    db.query(ContentChunk).filter(ContentChunk.document_id == document.id).delete()
    db.delete(document)
    db.commit()
