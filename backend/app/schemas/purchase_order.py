from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import POStatus
from app.schemas.supplier import SupplierRead
from app.schemas.user import UserRead


class POItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class POItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    received_quantity: int


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    expected_delivery_date: date | None = None
    notes: str | None = None
    items: list[POItemCreate] = Field(min_length=1)


class PurchaseOrderUpdate(BaseModel):
    expected_delivery_date: date | None = None
    notes: str | None = None
    items: list[POItemCreate] | None = None


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    supplier: SupplierRead
    status: POStatus
    expected_delivery_date: date | None
    notes: str | None
    items: list[POItemRead]
    creator: UserRead
    approver: UserRead | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    total: Decimal


class ReceiveItem(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class ReceivePurchaseOrderRequest(BaseModel):
    items: list[ReceiveItem] = Field(min_length=1)
