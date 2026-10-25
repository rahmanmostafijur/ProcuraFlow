from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TaxType


class TaxRate(Base):
    """A tax rate that can be chosen per purchase-order line.

    Lines copy the name, percentage and flags when they are priced, so editing or retiring a rate never
    changes an existing order. Reverse charge means the supplier charges no tax and the buyer accounts
    for it, so such a rate is always 0%.
    """

    __tablename__ = "tax_rates"
    __table_args__ = (
        CheckConstraint("percentage >= 0 AND percentage <= 100", name="ck_tax_rates_percentage_range"),
        CheckConstraint("NOT is_reverse_charge OR percentage = 0", name="ck_tax_rates_reverse_charge_is_zero"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    tax_type: Mapped[TaxType] = mapped_column(SAEnum(TaxType, name="tax_type"), nullable=False)
    is_inclusive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_reverse_charge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    region: Mapped[str | None] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
