from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_po_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_po_items_unit_price_non_negative"),
        CheckConstraint("received_quantity >= 0", name="ck_po_items_received_quantity_non_negative"),
        # Receiving matches lines by product, so a repeated product would make receipts ambiguous.
        UniqueConstraint("po_id", "product_id", name="uq_purchase_order_items_po_id_product_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The tax chosen for the line, copied when the line is priced so later edits to the rate change nothing here.
    tax_rate_id: Mapped[int | None] = mapped_column(ForeignKey("tax_rates.id"), index=True)
    tax_name: Mapped[str | None] = mapped_column(String(100))
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False, default=0)
    tax_inclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reverse_charge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    line_net: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
