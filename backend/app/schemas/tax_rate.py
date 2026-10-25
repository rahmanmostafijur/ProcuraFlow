from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import TaxType

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Percentage = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        return value.strip().upper() or None
    return value


Region = Annotated[str | None, BeforeValidator(_blank_to_none), Field(max_length=10)]


class TaxRateCreate(BaseModel):
    name: Name
    percentage: Percentage
    tax_type: TaxType
    is_inclusive: bool = False
    is_reverse_charge: bool = False
    region: Region = None
    is_active: bool = True

    @model_validator(mode="after")
    def _reverse_charge_is_zero(self) -> "TaxRateCreate":
        if self.is_reverse_charge and self.percentage != 0:
            raise ValueError("A reverse-charge rate must be 0%: the supplier charges no tax")
        return self


class TaxRateUpdate(BaseModel):
    name: Name | None = None
    percentage: Percentage | None = None
    tax_type: TaxType | None = None
    is_inclusive: bool | None = None
    is_reverse_charge: bool | None = None
    region: Region = None
    is_active: bool | None = None


class TaxRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    percentage: Decimal
    tax_type: TaxType
    is_inclusive: bool
    is_reverse_charge: bool
    region: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
