from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.product import Product
from app.models.supplier import Supplier


class CatalogItem(Base):
    """A product a supplier has agreed to sell at a contract price, so requests can start from a known price."""

    __tablename__ = "catalog_items"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "supplier_id", "currency_code", name="uq_catalog_items_product_supplier_currency"
        ),
        CheckConstraint("contract_price >= 0", name="ck_catalog_items_price_non_negative"),
        CheckConstraint("lead_time_days >= 0", name="ck_catalog_items_lead_time_non_negative"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_catalog_items_dates"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    contract_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False, index=True)
    lead_time_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped[Product] = relationship()
    supplier: Mapped[Supplier] = relationship()
