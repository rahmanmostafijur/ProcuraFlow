from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.product import Product
from app.models.supplier import Supplier
from app.services.invoice_matching_service import price_is_within_tolerance, total_is_within_tolerance
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    create_invoice,
    invoice_body,
    ordered_po,
    reason_codes,
    receive,
    received_po,
    set_matching,
    submit_invoice,
    submitted_invoice,
)

# --- the pure comparisons ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("invoice_price", "expected"),
    [("10.20", True), ("10.21", False), ("9.80", True), ("9.79", False), ("10.00", True)],
)
def test_the_price_check_is_inclusive_at_the_tolerance_limit(invoice_price: str, expected: bool) -> None:
    assert price_is_within_tolerance(Decimal(invoice_price), Decimal("10.00"), Decimal("2.00")) is expected


@pytest.mark.parametrize(("total", "expected"), [("102.00", True), ("102.01", False), ("50.00", True)])
def test_the_total_check_is_inclusive_and_never_flags_a_smaller_invoice(total: str, expected: bool) -> None:
    assert total_is_within_tolerance(Decimal(total), Decimal("100.00"), Decimal("2.00")) is expected


def test_a_zero_order_price_accepts_only_a_zero_invoice_price() -> None:
    assert price_is_within_tolerance(Decimal(0), Decimal(0), Decimal("2.00")) is True
    assert price_is_within_tolerance(Decimal("0.01"), Decimal(0), Decimal("2.00")) is False


# --- price ---------------------------------------------------------------------------------------------------------


async def test_an_invoice_that_agrees_with_the_order_is_matched(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)

    invoice = await submitted_invoice(client, staff, po, product)

    assert invoice["status"] == "matched"
    assert invoice["exception_reasons"] == []
    assert invoice["match_mode"] == "three_way"
    assert invoice["tolerance_percent"] == "2.00"
    assert invoice["submitted_at"] is not None


@pytest.mark.parametrize("price", ["10.20", "9.80"])
async def test_a_price_exactly_at_the_tolerance_limit_matches(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, price: str
) -> None:
    po = await received_po(client, staff, supplier, product)

    invoice = await submitted_invoice(client, staff, po, product, quantity=1, unit_price=price)

    assert invoice["status"] == "matched"


@pytest.mark.parametrize("price", ["10.21", "9.79"])
async def test_a_price_just_beyond_the_tolerance_limit_is_an_exception(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, price: str
) -> None:
    po = await received_po(client, staff, supplier, product)

    invoice = await submitted_invoice(client, staff, po, product, quantity=1, unit_price=price)

    assert invoice["status"] == "exception"
    assert reason_codes(invoice) == ["PRICE_VARIANCE"]
    [reason] = invoice["exception_reasons"]
    assert reason["line"] == 1
    assert f"invoice price {price} differs from the order price 10.00" in reason["message"]
    assert "(tolerance 2.00%)" in reason["message"]


