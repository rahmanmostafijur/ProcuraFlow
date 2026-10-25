from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, Sequence, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PurchaseRequestStatus

if TYPE_CHECKING:
    from app.models.user import User

# Shared by all years and never reset, like the purchase order numbers.
REQUEST_NUMBER_SEQUENCE = Sequence("purchase_request_number_seq", metadata=Base.metadata)


class PurchaseRequest(Base):
    """An employee's request to buy something. Once approved it is turned into purchase orders."""

    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    cost_centre_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centres.id"), index=True)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False, index=True)
    needed_by: Mapped[date | None] = mapped_column(Date)
    status: Mapped[PurchaseRequestStatus] = mapped_column(
        SAEnum(PurchaseRequestStatus, name="purchase_request_status"),
        nullable=False,
        default=PurchaseRequestStatus.DRAFT,
        index=True,
    )
    # Sum of the rounded line estimates, in the request currency; the base amount is fixed when it is submitted.
    estimated_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    base_estimated_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    requester: Mapped["User"] = relationship(foreign_keys=[requester_id])
    lines: Mapped[list["PurchaseRequestLine"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="PurchaseRequestLine.id"
    )


class PurchaseRequestLine(Base):
    __tablename__ = "purchase_request_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_request_lines_quantity_positive"),
        CheckConstraint("estimated_unit_price >= 0", name="ck_purchase_request_lines_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    catalog_item_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_items.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="unit")
    estimated_unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    # Set when the line has been turned into a purchase order, so it cannot be ordered twice.
    converted_po_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), index=True)

    request: Mapped[PurchaseRequest] = relationship(back_populates="lines")
