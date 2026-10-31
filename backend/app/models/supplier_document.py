from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupplierDocument(Base):
    """A compliance document of a supplier (W-9, VAT certificate, insurance, ISO, bank letter) and its file.

    There is deliberately no status column: valid / expiring soon / expired depend on today's date, so they are
    worked out when the document is read (see supplier_document_service.document_status).
    """

    __tablename__ = "supplier_documents"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_supplier_documents_size_positive"),
        CheckConstraint(
            "issue_date IS NULL OR expiry_date IS NULL OR expiry_date >= issue_date",
            name="ck_supplier_documents_dates_in_order",
        ),
        CheckConstraint(
            "document_type IN ('w9', 'vat_certificate', 'insurance', 'iso_certificate', 'bank_letter')",
            name="ck_supplier_documents_type",
        ),
        Index("ix_supplier_documents_expiry_date", "expiry_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
