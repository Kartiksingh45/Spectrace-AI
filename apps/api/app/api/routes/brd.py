import uuid
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_brd_generator, get_current_user, require_project_member
from app.db.session import get_db
from app.models.brd_document import BrdDocument
from app.models.project import Project
from app.models.user import User
from app.schemas.brd import BrdDocumentOut, BrdInput, GeneratedBrd

router = APIRouter(prefix="/projects/{project_id}/brd", tags=["brd"])


@router.post("", response_model=BrdDocumentOut, status_code=status.HTTP_201_CREATED)
def generate_brd_document(
    payload: BrdInput,
    project: Project = Depends(require_project_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    generator: Callable[[BrdInput], GeneratedBrd] = Depends(get_brd_generator),
) -> BrdDocument:
    try:
        generated = generator(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not generate a BRD right now - try again shortly"
        ) from exc

    document = BrdDocument(
        project_id=project.id,
        created_by=user.id,
        inputs=payload.model_dump(),
        content=generated.model_dump(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("", response_model=list[BrdDocumentOut])
def list_brd_documents(
    project: Project = Depends(require_project_member), db: Session = Depends(get_db)
) -> list[BrdDocument]:
    return (
        db.query(BrdDocument)
        .filter(BrdDocument.project_id == project.id)
        .order_by(BrdDocument.created_at.desc())
        .all()
    )


@router.delete("/{brd_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brd_document(
    brd_id: uuid.UUID, project: Project = Depends(require_project_member), db: Session = Depends(get_db)
) -> None:
    document = db.get(BrdDocument, brd_id)
    if not document or document.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BRD not found")
    db.delete(document)
    db.commit()
