from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.supplier import Supplier
from tests.flow_helpers import API
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    add_rate,
    create_invoice,
    invoice_body,
    ordered_po,
    reason_codes,
    receive,
    received_po,
    submit_invoice,
    submitted_invoice,
    tax_rate,
)

# --- total ---------------------------------------------------------------------------------------------------------


async def test_a_total_more_than_the_tolerance_above_the_order_is_flagged(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    tax_id = await tax_rate(client, staff, "2.01")
    body = invoice_body(po, product, number="TAXED")
    body["lines"][0]["tax_rate_id"] = tax_id
    invoice = await create_invoice(client, staff.officer, body)

    result = (await submit_invoice(client, staff.officer, invoice["id"])).json()

    assert result["grand_total"] == "102.01"
    assert reason_codes(result) == ["TOTAL_EXCEEDS_ORDER"]
    assert (
        "Invoice total 102.01 USD exceeds the order total 100.00 USD by 2.01% (tolerance 2.00%)"
        in (result["exception_reasons"][0]["message"])
    )
    assert result["exception_reasons"][0]["line"] is None


async def test_a_total_exactly_at_the_tolerance_above_the_order_matches(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    tax_id = await tax_rate(client, staff, "2")
    body = invoice_body(po, product)
    body["lines"][0]["tax_rate_id"] = tax_id
    invoice = await create_invoice(client, staff.officer, body)

    result = (await submit_invoice(client, staff.officer, invoice["id"])).json()

    assert result["grand_total"] == "102.00"
    assert result["status"] == "matched"


async def _taxed_received_po(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, tax_id: int
) -> dict[str, Any]:
    created = await client.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": product.id, "quantity": 10, "unit_price": "10.00", "tax_rate_id": tax_id}],
        },
        headers=staff.officer,
    )
    po_id = created.json()["id"]
    await client.post(f"{API}/purchase-orders/{po_id}/submit", headers=staff.officer)
    await client.post(f"{API}/purchase-orders/{po_id}/approve", headers=staff.manager)
    await client.post(f"{API}/purchase-orders/{po_id}/order", headers=staff.officer)
    received = await client.post(
        f"{API}/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": product.id, "quantity": 10}]},
        headers=staff.warehouse,
    )
    return dict(received.json())


async def test_an_invoice_line_without_a_tax_choice_inherits_the_order_lines_tax(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    tax_id = await tax_rate(client, staff, "20")
    po = await _taxed_received_po(client, staff, supplier, product, tax_id)

    inherited = await create_invoice(client, staff.officer, invoice_body(po, product, number="A"))
    submitted = await submit_invoice(client, staff.officer, inherited["id"])
    without_tax_body = invoice_body(po, product, number="B", quantity=1)
    without_tax_body["lines"][0]["tax_rate_id"] = None
    without_tax = await create_invoice(client, staff.officer, without_tax_body)

    assert po["grand_total"] == "120.00"
    assert inherited["lines"][0]["tax_rate_id"] == tax_id
    assert inherited["grand_total"] == "120.00"
    assert without_tax["lines"][0]["tax_rate_id"] is None
    assert without_tax["grand_total"] == "10.00"
    assert submitted.json()["status"] == "matched"


# --- unknown lines -------------------------------------------------------------------------------------------------


async def test_a_product_that_is_not_on_the_order_is_an_unknown_line(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    po = await received_po(client, staff, supplier, product)
    other = Product(sku="OTHER-9", name="Other thing", cost=1, minimum_stock=0, supplier_id=supplier.id)
    db_session.add(other)
    await db_session.commit()
    body = invoice_body(po, product, quantity=5)
    body["lines"].append({"product_id": other.id, "quantity": 1, "unit_price": "1.00"})
    invoice = await create_invoice(client, staff.officer, body)

    result = (await submit_invoice(client, staff.officer, invoice["id"])).json()

    assert reason_codes(result) == ["UNKNOWN_LINE"]
    assert result["exception_reasons"][0]["line"] == 2
    assert f"is not on purchase order {po['po_number']}" in result["exception_reasons"][0]["message"]


async def test_a_line_without_a_product_is_an_unknown_line(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    body = invoice_body(po, product, quantity=5)
    body["lines"].append({"description": "Freight", "quantity": 1, "unit_price": "5.00"})
    invoice = await create_invoice(client, staff.officer, body)

    result = (await submit_invoice(client, staff.officer, invoice["id"])).json()

    assert reason_codes(result) == ["UNKNOWN_LINE"]
    assert "Freight" in result["exception_reasons"][0]["message"]


async def test_several_problems_are_all_reported_together(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 5)

    invoice = await submitted_invoice(client, staff, po, product, quantity=9, unit_price="12.00")

    assert reason_codes(invoice) == ["PRICE_VARIANCE", "QUANTITY_EXCEEDS_RECEIVED", "TOTAL_EXCEEDS_ORDER"]


# --- foreign currency ----------------------------------------------------------------------------------------------


async def test_matching_works_in_the_order_currency(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "1.1")
    po = await received_po(client, staff, supplier, product, currency_code="EUR")

    invoice = await submitted_invoice(client, staff, po, product)

    assert invoice["currency_code"] == "EUR"
    assert invoice["status"] == "matched"
    assert invoice["grand_total"] == "100.00"


async def test_an_invoice_in_another_currency_than_the_order_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)

    response = await client.post(INVOICES, json=invoice_body(po, product, currency_code="EUR"), headers=staff.officer)

    assert response.status_code == 422
    assert "must equal the purchase order currency USD" in response.json()["detail"]


async def test_the_matching_setting_is_validated(client: AsyncClient, staff: Staff) -> None:
    bad = await client.patch(f"{API}/company-settings", json={"invoice_matching": "four_way"}, headers=staff.admin)
    cleared = await client.patch(f"{API}/company-settings", json={"invoice_matching": None}, headers=staff.admin)
    good = await client.patch(f"{API}/company-settings", json={"invoice_matching": "two_way"}, headers=staff.admin)

    assert bad.status_code == 422
    assert cleared.status_code == 422
    assert good.json()["invoice_matching"] == "two_way"
