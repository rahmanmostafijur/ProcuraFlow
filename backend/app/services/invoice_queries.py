"""Reading invoices: loading one (optionally locked), and the filters the list and the metrics share."""

from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.models.enums import InvoiceStatus
from app.models.supplier_invoice import SupplierInvoice

INVOICE_LOAD = (
    selectinload(SupplierInvoice.supplier),
    selectinload(SupplierInvoice.purchase_order),
    selectinload(SupplierInvoice.creator),
    selectinload(SupplierInvoice.approver),
    selectinload(SupplierInvoice.lines),
)


@dataclass(frozen=True)
class InvoiceFilter:
    """What the invoice list narrows to. The dashboard figures take the same filter, so they always agree."""

    status: InvoiceStatus | None = None
    supplier_id: int | None = None
    po_id: int | None = None
    # Invoices whose due date is strictly before this day.
    due_before: date | None = None
    # Part of the supplier's invoice number, any case.
    search: str | None = None

    def conditions(self) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if self.status is not None:
            conditions.append(SupplierInvoice.status == self.status)
        if self.supplier_id is not None:
            conditions.append(SupplierInvoice.supplier_id == self.supplier_id)
        if self.po_id is not None:
            conditions.append(SupplierInvoice.po_id == self.po_id)
        if self.due_before is not None:
            conditions.append(SupplierInvoice.due_date < self.due_before)
        if self.search:
            escaped = self.search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(SupplierInvoice.invoice_number.ilike(f"%{escaped}%", escape="\\"))
        return conditions


def list_statement(flt: InvoiceFilter) -> Select[tuple[SupplierInvoice]]:
    stmt = select(SupplierInvoice).options(*INVOICE_LOAD).order_by(SupplierInvoice.id.desc())
    for condition in flt.conditions():
        stmt = stmt.where(condition)
    return stmt


async def get_invoice(db: AsyncSession, invoice_id: int, *, for_update: bool = False) -> SupplierInvoice:
    """The invoice, or a 404. Locking it makes the caller the only one changing it until commit."""
    stmt = select(SupplierInvoice).options(*INVOICE_LOAD).where(SupplierInvoice.id == invoice_id)
    if for_update:
        stmt = stmt.with_for_update(of=SupplierInvoice)
    invoice = await db.scalar(stmt.execution_options(populate_existing=True))
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice
