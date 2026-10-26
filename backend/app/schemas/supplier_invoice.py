from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import InvoiceMatchMode, InvoiceStatus, MatchReasonCode
from app.schemas.common import Money, PaginatedResponse
from app.schemas.currency import CurrencyCodeStr
from app.schemas.person import PersonRead

InvoiceNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class InvoiceLineWrite(BaseModel):
    # The order line this bills, by product. A line with no product, or a product that is not on the order, is
    # recorded but flagged as an unknown line when the invoice is matched.
    product_id: int | None = None
    # Omitted: the product's name.
    description: Description | None = None
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    # Omitted: the tax of the matching order line. Sent as null: no tax.
    tax_rate_id: int | None = None


class InvoiceCreate(BaseModel):
    po_id: int
    # Optional: the order's supplier is used. Sent, it must be that supplier.
    supplier_id: int | None = None
    invoice_number: InvoiceNumber
    invoice_date: date
    # Omitted: invoice date + the supplier's payment terms, else the company default terms.
    due_date: date | None = None
    # Optional: must equal the order's currency.
    currency_code: CurrencyCodeStr | None = None
    notes: Notes | None = None
    lines: list[InvoiceLineWrite] = Field(min_length=1)


class InvoiceUpdate(BaseModel):
    invoice_number: InvoiceNumber | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    notes: Notes | None = None
    # When sent, replaces all lines.
    lines: list[InvoiceLineWrite] | None = Field(default=None, min_length=1)


class InvoiceReasonBody(BaseModel):
    reason: Reason


class InvoiceDecision(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class InvoiceRejection(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ExceptionReason(BaseModel):
    code: MatchReasonCode
    message: str
    # 1-based position of the invoice line the reason is about, when it is about one.
    line: int | None = None
    # The other invoice, for a duplicate.
    duplicate_of: int | None = None


class SupplierRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class PurchaseOrderRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_item_id: int | None
    product_id: int | None
    description: str
    quantity: int
    unit_price: Money
    tax_rate_id: int | None
    tax_name: str | None
    tax_percent: Decimal
    tax_inclusive: bool
    reverse_charge: bool
    line_net: Money
    line_tax: Money
    line_total: Money


class InvoiceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier: SupplierRef
    purchase_order: PurchaseOrderRef
    invoice_number: str
    invoice_date: date
    due_date: date
    currency_code: str
    subtotal: Money
    tax_total: Money
    grand_total: Money
    paid_total: Money
    open_amount: Money
    status: InvoiceStatus
    match_mode: InvoiceMatchMode | None
    tolerance_percent: Decimal | None
    exception_reasons: list[ExceptionReason]
    notes: str | None
    created_by: int
    creator: PersonRead
    submitted_at: datetime | None
    approved_by: int | None
    approver: PersonRead | None
    approved_at: datetime | None
    hold_reason: str | None
    void_reason: str | None
    rejection_reason: str | None
    # Locked at approval; null before.
    exchange_rate: Decimal | None
    base_subtotal: Money | None
    base_tax_total: Money | None
    base_grand_total: Money | None
    created_at: datetime
    updated_at: datetime


class InvoiceRead(InvoiceSummary):
    lines: list[InvoiceLineRead]


class InvoiceListTotals(BaseModel):
    """Figures for everything the list's filters match (not just the current page), from the same metric functions
    the dashboard uses."""

    by_status: dict[InvoiceStatus, int]
    needing_attention: int
    payables_outstanding: Money
    payables_overdue: Money


class InvoiceListResponse(PaginatedResponse[InvoiceSummary]):
    totals: InvoiceListTotals
