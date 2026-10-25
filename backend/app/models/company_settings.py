from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

# The single settings row. Everything branded (header, sign-in page, PDFs, emails) reads from it.
COMPANY_SETTINGS_ID = 1


class CompanySettings(Base):
    __tablename__ = "company_settings"
    __table_args__ = (
        CheckConstraint(f"id = {COMPANY_SETTINGS_ID}", name="ck_company_settings_singleton"),
        CheckConstraint("fiscal_year_start_month BETWEEN 1 AND 12", name="ck_company_settings_fiscal_month"),
        CheckConstraint(
            "invoice_tolerance_percent >= 0 AND invoice_tolerance_percent <= 100",
            name="ck_company_settings_tolerance_range",
        ),
        CheckConstraint("default_payment_terms_days >= 0", name="ck_company_settings_payment_terms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=COMPANY_SETTINGS_ID)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country_code: Mapped[str | None] = mapped_column(String(2))
    tax_id: Mapped[str | None] = mapped_column(String(50))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(50))

    logo_storage_key: Mapped[str | None] = mapped_column(String(255))
    logo_content_type: Mapped[str | None] = mapped_column(String(50))
    logo_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    brand_color: Mapped[str] = mapped_column(String(7), nullable=False)

    base_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    fiscal_year_start_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    date_format: Mapped[str] = mapped_column(String(10), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    po_number_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    invoice_tolerance_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    default_payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False)

    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    updater: Mapped["User | None"] = relationship()
