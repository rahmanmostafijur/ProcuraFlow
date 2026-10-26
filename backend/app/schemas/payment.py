from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import PaymentMethod, PaymentRunStatus
from app.schemas.common import Money
from app.schemas.person import PersonRead

Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    method: PaymentMethod
    # Omitted: today in the company time zone. Cannot be in the future.
    paid_on: date | None = None
    reference: Reference | None = None


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    payment_run_id: int | None
    amount: Money
    currency_code: str
    method: PaymentMethod
    paid_on: date
    reference: str | None
    created_by: int
    creator: PersonRead
    created_at: datetime


class PaymentRunCreate(BaseModel):
    invoice_ids: list[int] = Field(min_length=1, max_length=500)
    method: PaymentMethod = PaymentMethod.BANK_TRANSFER


class PaymentRunItemRead(BaseModel):
    id: int
    invoice_id: int
    invoice_number: str
    supplier_id: int
    supplier_name: str
    amount: Money


class PaymentRunRead(BaseModel):
    id: int
    number: str
    status: PaymentRunStatus
    method: PaymentMethod
    currency_code: str
    total: Money
    created_by: int
    creator: PersonRead
    released_by: int | None
    releaser: PersonRead | None
    released_at: datetime | None
    created_at: datetime
    items: list[PaymentRunItemRead]
