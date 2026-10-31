from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupplierBankDetails(Base):
    """One version of a supplier's bank details, and the history of how they changed.

    A change is stored as a ``pending`` row and takes effect only when a different person approves it: the old
    ``current`` row becomes ``superseded`` and stays here. Partial unique indexes allow one current and one
    pending version per supplier.
    """

    __tablename__ = "supplier_bank_details"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'current', 'superseded', 'rejected')", name="ck_supplier_bank_details_status"
        ),
        Index(
            "uq_supplier_bank_details_current",
            "supplier_id",
            unique=True,
            postgresql_where=text("status = 'current'"),
        ),
        Index(
            "uq_supplier_bank_details_pending",
            "supplier_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    bank_account_name: Mapped[str | None] = mapped_column(String(140))
    iban: Mapped[str | None] = mapped_column(String(34))
    bic: Mapped[str | None] = mapped_column(String(11))
    bank_account_number: Mapped[str | None] = mapped_column(String(34))
    routing_number: Mapped[str | None] = mapped_column(String(9))
    bank_country: Mapped[str | None] = mapped_column(String(2))
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_comment: Mapped[str | None] = mapped_column(String(500))
    # When a newer version replaced this one.
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
