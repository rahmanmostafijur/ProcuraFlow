"""Plain CSV exports of purchase orders, supplier invoices and suppliers, for spreadsheets and other tools."""

from collections.abc import AsyncIterator, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import InvoiceStatus, POStatus
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.services.export_common import (
    Dataset,
    ExportFilters,
    day_after,
    day_start,
    keyset_pages,
    minor_units_by_currency,
)
from app.services.export_writer import Cell, Fixed

ACTIVE = "active"
INACTIVE = "inactive"


async def purchase_order_rows(db: AsyncSession, filters: ExportFilters) -> AsyncIterator[Sequence[Cell]]:
    stmt = select(PurchaseOrder).options(selectinload(PurchaseOrder.supplier))
    if filters.status:
        stmt = stmt.where(PurchaseOrder.status == POStatus(filters.status))
    if filters.date_from:
        stmt = stmt.where(PurchaseOrder.created_at >= day_start(filters.date_from))
    if filters.date_to:
        stmt = stmt.where(PurchaseOrder.created_at < day_after(filters.date_to))
    minor_units = await minor_units_by_currency(db)
    async for page in keyset_pages(db, stmt, PurchaseOrder.id):
        for po in page:
            places = minor_units[po.currency_code]
            yield [
                po.po_number,
                po.supplier.name,
                po.status.value,
                po.currency_code,
                Fixed(po.subtotal, places),
                Fixed(po.tax_total, places),
                Fixed(po.grand_total, places),
                po.expected_delivery_date,
                po.created_at.date(),
                po.approved_at.date() if po.approved_at else None,
            ]


async def invoice_rows(db: AsyncSession, filters: ExportFilters) -> AsyncIterator[Sequence[Cell]]:
    stmt = select(SupplierInvoice).options(
        selectinload(SupplierInvoice.supplier), selectinload(SupplierInvoice.purchase_order)
    )
    if filters.status:
        stmt = stmt.where(SupplierInvoice.status == InvoiceStatus(filters.status))
    if filters.date_from:
        stmt = stmt.where(SupplierInvoice.invoice_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(SupplierInvoice.invoice_date <= filters.date_to)
    minor_units = await minor_units_by_currency(db)
    async for page in keyset_pages(db, stmt, SupplierInvoice.id):
        for invoice in page:
            places = minor_units[invoice.currency_code]
            yield [
                invoice.invoice_number,
                invoice.supplier.name,
                invoice.purchase_order.po_number,
                invoice.invoice_date,
                invoice.due_date,
                invoice.status.value,
                invoice.currency_code,
                Fixed(invoice.subtotal, places),
                Fixed(invoice.tax_total, places),
                Fixed(invoice.grand_total, places),
                Fixed(invoice.paid_total, places),
                Fixed(invoice.open_amount, places),
            ]


async def supplier_rows(db: AsyncSession, filters: ExportFilters) -> AsyncIterator[Sequence[Cell]]:
    stmt = select(Supplier)
    if filters.status:
        stmt = stmt.where(Supplier.is_active.is_(filters.status == ACTIVE))
    if filters.date_from:
        stmt = stmt.where(Supplier.created_at >= day_start(filters.date_from))
    if filters.date_to:
        stmt = stmt.where(Supplier.created_at < day_after(filters.date_to))
    async for page in keyset_pages(db, stmt, Supplier.id):
        for supplier in page:
            yield [
                supplier.name,
                supplier.contact_name,
                supplier.email,
                supplier.phone,
                supplier.address,
                supplier.country_code,
                supplier.tax_id,
                supplier.currency_code,
                supplier.payment_terms_days,
                supplier.is_active,
                supplier.created_at.date(),
            ]


PURCHASE_ORDERS = Dataset(
    name="purchase-orders",
    filename="purchase-orders.csv",
    header=(
        "PO Number",
        "Supplier",
        "Status",
        "Currency",
        "Subtotal",
        "Tax",
        "Total",
        "Expected Delivery",
        "Created",
        "Approved",
    ),
    rows=purchase_order_rows,
    statuses=frozenset(status.value for status in POStatus),
)
INVOICES = Dataset(
    name="invoices",
    filename="invoices.csv",
    header=(
        "Invoice Number",
        "Supplier",
        "PO Number",
        "Invoice Date",
        "Due Date",
        "Status",
        "Currency",
        "Subtotal",
        "Tax",
        "Total",
        "Paid",
        "Open",
    ),
    rows=invoice_rows,
    statuses=frozenset(status.value for status in InvoiceStatus),
)
SUPPLIERS = Dataset(
    name="suppliers",
    filename="suppliers.csv",
    header=(
        "Name",
        "Contact",
        "Email",
        "Phone",
        "Address",
        "Country",
        "Tax ID",
        "Currency",
        "Payment Terms (days)",
        "Active",
        "Created",
    ),
    rows=supplier_rows,
    statuses=frozenset({ACTIVE, INACTIVE}),
)
