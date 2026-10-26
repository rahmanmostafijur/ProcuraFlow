from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ReceiptCondition, ReturnResolution, ReturnStatus

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.purchase_order import PurchaseOrder
    from app.models.user import User


class GoodsReceipt(Base):
    """One delivery booked against a purchase order: what arrived, what was accepted into stock and what was not."""

    __tablename__ = "goods_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    received_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    note: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["GoodsReceiptLine"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan", order_by="GoodsReceiptLine.id"
    )
    receiver: Mapped["User"] = relationship(foreign_keys=[received_by])


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    __table_args__ = (
        CheckConstraint("delivered_quantity > 0", name="ck_goods_receipt_lines_delivered_positive"),
        CheckConstraint("accepted_quantity >= 0", name="ck_goods_receipt_lines_accepted_non_negative"),
        CheckConstraint("rejected_quantity >= 0", name="ck_goods_receipt_lines_rejected_non_negative"),
        CheckConstraint(
            "accepted_quantity + rejected_quantity = delivered_quantity", name="ck_goods_receipt_lines_adds_up"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(
        ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    delivered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    condition: Mapped[ReceiptCondition] = mapped_column(
        SAEnum(ReceiptCondition, name="goods_receipt_condition"), nullable=False, default=ReceiptCondition.GOOD
    )
    note: Mapped[str | None] = mapped_column(String(500))

    receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()


class SupplierReturn(Base):
    """Rejected goods sent back to the supplier, with what the supplier owes in exchange."""

    __tablename__ = "supplier_returns"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_supplier_returns_quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    resolution: Mapped[ReturnResolution] = mapped_column(
        SAEnum(ReturnResolution, name="return_resolution"), nullable=False
    )
    status: Mapped[ReturnStatus] = mapped_column(
        SAEnum(ReturnStatus, name="return_status"), nullable=False, default=ReturnStatus.OPEN, index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship()
    product: Mapped["Product"] = relationship()
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
