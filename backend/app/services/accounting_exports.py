"""Supplier bills in the import layouts of QuickBooks Online and Xero.

A bill is a supplier invoice that finance has approved (or that has since been paid). Each invoice line becomes one
row, repeating the bill's header columns, which is how both products read a multi-line bill. Accounts and tax names
are neutral defaults: the accountant maps them to the real chart of accounts in the import screen.
"""

from collections.abc import AsyncIterator, Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import InvoiceStatus
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services.export_common import (
    Dataset,
    ExportFilters,
    keyset_pages,
    minor_units_by_currency,
)
from app.services.export_writer import Cell, Fixed

BILL_STATUSES = (InvoiceStatus.APPROVED, InvoiceStatus.PAID)
QBO_DATE_FORMAT = "%m/%d/%Y"
XERO_DATE_FORMAT = "%d/%m/%Y"
QBO_EXPENSE_ACCOUNT = "Uncategorized Expense"
XERO_ACCOUNT_CODE = "300"
XERO_NO_TAX = "Tax Exempt"
PRICE_PRECISION = 4

QBO_HEADER = (
    "*BillNo",
    "*Vendor",
    "*BillDate",
    "*DueDate",
    "Terms",
    "Location",
    "Memo",
    "*Account",
    "LineDescription",
    "*LineAmount",
    "LineTaxCode",
    "LineTaxAmount",
    "Currency",
)
XERO_HEADER = (
    "*ContactName",
    "EmailAddress",
    "POAddressLine1",
    "POAddressLine2",
    "POAddressLine3",
    "POAddressLine4",
    "POCity",
    "PORegion",
    "POPostalCode",
    "POCountry",
    "*InvoiceNumber",
    "Reference",
    "*InvoiceDate",
    "*DueDate",
    "InventoryItemCode",
    "Description",
    "*Quantity",
    "*UnitAmount",
    "*AccountCode",
    "*TaxType",
    "TaxAmount",
    "TrackingName1",
    "TrackingOption1",
    "TrackingName2",
    "TrackingOption2",
    "Currency",
)


def bills_statement(filters: ExportFilters) -> Select[tuple[SupplierInvoice]]:
    statuses = [InvoiceStatus(filters.status)] if filters.status else list(BILL_STATUSES)
    stmt = (
        select(SupplierInvoice)
        .options(
            selectinload(SupplierInvoice.lines),
            selectinload(SupplierInvoice.supplier),
            selectinload(SupplierInvoice.purchase_order),
        )
        .where(SupplierInvoice.status.in_(statuses))
    )
    if filters.date_from:
        stmt = stmt.where(SupplierInvoice.invoice_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(SupplierInvoice.invoice_date <= filters.date_to)
    return stmt


async def _bill_lines(
    db: AsyncSession, filters: ExportFilters
) -> AsyncIterator[tuple[SupplierInvoice, SupplierInvoiceLine, int]]:
    minor_units = await minor_units_by_currency(db)
    async for page in keyset_pages(db, bills_statement(filters), SupplierInvoice.id):
        for invoice in page:
            for line in invoice.lines:
                yield invoice, line, minor_units[invoice.currency_code]


def _terms(invoice: SupplierInvoice) -> str:
    return f"Net {(invoice.due_date - invoice.invoice_date).days}"


async def quickbooks_rows(db: AsyncSession, filters: ExportFilters) -> AsyncIterator[Sequence[Cell]]:
    async for invoice, line, places in _bill_lines(db, filters):
        yield [
            invoice.invoice_number,
            invoice.supplier.name,
            invoice.invoice_date,
            invoice.due_date,
            _terms(invoice),
            None,
            invoice.purchase_order.po_number,
            QBO_EXPENSE_ACCOUNT,
            line.description,
            Fixed(line.line_net, places),
            line.tax_name,
            Fixed(line.line_tax, places),
            invoice.currency_code,
        ]


async def xero_rows(db: AsyncSession, filters: ExportFilters) -> AsyncIterator[Sequence[Cell]]:
    async for invoice, line, places in _bill_lines(db, filters):
        supplier = invoice.supplier
        yield [
            supplier.name,
            supplier.email,
            supplier.address,
            None,
            None,
            None,
            None,
            None,
            None,
            supplier.country_code,
            invoice.invoice_number,
            invoice.purchase_order.po_number,
            invoice.invoice_date,
            invoice.due_date,
            None,
            line.description,
            line.quantity,
            Fixed(line.unit_price, places, PRICE_PRECISION),
            XERO_ACCOUNT_CODE,
            line.tax_name or XERO_NO_TAX,
            Fixed(line.line_tax, places),
            None,
            None,
            None,
            None,
            invoice.currency_code,
        ]


BILL_STATUS_VALUES = frozenset(status.value for status in BILL_STATUSES)

QUICKBOOKS_BILLS = Dataset(
    name="quickbooks-bills",
    filename="quickbooks-bills.csv",
    header=QBO_HEADER,
    rows=quickbooks_rows,
    statuses=BILL_STATUS_VALUES,
    date_format=QBO_DATE_FORMAT,
)
XERO_BILLS = Dataset(
    name="xero-bills",
    filename="xero-bills.csv",
    header=XERO_HEADER,
    rows=xero_rows,
    statuses=BILL_STATUS_VALUES,
    date_format=XERO_DATE_FORMAT,
)
