import asyncio
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    add_rate,
    approved_invoice,
    get_invoice,
    matched_invoice,
    pay,
    received_po,
)

OPERATION_TIMEOUT_SECONDS = 20


async def _approved(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, **po_extra: Any
) -> dict[str, Any]:
    po = await received_po(client, staff, supplier, product, **po_extra)
    return await approved_invoice(client, staff, po, product)


async def test_a_partial_payment_keeps_the_invoice_approved_and_the_rest_open(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)

    response = await pay(client, staff.finance, invoice["id"], "40.00", reference="CHQ-1", method="cheque")

    body = response.json()
    assert response.status_code == 201
    assert body["amount"] == "40.00"
    assert (body["method"], body["reference"], body["currency_code"]) == ("cheque", "CHQ-1", "USD")
    assert body["paid_on"] == utc_today().isoformat()
    assert body["payment_run_id"] is None
    assert body["creator"]["full_name"] == "Finance User"
    after = await get_invoice(client, staff.finance, invoice["id"])
    assert (after["status"], after["paid_total"], after["open_amount"]) == ("approved", "40.00", "60.00")


async def test_payments_that_cover_the_total_make_the_invoice_paid(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)
    await pay(client, staff.finance, invoice["id"], "40.00")

    final = await pay(client, staff.finance, invoice["id"], "60.00", method="card")

    assert final.status_code == 201
    after = await get_invoice(client, staff.finance, invoice["id"])
    assert (after["status"], after["paid_total"], after["open_amount"]) == ("paid", "100.00", "0.00")
    listed = (await client.get(f"{INVOICES}/{invoice['id']}/payments", headers=staff.finance)).json()
    assert [(row["amount"], row["method"]) for row in listed] == [("40.00", "bank_transfer"), ("60.00", "card")]


async def test_a_payment_above_the_open_amount_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)
    await pay(client, staff.finance, invoice["id"], "70.00")

    over = await pay(client, staff.finance, invoice["id"], "30.01")
    exact = await pay(client, staff.finance, invoice["id"], "30.00")

    assert over.status_code == 422
    assert over.json()["detail"] == "The payment of 30.01 USD is more than the open amount of 30.00 USD"
    assert exact.status_code == 201


async def test_a_paid_invoice_cannot_be_paid_again(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)
    await pay(client, staff.finance, invoice["id"], "100.00")

    again = await pay(client, staff.finance, invoice["id"], "1.00")

    assert again.status_code == 409
    assert again.json()["detail"] == "Only approved invoices can be paid; this one is 'paid'"


async def test_an_invoice_that_is_not_approved_cannot_be_paid(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    response = await pay(client, staff.finance, invoice["id"], "10.00")

    assert response.status_code == 409
    assert response.json()["detail"] == "Only approved invoices can be paid; this one is 'matched'"


@pytest.mark.parametrize("amount", ["0", "-5.00", "abc", "1.00001"])
async def test_invalid_amounts_are_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, amount: str
) -> None:
    invoice = await _approved(client, staff, supplier, product)

    response = await pay(client, staff.finance, invoice["id"], amount)

    assert response.status_code == 422


async def test_an_amount_with_more_decimals_than_the_currency_has_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)

    response = await pay(client, staff.finance, invoice["id"], "10.005")

    assert response.status_code == 422
    assert "at most 2 decimal places" in response.json()["detail"]


async def test_an_unknown_method_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)

    response = await pay(client, staff.finance, invoice["id"], "10.00", method="crypto")

    assert response.status_code == 422


async def test_the_payment_date_defaults_to_today_can_be_in_the_past_but_not_the_future(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)
    past = (utc_today() - timedelta(days=2)).isoformat()
    future = (utc_today() + timedelta(days=2)).isoformat()

    earlier = await pay(client, staff.finance, invoice["id"], "10.00", paid_on=past)
    later = await pay(client, staff.finance, invoice["id"], "10.00", paid_on=future)

    assert earlier.json()["paid_on"] == past
    assert later.status_code == 422


async def test_a_foreign_currency_invoice_is_paid_in_its_own_currency(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    await add_rate(client, staff.finance, "EUR", "1.1")
    invoice = await _approved(client, staff, supplier, product, currency_code="EUR")

    response = await pay(client, staff.finance, invoice["id"], "100.00")

    assert response.json()["currency_code"] == "EUR"
    assert (await get_invoice(client, staff.finance, invoice["id"]))["status"] == "paid"


async def test_every_payment_is_audited(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    invoice = await _approved(client, staff, supplier, product)
    await pay(client, staff.finance, invoice["id"], "100.00", reference="WIRE-9")

    entry = await db_session.scalar(select(AuditLog).where(AuditLog.action == "payment_recorded"))

    assert entry is not None
    assert entry.entity_type == "supplier_invoice"
    assert entry.extra_data is not None
    assert entry.extra_data["amount"] == "100.00"
    assert entry.extra_data["fully_paid"] is True


@pytest.mark.parametrize("role", ["officer", "manager", "warehouse", "viewer"])
async def test_recording_a_payment_needs_the_payment_permission(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, role: str
) -> None:
    invoice = await _approved(client, staff, supplier, product)

    response = await pay(client, getattr(staff, role), invoice["id"], "10.00")

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have the 'payment:write' permission"


async def test_an_admin_can_record_a_payment(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)

    response = await pay(client, staff.admin, invoice["id"], "10.00")

    assert response.status_code == 201


async def test_payments_of_an_unknown_invoice_are_not_found_and_need_sign_in(client: AsyncClient, staff: Staff) -> None:
    assert (await pay(client, staff.finance, 99999, "10.00")).status_code == 404
    assert (await client.get(f"{INVOICES}/99999/payments", headers=staff.finance)).status_code == 404
    assert (await client.post(f"{INVOICES}/1/payments", json={})).status_code == 401
    assert (await client.get(f"{INVOICES}/1/payments")).status_code == 401


async def test_two_simultaneous_payments_cannot_together_exceed_the_open_amount(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)

    responses = await asyncio.wait_for(
        asyncio.gather(*(pay(client, staff.finance, invoice["id"], "60.00") for _ in range(2))),
        timeout=OPERATION_TIMEOUT_SECONDS,
    )

    assert sorted(response.status_code for response in responses) == [201, 422]
    after = await get_invoice(client, staff.finance, invoice["id"])
    assert (after["paid_total"], after["open_amount"]) == ("60.00", "40.00")


async def test_many_simultaneous_payments_pay_exactly_what_fits(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product)

    responses = await asyncio.wait_for(
        asyncio.gather(*(pay(client, staff.finance, invoice["id"], "30.00") for _ in range(6))),
        timeout=OPERATION_TIMEOUT_SECONDS,
    )

    assert sorted(response.status_code for response in responses) == [201, 201, 201, 422, 422, 422]
    after = await get_invoice(client, staff.finance, invoice["id"])
    assert Decimal(after["paid_total"]) == Decimal("90.00")
    assert after["status"] == "approved"
