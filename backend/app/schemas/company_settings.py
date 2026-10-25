from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import available_timezones

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

DateFormat = Literal["YYYY-MM-DD", "MM/DD/YYYY", "DD/MM/YYYY", "DD.MM.YYYY"]


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _known_timezone(value: str) -> str:
    if value not in available_timezones():
        raise ValueError(f"Unknown time zone '{value}'; use an IANA name such as 'Europe/Berlin'")
    return value


def _upper(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


BlankIsNone = BeforeValidator(_blank_to_none)
Text200 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Text100 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Text50 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
Text20 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]
CountryCode = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z]{2}$")]
CurrencyCode = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z]{3}$")]
BrandColor = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^#[0-9A-F]{6}$")]
PONumberPrefix = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z0-9]{1,10}$")]
TimeZoneName = Annotated[str, AfterValidator(_known_timezone)]

# Settings that always have a value: a PATCH may change them but not set them to null.
REQUIRED_FIELDS = frozenset(
    {
        "company_name",
        "brand_color",
        "base_currency_code",
        "fiscal_year_start_month",
        "date_format",
        "timezone",
        "po_number_prefix",
        "invoice_tolerance_percent",
        "default_payment_terms_days",
        "budget_block_over_budget",
        "budget_warn_percent",
    }
)


class CompanySettingsUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""

    company_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    legal_name: Annotated[Text200 | None, BlankIsNone] = None
    address_line1: Annotated[Text200 | None, BlankIsNone] = None
    address_line2: Annotated[Text200 | None, BlankIsNone] = None
    city: Annotated[Text100 | None, BlankIsNone] = None
    region: Annotated[Text100 | None, BlankIsNone] = None
    postal_code: Annotated[Text20 | None, BlankIsNone] = None
    country_code: Annotated[CountryCode | None, BlankIsNone] = None
    tax_id: Annotated[Text50 | None, BlankIsNone] = None
    contact_email: Annotated[EmailStr | None, BlankIsNone] = None
    contact_phone: Annotated[Text50 | None, BlankIsNone] = None
    brand_color: BrandColor | None = None
    base_currency_code: CurrencyCode | None = None
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    date_format: DateFormat | None = None
    timezone: TimeZoneName | None = None
    po_number_prefix: PONumberPrefix | None = None
    invoice_tolerance_percent: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    default_payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    budget_block_over_budget: bool | None = None
    budget_warn_percent: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)

    @model_validator(mode="after")
    def _required_fields_are_not_cleared(self) -> "CompanySettingsUpdate":
        cleared = sorted(name for name in self.model_fields_set & REQUIRED_FIELDS if getattr(self, name) is None)
        if cleared:
            raise ValueError(f"These settings cannot be empty: {', '.join(cleared)}")
        return self


class BrandingRead(BaseModel):
    """The public subset shown before sign-in."""

    company_name: str
    brand_color: str
    logo_url: str | None


class CompanySettingsRead(BrandingRead):
    model_config = ConfigDict(from_attributes=True)

    legal_name: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    country_code: str | None
    tax_id: str | None
    contact_email: str | None
    contact_phone: str | None
    base_currency_code: str
    fiscal_year_start_month: int
    date_format: DateFormat
    timezone: str
    po_number_prefix: str
    invoice_tolerance_percent: Decimal
    default_payment_terms_days: int
    budget_block_over_budget: bool
    budget_warn_percent: Decimal
    updated_at: datetime
