from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints


def _upper(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


CurrencyCodeStr = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z]{3}$")]


class CurrencyCreate(BaseModel):
    code: CurrencyCodeStr
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    symbol: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8)]
    # Fixed once chosen: changing it later would change how existing orders round.
    minor_units: int = Field(ge=0, le=4)
    is_active: bool = True


class CurrencyUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    symbol: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8)] | None = None
    is_active: bool | None = None


class CurrencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    symbol: str
    minor_units: int
    is_active: bool


class ExchangeRateCreate(BaseModel):
    currency_code: CurrencyCodeStr
    # Units of the base currency per one unit of `currency_code`.
    rate: Decimal = Field(gt=0, lt=Decimal("1000000000"), max_digits=18, decimal_places=8)
    effective_date: date


class ExchangeRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    base_currency_code: str
    currency_code: str
    rate: Decimal
    effective_date: date
    created_at: datetime