async def test_the_tolerance_comes_from_the_company_settings(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    await set_matching(client, staff, invoice_tolerance_percent="0")

    strict = await submitted_invoice(client, staff, po, product, quantity=1, unit_price="10.01", number="A")
    await set_matching(client, staff, invoice_tolerance_percent="10")
    loose = await submitted_invoice(client, staff, po, product, quantity=1, unit_price="10.99", number="B")

    assert strict["status"] == "exception"
    assert strict["tolerance_percent"] == "0.00"
    assert loose["status"] == "matched"
    assert loose["tolerance_percent"] == "10.00"


async def test_the_price_message_names_the_percentage_difference(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)

    invoice = await submitted_invoice(client, staff, po, product, quantity=1, unit_price="11.00")

    assert "by 10.00%" in invoice["exception_reasons"][0]["message"]


# --- quantity ------------------------------------------------------------------------------------------------------


async def test_three_way_matching_compares_with_the_accepted_quantity(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 6)

    invoice = await submitted_invoice(client, staff, po, product, quantity=7)

    assert invoice["status"] == "exception"
    assert reason_codes(invoice) == ["QUANTITY_EXCEEDS_RECEIVED"]
    assert (
        "7 units invoiced in total (this invoice included), but only 6 accepted into stock"
        in (invoice["exception_reasons"][0]["message"])
    )


async def test_rejected_units_do_not_count_as_received_for_three_way_matching(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 10, rejected=4)

    over = await submitted_invoice(client, staff, po, product, quantity=7, number="A")
    exact = await submitted_invoice(client, staff, po, product, quantity=6, number="B")

    assert reason_codes(over) == ["QUANTITY_EXCEEDS_RECEIVED"]
    assert "only 6 accepted" in over["exception_reasons"][0]["message"]
    assert exact["status"] == "exception"  # A is still a draft-turned-exception and counts: 7 + 6 > 6
    assert reason_codes(exact) == ["QUANTITY_EXCEEDS_RECEIVED"]


async def test_exactly_the_accepted_quantity_matches_three_way(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 10, rejected=4)

    invoice = await submitted_invoice(client, staff, po, product, quantity=6)

    assert invoice["status"] == "matched"


async def test_an_order_with_nothing_received_cannot_match_three_way(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)

    invoice = await submitted_invoice(client, staff, po, product, quantity=1)

    assert reason_codes(invoice) == ["QUANTITY_EXCEEDS_RECEIVED"]


async def test_two_way_matching_compares_with_the_ordered_quantity_not_the_received_one(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await set_matching(client, staff, invoice_matching="two_way")
    po = await ordered_po(client, staff, supplier, product)

    within = await submitted_invoice(client, staff, po, product, quantity=10, number="A")

    assert within["status"] == "matched"
    assert within["match_mode"] == "two_way"


async def test_two_way_matching_flags_more_than_was_ordered(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await set_matching(client, staff, invoice_matching="two_way")
    po = await ordered_po(client, staff, supplier, product)

    invoice = await submitted_invoice(client, staff, po, product, quantity=11)

    assert reason_codes(invoice) == ["QUANTITY_EXCEEDS_ORDERED", "TOTAL_EXCEEDS_ORDER"]
    assert "but only 10 ordered" in invoice["exception_reasons"][0]["message"]


async def test_the_mode_in_force_at_submission_is_the_one_used(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product, quantity=5))
    await set_matching(client, staff, invoice_matching="two_way")

    submitted = await submit_invoice(client, staff.officer, invoice["id"])

    assert submitted.json()["match_mode"] == "two_way"
    assert submitted.json()["status"] == "matched"


async def test_quantities_add_up_across_invoices_for_the_same_order_line(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    first = await submitted_invoice(client, staff, po, product, quantity=6, number="A")

    second = await submitted_invoice(client, staff, po, product, quantity=5, number="B")

    assert first["status"] == "matched"
    assert second["status"] == "exception"
    assert reason_codes(second) == ["QUANTITY_EXCEEDS_RECEIVED"]
    assert "11 units invoiced in total" in second["exception_reasons"][0]["message"]


async def test_two_invoices_that_together_use_the_whole_order_both_match(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)

    first = await submitted_invoice(client, staff, po, product, quantity=6, number="A")
    second = await submitted_invoice(client, staff, po, product, quantity=4, number="B")

    assert (first["status"], second["status"]) == ("matched", "matched")


async def test_cumulative_quantities_apply_in_two_way_mode_too(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await set_matching(client, staff, invoice_matching="two_way")
    po = await ordered_po(client, staff, supplier, product)
    await submitted_invoice(client, staff, po, product, quantity=6, number="A")

    second = await submitted_invoice(client, staff, po, product, quantity=5, number="B")

    assert "QUANTITY_EXCEEDS_ORDERED" in reason_codes(second)


async def test_voided_invoices_no_longer_count_towards_the_quantity(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    first = await submitted_invoice(client, staff, po, product, quantity=10, number="A")
    await client.post(f"{INVOICES}/{first['id']}/void", json={"reason": "Wrong PO"}, headers=staff.officer)

    second = await submitted_invoice(client, staff, po, product, quantity=10, number="B")

    assert second["status"] == "matched"


async def test_draft_invoices_of_the_same_order_count_towards_the_quantity(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    await create_invoice(client, staff.officer, invoice_body(po, product, quantity=10, number="A"))

    second = await submitted_invoice(client, staff, po, product, quantity=1, number="B")

    assert reason_codes(second) == ["QUANTITY_EXCEEDS_RECEIVED"]


async def test_late_received_stock_lets_a_resubmitted_invoice_match(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 5)
    first = await submitted_invoice(client, staff, po, product, quantity=10)
    assert first["status"] == "exception"
    await client.post(f"{INVOICES}/{first['id']}/void", json={"reason": "Redo"}, headers=staff.officer)
    await receive(client, staff, po["id"], product, 5)

    second = await submitted_invoice(client, staff, po, product, quantity=10, number="INV-2")

    assert second["status"] == "matched"
