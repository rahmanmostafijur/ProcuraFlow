from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Money
from app.schemas.currency import CurrencyCodeStr

ContractPrice = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
LeadTime = Annotated[int, Field(ge=0, le=3650)]


class CatalogItemCreate(BaseModel):
    product_id: int
    supplier_id: int
    contract_price: ContractPrice
    # Left out: the supplier's default currency, else the company's base currency.
    currency_code: CurrencyCodeStr | None = None
    lead_time_days: LeadTime = 0
    valid_from: date | None = None
    valid_until: date | None = None

    @model_validator(mode="after")
    def _dates_in_order(self) -> "CatalogItemCreate":
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("The contract cannot end before it starts")
        return self


class CatalogItemUpdate(BaseModel):
    contract_price: ContractPrice | None = None
    lead_time_days: LeadTime | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    is_active: bool | None = None


class CatalogItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_sku: str
    product_name: str
    supplier_id: int
    supplier_name: str
    contract_price: Money
    currency_code: str
    lead_time_days: int
    valid_from: date | None
    valid_until: date | None
    is_active: bool
    # Worked out from today's date in the company time zone when asked for, never stored.
    is_current: bool
    created_at: datetime
