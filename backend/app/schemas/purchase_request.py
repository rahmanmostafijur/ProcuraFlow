from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import PurchaseRequestStatus
from app.schemas.common import Money
from app.schemas.currency import CurrencyCodeStr
from app.schemas.person import PersonRead

UnitPrice = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
MAX_LINES = 100


class RequestLineWrite(BaseModel):
    description: Description
    quantity: int = Field(gt=0, le=1_000_000)
    unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)] = "unit"
    # Left out when a catalog item is chosen: the contract price is used.
    estimated_unit_price: UnitPrice | None = None
    catalog_item_id: int | None = None
    product_id: int | None = None
    supplier_id: int | None = None


class PurchaseRequestCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    notes: str | None = Field(default=None, max_length=5000)
    cost_centre_id: int | None = None
    # Left out: the company's base currency.
    currency_code: CurrencyCodeStr | None = None
    needed_by: date | None = None
    lines: list[RequestLineWrite] = Field(min_length=1, max_length=MAX_LINES)


class PurchaseRequestUpdate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    notes: str | None = Field(default=None, max_length=5000)
    cost_centre_id: int | None = None
    currency_code: CurrencyCodeStr | None = None
    needed_by: date | None = None
    # When sent, replaces all lines.
    lines: list[RequestLineWrite] | None = Field(default=None, min_length=1, max_length=MAX_LINES)


class RequestLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    catalog_item_id: int | None
    product_id: int | None
    supplier_id: int | None
    quantity: int
    unit: str
    estimated_unit_price: Money
    line_total: Money
    converted_po_id: int | None


class PurchaseRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_number: str
    requester: PersonRead
    title: str
    notes: str | None
    cost_centre_id: int | None
    currency_code: str
    needed_by: date | None
    status: PurchaseRequestStatus
    estimated_total: Money
    base_estimated_total: Money | None
    submitted_at: datetime | None
    decided_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[RequestLineRead]


class ConvertLine(BaseModel):
    line_id: int
    # Needed for a free-text line, which has no product yet.
    product_id: int | None = None
    # Left out: the line's estimated price.
    unit_price: UnitPrice | None = None


class ConvertOrder(BaseModel):
    supplier_id: int
    lines: list[ConvertLine] = Field(min_length=1)
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ConvertRequest(BaseModel):
    orders: list[ConvertOrder] = Field(min_length=1, max_length=20)


class ConvertResult(BaseModel):
    purchase_order_ids: list[int]
    request: PurchaseRequestRead
