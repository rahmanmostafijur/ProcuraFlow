import asyncio
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.audit import AuditLog
from app.models.payment import Payment
from app.models.product import Product
from app.models.supplier import Supplier
from tests.invoice_helpers import (
    INVOICES,
    RUNS,
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
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, number: str, **po_extra: Any
) -> dict[str, Any]:
    po = await received_po(client, staff, supplier, product, **po_extra)
    return await approved_invoice(client, staff, po, product, number=number)


async def _create(client: AsyncClient, headers: dict[str, str], invoice_ids: list[int], **extra: Any) -> Response:
    return await client.post(RUNS, json={"invoice_ids": invoice_ids, **extra}, headers=headers)


async def _release(client: AsyncClient, headers: dict[str, str], run_id: int) -> Response:
    return await client.post(f"{RUNS}/{run_id}/release", headers=headers)


async def _draft_run(
    client: AsyncClient,
    staff: Staff,
    supplier: Supplier,
    product: Product,
    count: int = 2,
    prefix: str = "INV",
    **extra: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    invoices = [await _approved(client, staff, supplier, product, f"{prefix}-{n}") for n in range(count)]
    response = await _create(client, staff.finance, [invoice["id"] for invoice in invoices], **extra)
    assert response.status_code == 201, response.text
    return dict(response.json()), invoices


async def test_a_run_groups_approved_invoices_at_their_open_amounts(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    first = await _approved(client, staff, supplier, product, "INV-A")
    second = await _approved(client, staff, supplier, product, "INV-B")
    await pay(client, staff.finance, second["id"], "40.00")

    response = await _create(client, staff.finance, [first["id"], second["id"]], method="cheque")

    body = response.json()
    assert response.status_code == 201
    assert body["number"] == f"PAY-{utc_today().year}-{body['id']:05d}" or body["number"].startswith(
        f"PAY-{utc_today().year}-"
    )
    assert (body["status"], body["method"], body["currency_code"], body["total"]) == (
        "draft",
        "cheque",
        "USD",
        "160.00",
    )
    assert body["creator"]["full_name"] == "Finance User"
    assert body["released_by"] is None
    assert [(item["invoice_number"], item["amount"]) for item in body["items"]] == [
        ("INV-A", "100.00"),
        ("INV-B", "60.00"),
    ]
    assert body["items"][0]["supplier_name"] == supplier.name


async def test_creating_a_run_changes_nothing_about_the_invoices(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    _, invoices = await _draft_run(client, staff, supplier, product)

    after = await get_invoice(client, staff.finance, invoices[0]["id"])

    assert (after["status"], after["paid_total"]) == ("approved", "0.00")
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 0


async def test_the_same_invoice_listed_twice_counts_once(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product, "INV-A")

    response = await _create(client, staff.finance, [invoice["id"], invoice["id"]])

    assert response.status_code == 201
    assert response.json()["total"] == "100.00"


async def test_only_approved_invoices_can_go_into_a_run(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    approved = await _approved(client, staff, supplier, product, "INV-OK")
    po = await received_po(client, staff, supplier, product)
    matched = await matched_invoice(client, staff, po, product, number="INV-M")

    response = await _create(client, staff.finance, [approved["id"], matched["id"]])

    assert response.status_code == 409
    assert response.json()["detail"] == "Only approved invoices can go into a payment run: INV-M (matched)"


async def test_a_run_pays_one_currency(client: AsyncClient, staff: Staff, supplier: Supplier, product: Product) -> None:
    await add_rate(client, staff.finance, "EUR", "1.1")
    dollars = await _approved(client, staff, supplier, product, "INV-USD")
    euros = await _approved(client, staff, supplier, product, "INV-EUR", currency_code="EUR")

    response = await _create(client, staff.finance, [dollars["id"], euros["id"]])

    assert response.status_code == 422
    assert "pays one currency" in response.json()["detail"]
    assert "EUR, USD" in response.json()["detail"]


async def test_unknown_invoices_and_empty_runs_are_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    invoice = await _approved(client, staff, supplier, product, "INV-A")

    unknown = await _create(client, staff.finance, [invoice["id"], 99999])
    empty = await _create(client, staff.finance, [])
    bad_method = await _create(client, staff.finance, [invoice["id"]], method="barter")

    assert unknown.status_code == 400
    assert unknown.json()["detail"] == "Unknown invoice ids: [99999]"
    assert empty.status_code == 422
    assert bad_method.status_code == 422


async def test_an_invoice_in_an_open_run_cannot_join_another_until_that_run_is_cancelled(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run, invoices = await _draft_run(client, staff, supplier, product, count=1)

    second = await _create(client, staff.finance, [invoices[0]["id"]])
    await client.post(f"{RUNS}/{run['id']}/cancel", headers=staff.finance)
    third = await _create(client, staff.finance, [invoices[0]["id"]])

    assert second.status_code == 409
    assert second.json()["detail"] == f"Invoices [{invoices[0]['id']}] are already in an open payment run"
    assert third.status_code == 201


async def test_a_second_person_releases_the_run_and_one_payment_is_recorded_per_invoice(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    run, invoices = await _draft_run(client, staff, supplier, product, method="card")

    response = await _release(client, staff.finance2, run["id"])

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "released"
    assert body["released_by"] == body["releaser"]["id"]
    assert body["releaser"]["full_name"] == "Finance User"
    assert body["released_at"] is not None
    for invoice in invoices:
        paid = await get_invoice(client, staff.finance, invoice["id"])
        assert (paid["status"], paid["paid_total"]) == ("paid", "100.00")
        [payment] = (await client.get(f"{INVOICES}/{invoice['id']}/payments", headers=staff.finance)).json()
        assert payment["payment_run_id"] == run["id"]
        assert (payment["method"], payment["amount"], payment["reference"]) == ("card", "100.00", run["number"])
        assert payment["paid_on"] == utc_today().isoformat()
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 2


async def test_the_person_who_created_a_run_cannot_release_it(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run, invoices = await _draft_run(client, staff, supplier, product)

    response = await _release(client, staff.finance, run["id"])

    assert response.status_code == 403
    assert response.json()["detail"] == "You created this payment run, so a second person must release it."
    assert (await get_invoice(client, staff.finance, invoices[0]["id"]))["status"] == "approved"
    assert (await client.get(f"{RUNS}/{run['id']}", headers=staff.finance)).json()["status"] == "draft"


async def test_an_admin_who_did_not_create_the_run_can_release_it(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run, _ = await _draft_run(client, staff, supplier, product)

    response = await _release(client, staff.admin, run["id"])

    assert response.status_code == 200


@pytest.mark.parametrize("role", ["officer", "manager", "warehouse", "viewer"])
async def test_creating_releasing_and_cancelling_need_the_payment_permissions(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, role: str
) -> None:
    run, invoices = await _draft_run(client, staff, supplier, product)
    headers = getattr(staff, role)

    create = await _create(client, headers, [invoices[0]["id"]])
    release = await _release(client, headers, run["id"])
    cancel = await client.post(f"{RUNS}/{run['id']}/cancel", headers=headers)

    assert create.status_code == 403
    assert create.json()["detail"] == "You do not have the 'payment:write' permission"
    assert release.status_code == 403
    assert release.json()["detail"] == "You do not have the 'payment:release' permission"
    assert cancel.status_code == 403


async def test_an_invoice_paid_elsewhere_before_release_stops_the_whole_run(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    run, invoices = await _draft_run(client, staff, supplier, product)
    await pay(client, staff.finance, invoices[1]["id"], "100.00")

    response = await _release(client, staff.finance2, run["id"])

    assert response.status_code == 409
    assert "INV-1 changed after the run was created" in response.json()["detail"]
    assert (await get_invoice(client, staff.finance, invoices[0]["id"]))["status"] == "approved"
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 1
    assert (await client.get(f"{RUNS}/{run['id']}", headers=staff.finance)).json()["status"] == "draft"


async def test_a_partial_payment_elsewhere_changes_the_open_amount_and_blocks_release(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run, invoices = await _draft_run(client, staff, supplier, product)
    await pay(client, staff.finance, invoices[0]["id"], "10.00")

    response = await _release(client, staff.finance2, run["id"])

    assert response.status_code == 409


@pytest.mark.parametrize("change", ["hold", "void"])
async def test_an_invoice_held_or_voided_after_the_run_was_created_blocks_release(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, change: str
) -> None:
    run, invoices = await _draft_run(client, staff, supplier, product, count=1)
    await client.post(f"{INVOICES}/{invoices[0]['id']}/{change}", json={"reason": "Dispute"}, headers=staff.finance)

    response = await _release(client, staff.finance2, run["id"])

    assert response.status_code == 409


async def test_a_run_cannot_be_released_twice_or_after_cancelling(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    released, _ = await _draft_run(client, staff, supplier, product, count=1)
    await _release(client, staff.finance2, released["id"])
    cancelled, _ = await _draft_run(client, staff, supplier, product, count=1, prefix="B")
    await client.post(f"{RUNS}/{cancelled['id']}/cancel", headers=staff.finance)

    again = await _release(client, staff.finance2, released["id"])
    after_cancel = await _release(client, staff.finance2, cancelled["id"])

    assert again.status_code == 409
    assert again.json()["detail"] == "Cannot release a payment run that is 'released'"
    assert after_cancel.status_code == 409


async def test_a_draft_run_can_be_cancelled_and_a_released_one_cannot(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    draft, invoices = await _draft_run(client, staff, supplier, product, count=1)
    released, _ = await _draft_run(client, staff, supplier, product, count=1, prefix="B")
    await _release(client, staff.finance2, released["id"])

    cancel = await client.post(f"{RUNS}/{draft['id']}/cancel", headers=staff.finance)
    cancel_released = await client.post(f"{RUNS}/{released['id']}/cancel", headers=staff.finance)
    again = await client.post(f"{RUNS}/{draft['id']}/cancel", headers=staff.finance)

    assert cancel.json()["status"] == "cancelled"
    assert cancel_released.status_code == 409
    assert again.status_code == 409
    assert (await get_invoice(client, staff.finance, invoices[0]["id"]))["status"] == "approved"


async def test_two_simultaneous_releases_pay_each_invoice_once(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    run, _ = await _draft_run(client, staff, supplier, product)

    responses = await asyncio.wait_for(
        asyncio.gather(
            _release(client, staff.finance2, run["id"]),
            _release(client, staff.admin, run["id"]),
        ),
        timeout=OPERATION_TIMEOUT_SECONDS,
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 2


async def test_runs_are_listed_newest_first_and_filtered_by_status(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    first, _ = await _draft_run(client, staff, supplier, product, count=1)
    second, _ = await _draft_run(client, staff, supplier, product, count=1, prefix="B")
    await _release(client, staff.finance2, first["id"])

    everything = (await client.get(RUNS, headers=staff.finance)).json()
    released = (await client.get(RUNS, params={"status": "released"}, headers=staff.finance)).json()
    one = (await client.get(f"{RUNS}/{second['id']}", headers=staff.finance)).json()

    assert [row["id"] for row in everything["items"]] == [second["id"], first["id"]]
    assert [row["id"] for row in released["items"]] == [first["id"]]
    assert one["items"][0]["invoice_number"] == "B-0"


async def test_reading_runs_needs_the_invoice_read_permission_and_sign_in(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    run, _ = await _draft_run(client, staff, supplier, product, count=1)

    assert (await client.get(RUNS, headers=staff.viewer)).status_code == 403
    assert (await client.get(f"{RUNS}/{run['id']}", headers=staff.warehouse)).status_code == 403
    assert (await client.get(f"{RUNS}/{run['id']}", headers=staff.officer)).status_code == 200
    assert (await client.get(RUNS)).status_code == 401
    assert (await client.post(RUNS, json={"invoice_ids": [1]})).status_code == 401
    assert (await client.post(f"{RUNS}/1/release")).status_code == 401


async def test_an_unknown_run_is_not_found(client: AsyncClient, staff: Staff) -> None:
    assert (await client.get(f"{RUNS}/99999", headers=staff.finance)).status_code == 404
    assert (await _release(client, staff.finance2, 99999)).status_code == 404
    assert (await client.post(f"{RUNS}/99999/cancel", headers=staff.finance)).status_code == 404


async def test_creating_releasing_and_cancelling_a_run_are_audited(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    released, _ = await _draft_run(client, staff, supplier, product, count=1)
    await _release(client, staff.finance2, released["id"])
    cancelled, _ = await _draft_run(client, staff, supplier, product, count=1, prefix="B")
    await client.post(f"{RUNS}/{cancelled['id']}/cancel", headers=staff.finance)

    actions = (
        await db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_type == "payment_run").order_by(AuditLog.id)
        )
    ).all()

    assert list(actions) == [
        "payment_run_created",
        "payment_run_released",
        "payment_run_created",
        "payment_run_cancelled",
    ]
