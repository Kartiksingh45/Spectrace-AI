import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ChangeRequestStatus, RequestType


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    request_type: Mapped[RequestType | None] = mapped_column(
        Enum(RequestType, name="request_type"), nullable=True
    )
    status: Mapped[ChangeRequestStatus] = mapped_column(
        Enum(ChangeRequestStatus, name="change_request_status"),
        default=ChangeRequestStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
