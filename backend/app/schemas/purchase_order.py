from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from pydantic_core import PydanticCustomError

from app.models.enums import POStatus
from app.schemas.supplier import SupplierRead
from app.schemas.user import UserRead


class POItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


def reject_duplicate_products(items: list[POItemCreate]) -> list[POItemCreate]:
    seen: set[int] = set()
    for item in items:
        if item.product_id in seen:
            raise PydanticCustomError(
                "duplicate_product",
                "Each product can appear only once per purchase order (product {product_id} is repeated). "
                "Combine the quantities into one line.",
                {"product_id": item.product_id},
            )
        seen.add(item.product_id)
    return items


POItemList = Annotated[list[POItemCreate], AfterValidator(reject_duplicate_products)]


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
    items: POItemList = Field(min_length=1)


class PurchaseOrderUpdate(BaseModel):
    expected_delivery_date: date | None = None
    notes: str | None = None
    items: POItemList | None = None


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
