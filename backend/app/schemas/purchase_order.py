from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError

from app.models.enums import POStatus, ReceiptCondition
from app.schemas.common import Money
from app.schemas.currency import CurrencyCodeStr
from app.schemas.supplier import SupplierRead
from app.schemas.user import UserRead


class POItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    tax_rate_id: int | None = None


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
    unit_price: Money
    received_quantity: int
    tax_rate_id: int | None
    tax_name: str | None
    tax_percent: Decimal
    tax_inclusive: bool
    reverse_charge: bool
    line_net: Money
    line_tax: Money
    line_total: Money


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    # Omitted: the supplier's default currency, else the company's base currency.
    currency_code: CurrencyCodeStr | None = None
    # The budget the order is charged to; optional.
    cost_centre_id: int | None = None
    expected_delivery_date: date | None = None
    notes: str | None = None
    items: POItemList = Field(min_length=1)


class PurchaseOrderUpdate(BaseModel):
    currency_code: CurrencyCodeStr | None = None
    cost_centre_id: int | None = None
    expected_delivery_date: date | None = None
    notes: str | None = None
    items: POItemList | None = None


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    supplier: SupplierRead
    status: POStatus
    currency_code: str
    cost_centre_id: int | None
    purchase_request_id: int | None
    # How many times the order has been amended; 1 is the order as first approved.
    version: int
    expected_delivery_date: date | None
    notes: str | None
    items: list[POItemRead]
    creator: UserRead
    approver: UserRead | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    subtotal: Money
    tax_total: Money
    grand_total: Money
    # Locked at approval; null while the order is still a draft or awaiting approval.
    exchange_rate: Decimal | None
    base_subtotal: Money | None
    base_tax_total: Money | None
    base_grand_total: Money | None
    total: Money


class ReceiveItem(BaseModel):
    product_id: int
    # Units that arrived. Only the accepted ones (quantity - rejected_quantity) enter stock.
    quantity: int = Field(gt=0)
    rejected_quantity: int = Field(default=0, ge=0)
    condition: ReceiptCondition = ReceiptCondition.GOOD
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None

    @model_validator(mode="after")
    def _rejected_is_part_of_what_arrived(self) -> "ReceiveItem":
        if self.rejected_quantity > self.quantity:
            raise ValueError("The rejected quantity cannot be more than the quantity that arrived")
        return self


def reject_duplicate_receipt_products(items: list[ReceiveItem]) -> list[ReceiveItem]:
    seen: set[int] = set()
    for item in items:
        if item.product_id in seen:
            raise PydanticCustomError(
                "duplicate_product",
                "Product {product_id} is repeated; send one line per product.",
                {"product_id": item.product_id},
            )
        seen.add(item.product_id)
    return items


class ReceivePurchaseOrderRequest(BaseModel):
    items: Annotated[list[ReceiveItem], AfterValidator(reject_duplicate_receipt_products)] = Field(min_length=1)
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None
