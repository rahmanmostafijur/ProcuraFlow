from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, StringConstraints

from app.schemas.currency import CurrencyCodeStr


def _upper(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


CountryCodeStr = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z]{2}$")]
TaxIdStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class SupplierBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    country_code: CountryCodeStr | None = None
    tax_id: TaxIdStr | None = None
    currency_code: CurrencyCodeStr | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    country_code: CountryCodeStr | None = None
    tax_id: TaxIdStr | None = None
    currency_code: CurrencyCodeStr | None = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    is_active: bool | None = None


class SupplierRead(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
