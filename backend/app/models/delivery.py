from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DeliveryStatus

if TYPE_CHECKING:
    from app.models.purchase_order import PurchaseOrder


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    expected_date: Mapped[date | None] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"), nullable=False, default=DeliveryStatus.PENDING
    )
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="delivery")
