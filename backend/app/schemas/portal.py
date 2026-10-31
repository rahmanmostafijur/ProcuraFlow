"""What the supplier portal shows and accepts. Deliberately smaller than the internal schemas: no internal notes,
people, exchange rates, approval or matching details."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models.enums import InvoiceStatus, POStatus
from app.schemas.common import Money

InvoiceNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class PortalSupplier(BaseModel):
    id: int
    name: str


class PortalMe(BaseModel):
    id: int
    email: str
    full_name: str
    supplier: PortalSupplier


class PortalOrderLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    sku: str
    quantity: int
    received_quantity: int
    unit_price: Money
    tax_name: str | None
    tax_percent: Decimal
    line_net: Money
    line_tax: Money
    line_total: Money


class PortalOrderSummary(BaseModel):
    id: int
    po_number: str
    status: POStatus
    currency_code: str
    subtotal: Money
    tax_total: Money
    grand_total: Money
    expected_delivery_date: date | None
    # Counts amendments; a changed order has a higher version than the one acknowledged.
    version: int
    created_at: datetime
    acknowledged_at: datetime | None


class PortalOrderRead(PortalOrderSummary):
    items: list[PortalOrderLine]


class PortalInvoiceLine(BaseModel):
    # The ordered product this line bills. A line for something that is not on the order is flagged for review.
    product_id: int | None = None
    # Omitted: the product's name.
    description: Description | None = None
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=4)


class PortalInvoiceCreate(BaseModel):
    po_id: int
    invoice_number: InvoiceNumber
    invoice_date: date
    # Omitted: invoice date plus the payment terms agreed with the supplier.
    due_date: date | None = None
    notes: Notes | None = None
    lines: list[PortalInvoiceLine] = Field(min_length=1)


class PortalInvoiceRead(BaseModel):
    id: int
    invoice_number: str
    po_id: int
    po_number: str
    invoice_date: date
    due_date: date
    currency_code: str
    subtotal: Money
    tax_total: Money
    grand_total: Money
    paid_total: Money
    open_amount: Money
    status: InvoiceStatus
    created_at: datetime


class PortalInvite(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)


class PortalAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
