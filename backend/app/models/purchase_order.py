from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, Sequence, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import POStatus

if TYPE_CHECKING:
    from app.models.delivery import Delivery
    from app.models.purchase_order_item import PurchaseOrderItem
    from app.models.supplier import Supplier
    from app.models.user import User

# Shared by all years and never reset, so numbers stay unique even though they embed the creation year.
PO_NUMBER_SEQUENCE = Sequence("purchase_order_number_seq", metadata=Base.metadata)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    status: Mapped[POStatus] = mapped_column(
        SAEnum(POStatus, name="po_status"), nullable=False, default=POStatus.DRAFT, index=True
    )
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False, index=True)
    # Stored, not derived: each line is rounded once when priced, and these are the sums of those lines.
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    # Locked at approval (base units per one unit of the PO currency), so base-currency reports never move.
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    base_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    base_tax_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    base_grand_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    # Budget the order is charged to, and the request it was converted from, when there was one.
    cost_centre_id: Mapped[int | None] = mapped_column(ForeignKey("cost_centres.id"), index=True)
    purchase_request_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_requests.id"), index=True)
    # Counts amendments made after the order was placed; 1 is the order as first approved.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    # Set when the supplier confirmed the order in the portal.
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    delivery: Mapped["Delivery | None"] = relationship(
        back_populates="purchase_order", uselist=False, cascade="all, delete-orphan"
    )
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    approver: Mapped["User | None"] = relationship(foreign_keys=[approved_by])
    acknowledger: Mapped["User | None"] = relationship(foreign_keys=[acknowledged_by])

    @property
    def total(self) -> Decimal:
        """Kept for API compatibility: the amount payable in the PO currency."""
        return self.grand_total
