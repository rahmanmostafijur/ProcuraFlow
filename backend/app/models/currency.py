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
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Currency(Base):
    __tablename__ = "currencies"
    __table_args__ = (CheckConstraint("minor_units BETWEEN 0 AND 4", name="ck_currencies_minor_units"),)

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    minor_units: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ExchangeRate(Base):
    """A manually entered rate: one unit of ``currency_code`` is worth ``rate`` units of the base currency.

    Rates are kept per base currency, so a later change of base currency never reinterprets old rates.
    The rate in force on a day is the latest one whose effective date is on or before that day.
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint(
            "base_currency_code", "currency_code", "effective_date", name="uq_exchange_rates_pair_effective_date"
        ),
        CheckConstraint("rate > 0", name="ck_exchange_rates_rate_positive"),
        CheckConstraint("base_currency_code <> currency_code", name="ck_exchange_rates_distinct_currencies"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base_currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
