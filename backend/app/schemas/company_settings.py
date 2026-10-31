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

from app.core.bank_validation import BIC_PATTERN, compact, is_valid_iban, is_valid_routing_number
from app.models.enums import InvoiceMatchMode

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


def _compact_identifier(value: object) -> object:
    return compact(value) if isinstance(value, str) else value


def _valid_iban(value: str) -> str:
    if not is_valid_iban(value):
        raise ValueError("The IBAN is not valid (check the digits)")
    return value


def _valid_routing_number(value: str) -> str:
    if not is_valid_routing_number(value):
        raise ValueError("The routing number is not a valid 9-digit ABA number")
    return value


BlankIsNone = BeforeValidator(_blank_to_none)
# Bank identifiers: spaces and dashes dropped, capitals, and checked so a typo is refused when it is typed.
PayerIban = Annotated[str, BeforeValidator(_compact_identifier), AfterValidator(_valid_iban)]
PayerBic = Annotated[str, BeforeValidator(_compact_identifier), StringConstraints(pattern=BIC_PATTERN.pattern)]
PayerRouting = Annotated[str, BeforeValidator(_compact_identifier), AfterValidator(_valid_routing_number)]
PayerAccount = Annotated[str, BeforeValidator(_compact_identifier), StringConstraints(pattern=r"^[A-Z0-9]{1,34}$")]
AchCompanyId = Annotated[str, BeforeValidator(_compact_identifier), StringConstraints(pattern=r"^[A-Z0-9]{1,10}$")]
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
        "invoice_matching",
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
    invoice_matching: InvoiceMatchMode | None = None
    budget_block_over_budget: bool | None = None
    budget_warn_percent: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    # The company's own bank account, used as the payer in payment files.
    payer_iban: Annotated[PayerIban | None, BlankIsNone] = None
    payer_bic: Annotated[PayerBic | None, BlankIsNone] = None
    payer_routing_number: Annotated[PayerRouting | None, BlankIsNone] = None
    payer_account_number: Annotated[PayerAccount | None, BlankIsNone] = None
    ach_company_id: Annotated[AchCompanyId | None, BlankIsNone] = None

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
    invoice_matching: InvoiceMatchMode
    budget_block_over_budget: bool
    budget_warn_percent: Decimal
    payer_iban: str | None
    payer_bic: str | None
    payer_routing_number: str | None
    payer_account_number: str | None
    ach_company_id: str | None
    updated_at: datetime
