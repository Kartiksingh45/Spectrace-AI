import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_project_member
from app.core.config import settings
from app.db.session import get_db
from app.models.content_chunk import ContentChunk
from app.models.document import Document
from app.models.enums import ContentKind, DocumentStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.document import DocumentOut
from app.services.archive import UnsafeArchiveError, extract_safe
from app.services.chunking import DocumentParseError, chunk_code_file, parse_requirement_file
from app.services.embeddings import embed_batch

router = APIRouter(prefix="/projects/{project_id}", tags=["documents"])


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_requirement_document(
    file: UploadFile,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> Document:
    content = await file.read()
    max_bytes = settings.max_document_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds the {settings.max_document_size_mb} MB limit",
        )

    document = Document(project_id=project.id, kind=ContentKind.requirement, filename=file.filename or "untitled")
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        candidates = parse_requirement_file(
            document.filename, content, settings.chunk_size, settings.chunk_overlap
        )
        if candidates:
            vectors = embed_batch([c.text for c in candidates])
            for candidate, vector in zip(candidates, vectors):
                db.add(
                    ContentChunk(
                        project_id=project.id,
                        document_id=document.id,
                        content_type=ContentKind.requirement,
                        text=candidate.text,
                        embedding=vector,
                        source_metadata=candidate.metadata,
                    )
                )
        document.status = DocumentStatus.ready
    except DocumentParseError as exc:
        document.status = DocumentStatus.failed
        document.error = str(exc)

    db.commit()
    db.refresh(document)
    return document


@router.post("/codebases", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_codebase(
    file: UploadFile,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
) -> Document:
    content = await file.read()

    try:
        entries = extract_safe(
            content,
            max_files=settings.max_zip_files,
            max_uncompressed_bytes=settings.max_zip_uncompressed_mb * 1024 * 1024,
        )
    except UnsafeArchiveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = Document(project_id=project.id, kind=ContentKind.code, filename=file.filename or "untitled.zip")
    db.add(document)
    db.commit()
    db.refresh(document)

    candidates = []
    for relpath, file_bytes in entries:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            continue  # not actually a text source file despite its extension; skip it
        candidates.extend(chunk_code_file(text, relpath))

    if not candidates:
        document.status = DocumentStatus.failed
        document.error = "No supported source files found in archive"
    else:
        vectors = embed_batch([c.text for c in candidates])
        for candidate, vector in zip(candidates, vectors):
            db.add(
                ContentChunk(
                    project_id=project.id,
                    document_id=document.id,
                    content_type=ContentKind.code,
                    text=candidate.text,
                    embedding=vector,
                    source_metadata=candidate.metadata,
                )
            )
        document.status = DocumentStatus.ready

    db.commit()
    db.refresh(document)
    return document


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

    db.query(ContentChunk).filter(ContentChunk.document_id == document.id).delete()
    db.delete(document)
    db.commit()
