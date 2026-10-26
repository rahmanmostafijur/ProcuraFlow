"""Matching a supplier invoice against its purchase order, and spotting duplicates.

Rules, all compared as Decimals with the tolerance percent from the company settings:

* PRICE: |invoice unit price - order unit price| <= tolerance% of the order price, per line.
* QUANTITY: the quantity invoiced so far for the order line (every non-void invoice, this one included) may not
  exceed what was ordered (two-way) or what was accepted into stock (three-way).
* TOTAL: the invoice total may not exceed the order total by more than the tolerance.
* DUPLICATE: another non-void invoice from the supplier with the same number (trimmed, any case), or the same total
  dated within ``DUPLICATE_WINDOW_DAYS`` days.
* UNKNOWN_LINE: a line that is not on the order.

A result with no reasons is a match; anything else is an exception that goes through approval.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import HUNDRED
from app.models.enums import InvoiceMatchMode, InvoiceStatus, MatchReasonCode
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.schemas.common import format_money

# Two invoices from one supplier for the same amount this close together are treated as a possible duplicate.
DUPLICATE_WINDOW_DAYS = 7
PERCENT_DECIMALS = Decimal("0.01")

Reason = dict[str, Any]


@dataclass(frozen=True)
class MatchResult:
    mode: InvoiceMatchMode
    tolerance_percent: Decimal
    reasons: list[Reason]

    @property
    def is_match(self) -> bool:
        return not self.reasons


def _reason(code: MatchReasonCode, message: str, line: int | None = None, duplicate_of: int | None = None) -> Reason:
    return {"code": code.value, "message": message, "line": line, "duplicate_of": duplicate_of}


def price_is_within_tolerance(invoice_price: Decimal, order_price: Decimal, tolerance_percent: Decimal) -> bool:
    """Exactly at the limit still matches; one step beyond it does not."""
    return abs(invoice_price - order_price) * HUNDRED <= tolerance_percent * order_price


def total_is_within_tolerance(invoice_total: Decimal, order_total: Decimal, tolerance_percent: Decimal) -> bool:
    return (invoice_total - order_total) * HUNDRED <= tolerance_percent * order_total


def _percent_over(amount: Decimal, base: Decimal) -> str:
    if base == 0:
        return "n/a"
    return format((amount * HUNDRED / base).quantize(PERCENT_DECIMALS), "f")


def _label(position: int, line: SupplierInvoiceLine) -> str:
    return f"Line {position} ({line.description})"


def _price_reason(
    position: int, line: SupplierInvoiceLine, item: PurchaseOrderItem, tolerance: Decimal
) -> Reason | None:
    if price_is_within_tolerance(line.unit_price, item.unit_price, tolerance):
        return None
    difference = abs(line.unit_price - item.unit_price)
    return _reason(
        MatchReasonCode.PRICE_VARIANCE,
        f"{_label(position, line)}: invoice price {format_money(line.unit_price)} differs from the order price "
        f"{format_money(item.unit_price)} by {_percent_over(difference, item.unit_price)}% "
        f"(tolerance {format_money(tolerance)}%).",
        line=position,
    )


def _quantity_reason(
    position: int, line: SupplierInvoiceLine, item: PurchaseOrderItem, invoiced: int, mode: InvoiceMatchMode
) -> Reason | None:
    if mode == InvoiceMatchMode.THREE_WAY:
        if invoiced <= item.received_quantity:
            return None
        return _reason(
            MatchReasonCode.QUANTITY_EXCEEDS_RECEIVED,
            f"{_label(position, line)}: {invoiced} units invoiced in total (this invoice included), but only "
            f"{item.received_quantity} accepted into stock.",
            line=position,
        )
    if invoiced <= item.quantity:
        return None
    return _reason(
        MatchReasonCode.QUANTITY_EXCEEDS_ORDERED,
        f"{_label(position, line)}: {invoiced} units invoiced in total (this invoice included), but only "
        f"{item.quantity} ordered.",
        line=position,
    )


async def _invoiced_quantities(db: AsyncSession, po_id: int) -> dict[int, int]:
    """Units invoiced per product on the order across every non-void invoice, drafts and this one included."""
    rows = await db.execute(
        select(SupplierInvoiceLine.product_id, func.sum(SupplierInvoiceLine.quantity))
        .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceLine.invoice_id)
        .where(
            SupplierInvoice.po_id == po_id,
            SupplierInvoice.status != InvoiceStatus.VOID,
            SupplierInvoiceLine.product_id.is_not(None),
        )
        .group_by(SupplierInvoiceLine.product_id)
    )
    return {int(product_id): int(total) for product_id, total in rows.all()}


def _line_reasons(
    invoice: SupplierInvoice,
    po: PurchaseOrder,
    invoiced: dict[int, int],
    mode: InvoiceMatchMode,
    tolerance: Decimal,
) -> list[Reason]:
    items = {item.product_id: item for item in po.items}
    reasons: list[Reason] = []
    checked_quantities: set[int] = set()
    for position, line in enumerate(invoice.lines, start=1):
        item = items.get(line.product_id) if line.product_id is not None else None
        if item is None:
            reasons.append(
                _reason(
                    MatchReasonCode.UNKNOWN_LINE,
                    f"{_label(position, line)} is not on purchase order {po.po_number}.",
                    line=position,
                )
            )
            continue
        price = _price_reason(position, line, item, tolerance)
        if price:
            reasons.append(price)
        # One quantity verdict per order line, even when an invoice lists a product twice.
        if item.product_id not in checked_quantities:
            checked_quantities.add(item.product_id)
            quantity = _quantity_reason(position, line, item, invoiced.get(item.product_id, 0), mode)
            if quantity:
                reasons.append(quantity)
    return reasons


def _normalised(number: str) -> str:
    return number.strip().lower()


async def duplicate_reasons(db: AsyncSession, invoice: SupplierInvoice) -> list[Reason]:
    """One reason per other non-void invoice of the supplier that looks like the same bill."""
    others = (
        (
            await db.execute(
                select(SupplierInvoice).where(
                    SupplierInvoice.supplier_id == invoice.supplier_id,
                    SupplierInvoice.id != invoice.id,
                    SupplierInvoice.status != InvoiceStatus.VOID,
                )
            )
        )
        .scalars()
        .all()
    )
    window = timedelta(days=DUPLICATE_WINDOW_DAYS)
    reasons: list[Reason] = []
    for other in sorted(others, key=lambda row: row.id):
        if _normalised(other.invoice_number) == _normalised(invoice.invoice_number):
            message = (
                f"Possible duplicate of invoice {other.id} ({other.invoice_number}): same supplier and invoice number."
            )
        elif other.grand_total == invoice.grand_total and abs(other.invoice_date - invoice.invoice_date) <= window:
            message = (
                f"Possible duplicate of invoice {other.id} ({other.invoice_number}): same supplier and total "
                f"{format_money(invoice.grand_total)} {invoice.currency_code}, dated {other.invoice_date.isoformat()} "
                f"(within {DUPLICATE_WINDOW_DAYS} days)."
            )
        else:
            continue
        reasons.append(_reason(MatchReasonCode.DUPLICATE_INVOICE, message, duplicate_of=other.id))
    return reasons


async def match_invoice(
    db: AsyncSession,
    invoice: SupplierInvoice,
    po: PurchaseOrder,
    mode: InvoiceMatchMode,
    tolerance_percent: Decimal,
) -> MatchResult:
    """Run every rule on the invoice. The caller holds the order's lock, so quantities cannot change under it."""
    invoiced = await _invoiced_quantities(db, po.id)
    reasons = _line_reasons(invoice, po, invoiced, mode, tolerance_percent)
    if not total_is_within_tolerance(invoice.grand_total, po.grand_total, tolerance_percent):
        reasons.append(
            _reason(
                MatchReasonCode.TOTAL_EXCEEDS_ORDER,
                f"Invoice total {format_money(invoice.grand_total)} {invoice.currency_code} exceeds the order total "
                f"{format_money(po.grand_total)} {po.currency_code} by "
                f"{_percent_over(invoice.grand_total - po.grand_total, po.grand_total)}% "
                f"(tolerance {format_money(tolerance_percent)}%).",
            )
        )
    reasons.extend(await duplicate_reasons(db, invoice))
    return MatchResult(mode=mode, tolerance_percent=tolerance_percent, reasons=reasons)
