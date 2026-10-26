from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.product import Product
from app.models.supplier import Supplier
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    create_invoice,
    invoice_body,
    reason_codes,
    received_po,
    submit_invoice,
    submitted_invoice,
)


async def _two_orders(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        await received_po(client, staff, supplier, product),
        await received_po(client, staff, supplier, product),
    )


async def test_the_same_supplier_and_invoice_number_is_flagged_as_a_duplicate(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    first = await submitted_invoice(client, staff, po_one, product, number="INV-77")

    second = await submitted_invoice(client, staff, po_two, product, number="INV-77")

    assert first["status"] == "matched"
    assert second["status"] == "exception"
    assert reason_codes(second) == ["DUPLICATE_INVOICE"]
    [reason] = second["exception_reasons"]
    assert reason["duplicate_of"] == first["id"]
    assert reason["message"] == (
        f"Possible duplicate of invoice {first['id']} (INV-77): same supplier and invoice number."
    )


@pytest.mark.parametrize("second_number", ["inv-77", "Inv-77"])
async def test_the_invoice_number_comparison_ignores_case(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, second_number: str
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    first = await submitted_invoice(client, staff, po_one, product, number="INV-77")

    second = await submitted_invoice(client, staff, po_two, product, number=second_number)

    assert second["exception_reasons"][0]["duplicate_of"] == first["id"]


async def test_surrounding_spaces_in_the_number_are_ignored(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    first = await submitted_invoice(client, staff, po_one, product, number="INV-77")

    second = await submitted_invoice(client, staff, po_two, product, number="  INV-77  ")

    assert second["invoice_number"] == "INV-77"
    assert second["exception_reasons"][0]["duplicate_of"] == first["id"]


async def test_the_same_total_within_the_window_is_flagged_even_with_another_number(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    first = await submitted_invoice(client, staff, po_one, product, number="A-1", invoice_date=utc_today().isoformat())

    second = await submitted_invoice(
        client, staff, po_two, product, number="B-2", invoice_date=(utc_today() - timedelta(days=3)).isoformat()
    )

    assert reason_codes(second) == ["DUPLICATE_INVOICE"]
    reason = second["exception_reasons"][0]
    assert reason["duplicate_of"] == first["id"]
    assert "same supplier and total 100.00 USD" in reason["message"]
    assert "within 7 days" in reason["message"]


@pytest.mark.parametrize(("days_apart", "flagged"), [(7, True), (8, False)])
async def test_the_date_window_is_seven_days_inclusive(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, days_apart: int, flagged: bool
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    await submitted_invoice(client, staff, po_one, product, number="A-1", invoice_date=utc_today().isoformat())

    second = await submitted_invoice(
        client,
        staff,
        po_two,
        product,
        number="B-2",
        invoice_date=(utc_today() - timedelta(days=days_apart)).isoformat(),
    )

    assert (second["status"] == "exception") is flagged


async def test_a_different_total_with_a_different_number_is_not_a_duplicate(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    await submitted_invoice(client, staff, po_one, product, number="A-1")

    second = await submitted_invoice(client, staff, po_two, product, number="B-2", quantity=9)

    assert second["status"] == "matched"


async def test_another_suppliers_invoice_with_the_same_number_is_not_a_duplicate(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    other_supplier = Supplier(name="Other Supplier")
    db_session.add(other_supplier)
    await db_session.flush()
    other_product = Product(sku="OTH-2", name="Other", cost=1, minimum_stock=0, supplier_id=other_supplier.id)
    db_session.add(other_product)
    await db_session.commit()
    po_one = await received_po(client, staff, supplier, product)
    po_two = await received_po(client, staff, other_supplier, other_product)
    await submitted_invoice(client, staff, po_one, product, number="INV-1")

    second = await submitted_invoice(client, staff, po_two, other_product, number="INV-1")

    assert second["status"] == "matched"


@pytest.mark.parametrize("second_number", ["INV-9", "INV-10"])
async def test_a_voided_invoice_is_ignored_by_both_duplicate_rules(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, second_number: str
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    first = await submitted_invoice(client, staff, po_one, product, number="INV-9")
    await client.post(f"{INVOICES}/{first['id']}/void", json={"reason": "Entered twice"}, headers=staff.officer)

    second = await submitted_invoice(client, staff, po_two, product, number=second_number)

    assert second["status"] == "matched"


async def test_creating_a_duplicate_is_never_blocked(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    await create_invoice(client, staff.officer, invoice_body(po_one, product, number="INV-1"))

    again = await client.post(INVOICES, json=invoice_body(po_two, product, number="INV-1"), headers=staff.officer)

    assert again.status_code == 201
    assert again.json()["status"] == "draft"


async def test_a_resubmitted_invoice_is_not_a_duplicate_of_itself(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, number="INV-1", unit_price="12.00"))
    first = (await submit_invoice(client, staff.officer, invoice["id"])).json()
    await client.post(f"{INVOICES}/{invoice['id']}/reject", json={"comment": "Fix the price"}, headers=staff.finance)

    corrected = await client.patch(
        f"{INVOICES}/{invoice['id']}",
        json={"lines": [{"product_id": product.id, "quantity": 10, "unit_price": "10.00"}]},
        headers=staff.officer,
    )
    second = (await submit_invoice(client, staff.officer, invoice["id"])).json()

    assert first["status"] == "exception"
    assert corrected.status_code == 200
    assert second["status"] == "matched"
    assert second["exception_reasons"] == []


async def test_both_rules_naming_one_other_invoice_give_a_single_reason(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    await submitted_invoice(client, staff, po_one, product, number="INV-1")

    second = await submitted_invoice(client, staff, po_two, product, number="INV-1")

    assert reason_codes(second) == ["DUPLICATE_INVOICE"]


async def test_each_matching_earlier_invoice_gets_its_own_reason(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po_one, po_two = await _two_orders(client, staff, supplier, product)
    po_three = await received_po(client, staff, supplier, product)
    first = await submitted_invoice(client, staff, po_one, product, number="INV-1")
    second = await submitted_invoice(client, staff, po_two, product, number="INV-1")

    third = await submitted_invoice(client, staff, po_three, product, number="INV-1")

    assert [reason["duplicate_of"] for reason in third["exception_reasons"]] == [first["id"], second["id"]]
