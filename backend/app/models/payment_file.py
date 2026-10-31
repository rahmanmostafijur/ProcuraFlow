from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentRunFile(Base):
    """The bank file generated from a released payment run. One per run: later downloads return the same bytes."""

    __tablename__ = "payment_run_files"
    __table_args__ = (
        CheckConstraint("file_format IN ('sepa_pain001', 'nacha_ach')", name="ck_payment_run_files_format"),
        CheckConstraint("size_bytes > 0", name="ck_payment_run_files_size_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Unique: the database, not only the service, guarantees a run is exported once.
    run_id: Mapped[int] = mapped_column(ForeignKey("payment_runs.id"), unique=True, nullable=False)
    file_format: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
