from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, Sequence, String, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PaymentMethod, PaymentRunStatus

if TYPE_CHECKING:
    from app.models.supplier_invoice import SupplierInvoice
    from app.models.user import User

# Shared by all years and never reset, like the purchase order numbers.
PAYMENT_RUN_NUMBER_SEQUENCE = Sequence("payment_run_number_seq", metadata=Base.metadata)


class PaymentRun(Base):
    """A batch of approved invoices paid together. One person creates it and a second person releases it."""

    __tablename__ = "payment_runs"
    __table_args__ = (CheckConstraint("total >= 0", name="ck_payment_runs_total_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    status: Mapped[PaymentRunStatus] = mapped_column(
        SAEnum(PaymentRunStatus, name="payment_run_status"),
        nullable=False,
        default=PaymentRunStatus.DRAFT,
        index=True,
    )
    method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name="payment_method"), nullable=False)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False, index=True)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    released_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["PaymentRunItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="PaymentRunItem.id"
    )
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    releaser: Mapped["User | None"] = relationship(foreign_keys=[released_by])


class PaymentRunItem(Base):
    __tablename__ = "payment_run_items"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_run_items_amount_positive"),
        UniqueConstraint("run_id", "invoice_id", name="uq_payment_run_items_run_id_invoice_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("payment_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("supplier_invoices.id"), nullable=False, index=True)
    # The invoice's open amount when the run was created; release refuses to pay if that has changed.
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    run: Mapped[PaymentRun] = relationship(back_populates="items")
    invoice: Mapped["SupplierInvoice"] = relationship()


class Payment(Base):
    """Money paid against one invoice, recorded by hand or by releasing a payment run."""

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payments_amount_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("supplier_invoices.id"), nullable=False, index=True)
    payment_run_id: Mapped[int | None] = mapped_column(ForeignKey("payment_runs.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False, index=True)
    method: Mapped[PaymentMethod] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method", create_type=False), nullable=False
    )
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
