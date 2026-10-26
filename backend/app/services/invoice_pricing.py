"""Pricing of supplier invoice lines and the base-currency lock at approval.

Same money rules as purchase orders (``app.core.money``): each line is rounded once to the invoice currency,
document totals are sums of those lines, and approval converts the totals into the base currency at the rate in
force that day, so base-currency payables can never move afterwards.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import DocumentTotals, LineAmounts, compute_line, sum_lines
from app.models.currency import Currency
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.services.po_pricing import NO_TAX, TaxSnapshot, base_totals, locked_rate_today

__all__ = ["NO_TAX", "InvoiceLineSpec", "TaxSnapshot", "apply_totals", "lock_invoice_base_amounts", "price_lines"]


@dataclass(frozen=True)
class InvoiceLineSpec:
    product_id: int | None
    po_item_id: int | None
    description: str
    quantity: int
    unit_price: Decimal
    tax: TaxSnapshot = NO_TAX


def price_lines(
    specs: Sequence[InvoiceLineSpec], currency: Currency
) -> tuple[list[SupplierInvoiceLine], DocumentTotals]:
    lines: list[SupplierInvoiceLine] = []
    amounts: list[LineAmounts] = []
    for spec in specs:
        amount = compute_line(
            quantity=spec.quantity,
            unit_price=spec.unit_price,
            tax_percent=spec.tax.percent,
            tax_inclusive=spec.tax.inclusive,
            minor_units=currency.minor_units,
        )
        amounts.append(amount)
        lines.append(
            SupplierInvoiceLine(
                product_id=spec.product_id,
                po_item_id=spec.po_item_id,
                description=spec.description,
                quantity=spec.quantity,
                unit_price=spec.unit_price,
                tax_rate_id=spec.tax.rate_id,
                tax_name=spec.tax.name,
                tax_percent=spec.tax.percent,
                tax_inclusive=spec.tax.inclusive,
                reverse_charge=spec.tax.reverse_charge,
                line_net=amount.net,
                line_tax=amount.tax,
                line_total=amount.total,
            )
        )
    return lines, sum_lines(amounts)


def apply_totals(invoice: SupplierInvoice, totals: DocumentTotals) -> None:
    invoice.subtotal = totals.subtotal
    invoice.tax_total = totals.tax_total
    invoice.grand_total = totals.grand_total


async def lock_invoice_base_amounts(db: AsyncSession, invoice: SupplierInvoice) -> None:
    """Freeze the invoice's base-currency amounts at approval using the rate in force today (company time zone)."""
    invoice.exchange_rate = await locked_rate_today(db, invoice.currency_code)
    invoice.base_subtotal, invoice.base_tax_total, invoice.base_grand_total = await base_totals(
        db, invoice.subtotal, invoice.tax_total, invoice.exchange_rate
    )
