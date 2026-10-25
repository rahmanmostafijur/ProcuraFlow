"""Snapshots of a purchase order and a readable diff between two of them.

A snapshot is plain JSON (Decimals as strings) so it can be stored with the version and compared later even if the
products or tax rates it mentions change. Lines carry the product's SKU and name as they were, so a diff reads as
"Blue pen: quantity 10 to 8" without looking anything up.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.money import trim_money
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.common import format_money

Snapshot = dict[str, Any]
Change = dict[str, Any]

FIELD_LABELS = {
    "expected_delivery_date": "Expected delivery",
    "notes": "Notes",
}
LINE_FIELD_LABELS = {
    "quantity": "Quantity",
    "unit_price": "Unit price",
    "tax_name": "Tax",
}


def _money(value: Decimal) -> str:
    return format_money(value)


def snapshot_of(po: PurchaseOrder, product_names: dict[int, tuple[str, str]]) -> Snapshot:
    """The order as it is now. ``product_names`` maps a product id to its (SKU, name)."""
    return snapshot_from_parts(
        currency_code=po.currency_code,
        expected_delivery_date=po.expected_delivery_date,
        notes=po.notes,
        items=po.items,
        totals=(po.subtotal, po.tax_total, po.grand_total),
        product_names=product_names,
    )


def snapshot_from_parts(
    *,
    currency_code: str,
    expected_delivery_date: date | None,
    notes: str | None,
    items: Iterable[PurchaseOrderItem],
    totals: tuple[Decimal, Decimal, Decimal],
    product_names: dict[int, tuple[str, str]],
) -> Snapshot:
    """A snapshot of an order that may not exist yet: the lines and totals an amendment proposes."""
    lines = []
    for item in sorted(items, key=lambda line: line.product_id):
        sku, name = product_names.get(item.product_id, (str(item.product_id), ""))
        lines.append(
            {
                "product_id": item.product_id,
                "sku": sku,
                "name": name,
                "quantity": item.quantity,
                "unit_price": _money(item.unit_price),
                "tax_rate_id": item.tax_rate_id,
                "tax_name": item.tax_name,
                "tax_percent": str(trim_money(item.tax_percent)),
                "tax_inclusive": item.tax_inclusive,
                "reverse_charge": item.reverse_charge,
                "line_total": _money(item.line_total),
            }
        )
    subtotal, tax_total, grand_total = totals
    return {
        "currency_code": currency_code,
        "expected_delivery_date": expected_delivery_date.isoformat() if expected_delivery_date else None,
        "notes": notes,
        "lines": lines,
        "subtotal": _money(subtotal),
        "tax_total": _money(tax_total),
        "grand_total": _money(grand_total),
    }


def _line_label(line: Snapshot) -> str:
    return f"{line['name']} ({line['sku']})" if line.get("name") else str(line["sku"])


def _line_changes(before: Snapshot, after: Snapshot) -> list[Change]:
    changes: list[Change] = []
    for field, label in LINE_FIELD_LABELS.items():
        if before.get(field) != after.get(field):
            changes.append({"field": field, "label": label, "from": before.get(field), "to": after.get(field)})
    return changes


def diff_snapshots(before: Snapshot, after: Snapshot) -> list[Change]:
    """Readable changes from ``before`` to ``after``: fields, lines added, removed or changed, and the new total."""
    changes: list[Change] = []
    for field, label in FIELD_LABELS.items():
        if before.get(field) != after.get(field):
            changes.append(
                {"kind": "field", "field": field, "label": label, "from": before.get(field), "to": after.get(field)}
            )

    before_lines = {line["product_id"]: line for line in before["lines"]}
    after_lines = {line["product_id"]: line for line in after["lines"]}
    for product_id in sorted(after_lines.keys() - before_lines.keys()):
        line = after_lines[product_id]
        changes.append(
            {
                "kind": "line_added",
                "product_id": product_id,
                "label": _line_label(line),
                "quantity": line["quantity"],
                "unit_price": line["unit_price"],
                "line_total": line["line_total"],
            }
        )
    for product_id in sorted(before_lines.keys() - after_lines.keys()):
        line = before_lines[product_id]
        changes.append(
            {
                "kind": "line_removed",
                "product_id": product_id,
                "label": _line_label(line),
                "quantity": line["quantity"],
                "unit_price": line["unit_price"],
                "line_total": line["line_total"],
            }
        )
    for product_id in sorted(before_lines.keys() & after_lines.keys()):
        old, new = before_lines[product_id], after_lines[product_id]
        line_changes = _line_changes(old, new)
        if line_changes:
            changes.append(
                {
                    "kind": "line_changed",
                    "product_id": product_id,
                    "label": _line_label(new),
                    "changes": line_changes,
                    "from_total": old["line_total"],
                    "to_total": new["line_total"],
                }
            )
    if before["grand_total"] != after["grand_total"]:
        changes.append({"kind": "total", "label": "Total", "from": before["grand_total"], "to": after["grand_total"]})
    return changes
