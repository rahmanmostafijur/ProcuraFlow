from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AmendmentStatus


class PurchaseOrderVersion(Base):
    """One version of a purchase order after it was ordered: a full snapshot plus a readable diff from the last.

    Version 1 is the order as first approved. An amendment that raises the total is stored as
    ``pending_approval`` and only changes the order once it is approved.
    """

    __tablename__ = "purchase_order_versions"
    __table_args__ = (UniqueConstraint("po_id", "version", name="uq_purchase_order_versions_po_id_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AmendmentStatus] = mapped_column(
        SAEnum(AmendmentStatus, name="amendment_status"), nullable=False, default=AmendmentStatus.APPLIED
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
