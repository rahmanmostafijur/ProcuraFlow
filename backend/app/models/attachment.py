from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AttachmentParentType


class Attachment(Base):
    """A file attached to a record. Who may open it is decided by the record it is attached to, never by the file."""

    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_parent", "parent_type", "parent_id"),
        CheckConstraint("size_bytes > 0", name="ck_attachments_size_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_type: Mapped[AttachmentParentType] = mapped_column(
        SAEnum(AttachmentParentType, name="attachment_parent_type"), nullable=False
    )
    parent_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # What the uploader called the file; shown to people and never used as a path.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
