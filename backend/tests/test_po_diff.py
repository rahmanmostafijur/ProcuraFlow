from typing import Any

from app.services.po_diff import diff_snapshots


def _line(product_id: int, quantity: int, unit_price: str, total: str, tax_name: str | None = None) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "sku": f"SKU-{product_id}",
        "name": f"Product {product_id}",
        "quantity": quantity,
        "unit_price": unit_price,
        "tax_name": tax_name,
        "line_total": total,
    }


def _snapshot(lines: list[dict[str, Any]], total: str, **fields: Any) -> dict[str, Any]:
    return {
        "currency_code": "USD",
        "expected_delivery_date": None,
        "notes": None,
        "lines": lines,
        "subtotal": total,
        "tax_total": "0.00",
        "grand_total": total,
        **fields,
    }


def test_identical_snapshots_have_no_changes() -> None:
    snapshot = _snapshot([_line(1, 10, "10.00", "100.00")], "100.00")

    assert diff_snapshots(snapshot, snapshot) == []


def test_a_changed_line_lists_each_field_that_moved_and_the_new_total() -> None:
    before = _snapshot([_line(1, 10, "10.00", "100.00")], "100.00")
    after = _snapshot([_line(1, 8, "9.50", "76.00", tax_name="VAT 20%")], "76.00")

    changes = diff_snapshots(before, after)

    line, total = changes
    assert line["kind"] == "line_changed"
    assert line["label"] == "Product 1 (SKU-1)"
    assert [(c["field"], c["label"], c["from"], c["to"]) for c in line["changes"]] == [
        ("quantity", "Quantity", 10, 8),
        ("unit_price", "Unit price", "10.00", "9.50"),
        ("tax_name", "Tax", None, "VAT 20%"),
    ]
    assert (line["from_total"], line["to_total"]) == ("100.00", "76.00")
    assert total == {"kind": "total", "label": "Total", "from": "100.00", "to": "76.00"}


def test_added_and_removed_lines_are_reported_with_their_figures() -> None:
    before = _snapshot([_line(1, 10, "10.00", "100.00"), _line(2, 1, "5.00", "5.00")], "105.00")
    after = _snapshot([_line(1, 10, "10.00", "100.00"), _line(3, 2, "7.50", "15.00")], "115.00")

    changes = diff_snapshots(before, after)

    kinds = [(change["kind"], change.get("label")) for change in changes]
    assert kinds == [
        ("line_added", "Product 3 (SKU-3)"),
        ("line_removed", "Product 2 (SKU-2)"),
        ("total", "Total"),
    ]
    assert (changes[0]["quantity"], changes[0]["unit_price"], changes[0]["line_total"]) == (2, "7.50", "15.00")


def test_changed_fields_come_first_with_readable_labels() -> None:
    lines = [_line(1, 10, "10.00", "100.00")]
    before = _snapshot(lines, "100.00", notes="Original", expected_delivery_date="2026-12-01")
    after = _snapshot(lines, "100.00", notes="Rush order", expected_delivery_date="2026-11-15")

    changes = diff_snapshots(before, after)

    assert [(c["kind"], c["label"], c["from"], c["to"]) for c in changes] == [
        ("field", "Expected delivery", "2026-12-01", "2026-11-15"),
        ("field", "Notes", "Original", "Rush order"),
    ]


def test_a_line_with_only_its_total_changed_is_not_reported_as_a_line_change() -> None:
    # Same quantity, price and tax, so nothing a reader can act on changed; only the document total moved.
    before = _snapshot([_line(1, 10, "10.00", "100.00")], "100.00")
    after = _snapshot([_line(1, 10, "10.00", "100.01")], "100.01")

    changes = diff_snapshots(before, after)

    assert [change["kind"] for change in changes] == ["total"]


def test_the_order_of_lines_does_not_matter() -> None:
    a, b = _line(1, 1, "1.00", "1.00"), _line(2, 2, "2.00", "4.00")

    assert diff_snapshots(_snapshot([a, b], "5.00"), _snapshot([b, a], "5.00")) == []
