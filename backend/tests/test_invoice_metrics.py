from datetime import timedelta
from typing import Any

from httpx import AsyncClient

from app.core.clock import today_in
from app.models.product import Product
from app.models.supplier import Supplier
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    add_rate,
    approved_invoice,
    create_invoice,
    invoice_body,
    matched_invoice,
    pay,
    received_po,
    set_matching,
    submit_invoice,
)

SUMMARY_URL = "/api/v1/dashboard/summary"


async def _summary(client: AsyncClient, staff: Staff) -> dict[str, Any]:
    return dict((await client.get(SUMMARY_URL, headers=staff.viewer)).json())


async def _approved(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, number: str, **extra: Any
) -> dict[str, Any]:
    quantity = extra.pop("quantity", 10)
    price = extra.pop("unit_price", "10.00")
    invoice_extra = extra.pop("invoice_extra", {})
    po = await received_po(client, staff, supplier, product, quantity=quantity, unit_price=price, **extra)
    return await approved_invoice(
        client, staff, po, product, number=number, quantity=quantity, unit_price=price, **invoice_extra
    )


async def test_with_no_invoices_the_payables_figures_are_zero(client: AsyncClient, staff: Staff) -> None:
    summary = await _summary(client, staff)

    assert summary["payables_outstanding"] == "0.00"
    assert summary["payables_overdue"] == "0.00"
    assert summary["invoices_needing_attention"] == 0


async def test_payables_count_only_approved_invoices_at_their_locked_rates(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "2")
    await _approved(client, staff, supplier, product, "USD-1")  # 100.00 USD
    await _approved(client, staff, supplier, product, "EUR-1", currency_code="EUR")  # 100.00 EUR = 200.00
    held = await _approved(client, staff, supplier, product, "HELD")
    await client.post(f"{INVOICES}/{held['id']}/hold", json={"reason": "x"}, headers=staff.finance)
    voided = await _approved(client, staff, supplier, product, "VOID")
    await client.post(f"{INVOICES}/{voided['id']}/void", json={"reason": "x"}, headers=staff.finance)
    paid = await _approved(client, staff, supplier, product, "PAID")
    await pay(client, staff.finance, paid["id"], "100.00")
    po = await received_po(client, staff, supplier, product)
    await matched_invoice(client, staff, po, product, number="NOT-YET")

    summary = await _summary(client, staff)

    assert summary["payables_outstanding"] == "300.00"


async def test_a_partial_payment_lowers_payables_by_the_paid_part_at_the_locked_rate(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "2")
    invoice = await _approved(client, staff, supplier, product, "EUR-1", currency_code="EUR")

    await pay(client, staff.finance, invoice["id"], "40.00")

    assert (await _summary(client, staff))["payables_outstanding"] == "120.00"


async def test_a_new_exchange_rate_never_moves_payables_already_locked(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "2", days_ago=3)
    await _approved(client, staff, supplier, product, "EUR-1", currency_code="EUR")

    await add_rate(client, staff.finance, "EUR", "5")

    assert (await _summary(client, staff))["payables_outstanding"] == "200.00"


async def test_each_invoice_is_rounded_to_the_base_currency_before_summing(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "0.3355")
    for number in ("EUR-1", "EUR-2"):
        await _approved(client, staff, supplier, product, number, currency_code="EUR", quantity=1)

    # 10.00 EUR x 0.3355 = 3.355, which rounds half up to 3.36 for each invoice; the sum of the rounded amounts is 6.72.
    assert (await _summary(client, staff))["payables_outstanding"] == "6.72"


async def test_overdue_payables_are_those_due_before_today(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    today = today_in("UTC")
    for index, (number, offset) in enumerate((("LATE", -1), ("TODAY", 0), ("SOON", 5))):
        await _approved(
            client,
            staff,
            supplier,
            product,
            number,
            invoice_extra={
                "invoice_date": (today - timedelta(days=10 + 8 * index)).isoformat(),
                "due_date": (today + timedelta(days=offset)).isoformat(),
            },
        )

    summary = await _summary(client, staff)

    assert summary["payables_outstanding"] == "300.00"
    assert summary["payables_overdue"] == "100.00"


async def test_a_paid_part_of_an_overdue_invoice_is_no_longer_overdue(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    today = today_in("UTC")
    invoice = await _approved(
        client,
        staff,
        supplier,
        product,
        "LATE",
        invoice_extra={
            "invoice_date": (today - timedelta(days=10)).isoformat(),
            "due_date": (today - timedelta(days=2)).isoformat(),
        },
    )

    await pay(client, staff.finance, invoice["id"], "70.00")

    assert (await _summary(client, staff))["payables_overdue"] == "30.00"


async def test_the_company_time_zone_decides_which_invoices_are_overdue(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    # These two zones are 25 hours apart, so their calendar days always differ.
    behind, ahead = "Pacific/Pago_Pago", "Pacific/Kiritimati"
    due = today_in(behind)
    await _approved(
        client,
        staff,
        supplier,
        product,
        "TZ",
        invoice_extra={"invoice_date": (due - timedelta(days=3)).isoformat(), "due_date": due.isoformat()},
    )

    await set_matching(client, staff, timezone=behind)
    in_behind = (await _summary(client, staff))["payables_overdue"]
    await set_matching(client, staff, timezone=ahead)
    in_ahead = (await _summary(client, staff))["payables_overdue"]

    assert in_behind == "0.00"
    assert in_ahead == "100.00"


async def test_invoices_needing_attention_are_the_matched_and_exception_ones(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po_one = await received_po(client, staff, supplier, product)
    await matched_invoice(client, staff, po_one, product, number="M")
    po_two = await received_po(client, staff, supplier, product)
    exception = await create_invoice(
        client, staff.officer, invoice_body(po_two, product, number="E", unit_price="30.00")
    )
    await submit_invoice(client, staff.officer, exception["id"])
    po_three = await received_po(client, staff, supplier, product)
    await create_invoice(client, staff.officer, invoice_body(po_three, product, number="D"))
    await _approved(client, staff, supplier, product, "A")

    assert (await _summary(client, staff))["invoices_needing_attention"] == 2
