from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import InvoiceMatchMode, InvoiceStatus

if TYPE_CHECKING:
    from app.models.purchase_order import PurchaseOrder
    from app.models.supplier import Supplier
    from app.models.user import User


class SupplierInvoice(Base):
    """A bill from a supplier, recorded against one purchase order and matched to it before it can be paid."""

    __tablename__ = "supplier_invoices"
    __table_args__ = (
        CheckConstraint("paid_total >= 0", name="ck_supplier_invoices_paid_non_negative"),
        CheckConstraint("paid_total <= grand_total", name="ck_supplier_invoices_paid_within_total"),
        CheckConstraint("grand_total >= 0", name="ck_supplier_invoices_total_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    paid_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"), nullable=False, default=InvoiceStatus.DRAFT, index=True
    )
    # What the last match used: the mode and tolerance in force at submission, kept so the result stays explainable.
    match_mode: Mapped[InvoiceMatchMode | None] = mapped_column(SAEnum(InvoiceMatchMode, name="invoice_match_mode"))
    tolerance_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    exception_reasons: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hold_reason: Mapped[str | None] = mapped_column(String(500))
    # Where release returns the invoice to.
    status_before_hold: Mapped[InvoiceStatus | None] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status", create_type=False)
    )
    void_reason: Mapped[str | None] = mapped_column(String(500))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    # Locked at approval (base units per one unit of the invoice currency), like purchase orders.
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    base_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    base_tax_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    base_grand_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    supplier: Mapped["Supplier"] = relationship()
    purchase_order: Mapped["PurchaseOrder"] = relationship()
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    approver: Mapped["User | None"] = relationship(foreign_keys=[approved_by])
    lines: Mapped[list["SupplierInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="SupplierInvoiceLine.id"
    )

    @property
    def open_amount(self) -> Decimal:
        """What is still unpaid, in the invoice currency."""
        return self.grand_total - self.paid_total


class SupplierInvoiceLine(Base):
    __tablename__ = "supplier_invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_supplier_invoice_lines_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_supplier_invoice_lines_unit_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The order line this bills. Orders replace their lines when amended, so matching goes by product.
    po_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_order_items.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    tax_rate_id: Mapped[int | None] = mapped_column(ForeignKey("tax_rates.id"), index=True)
    tax_name: Mapped[str | None] = mapped_column(String(100))
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reverse_charge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    line_net: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)

    invoice: Mapped[SupplierInvoice] = relationship(back_populates="lines")
