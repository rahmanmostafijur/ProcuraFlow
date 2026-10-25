"""Builds purchase orders directly in the database with consistent stored amounts, for tests that need many
statuses or timestamps without walking each order through the API."""

from collections.abc import Sequence
from decimal import Decimal

from app.core.money import compute_line, sum_lines
from app.models.enums import COMMITTED_PO_STATUSES, POStatus
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem

Line = tuple[int, int, Decimal]  # product id, quantity, unit price


def build_po(
    *,
    po_number: str,
    supplier_id: int | None,
    created_by: int,
    status: POStatus,
    lines: Sequence[Line],
    currency_code: str = "USD",
    minor_units: int = 2,
    exchange_rate: Decimal = Decimal(1),
) -> PurchaseOrder:
    """An order whose line, document and (for committed statuses) base-currency amounts are already stored."""
    items: list[PurchaseOrderItem] = []
    amounts = []
    for product_id, quantity, unit_price in lines:
        line = compute_line(
            quantity=quantity,
            unit_price=unit_price,
            tax_percent=Decimal(0),
            tax_inclusive=False,
            minor_units=minor_units,
        )
        amounts.append(line)
        items.append(
            PurchaseOrderItem(
                product_id=product_id,
                quantity=quantity,
                unit_price=unit_price,
                line_net=line.net,
                line_tax=line.tax,
                line_total=line.total,
            )
        )
    totals = sum_lines(amounts)
    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=supplier_id,
        created_by=created_by,
        status=status,
        currency_code=currency_code,
        subtotal=totals.subtotal,
        tax_total=totals.tax_total,
        grand_total=totals.grand_total,
    )
    po.items = items
    if status in COMMITTED_PO_STATUSES:
        po.exchange_rate = exchange_rate
        po.base_subtotal = totals.subtotal * exchange_rate
        po.base_tax_total = totals.tax_total * exchange_rate
        po.base_grand_total = totals.grand_total * exchange_rate
    return po
