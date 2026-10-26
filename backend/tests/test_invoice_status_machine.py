from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from tests.invoice_helpers import (
    INVOICES,
    Staff,
    approved_invoice,
    create_invoice,
    get_invoice,
    invoice_body,
    matched_invoice,
    pay,
    received_po,
    submit_invoice,
)

# --- approval of a matched invoice ----------------------------------------------------------------------------------


async def test_finance_approves_a_matched_invoice_and_the_exchange_rate_is_locked(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    response = await client.post(f"{INVOICES}/{invoice['id']}/approve", headers=staff.finance)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "approved"
    assert body["approver"]["full_name"] == "Finance User"
    assert body["approved_at"] is not None
    assert body["exchange_rate"] == "1.00000000"
    assert body["base_grand_total"] == "100.00"


async def test_the_person_who_recorded_an_invoice_cannot_approve_it(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.finance, invoice_body(po, product))
    await submit_invoice(client, staff.finance, invoice["id"])

    own = await client.post(f"{INVOICES}/{invoice['id']}/approve", headers=staff.finance)
    other = await client.post(f"{INVOICES}/{invoice['id']}/approve", headers=staff.finance2)

    assert own.status_code == 403
    assert own.json()["detail"] == "You cannot approve an invoice you created."
    assert other.status_code == 200


async def test_someone_without_the_approve_permission_cannot_approve_a_matched_invoice(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    response = await client.post(f"{INVOICES}/{invoice['id']}/approve", headers=staff.manager)

    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have the 'invoice:approve' permission"


async def test_rejecting_a_matched_invoice_sends_it_back_to_draft_with_the_reason(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    response = await client.post(
        f"{INVOICES}/{invoice['id']}/reject", json={"comment": "Wrong PO reference"}, headers=staff.finance
    )
    edit = await client.patch(f"{INVOICES}/{invoice['id']}", json={"notes": "fixed"}, headers=staff.officer)

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert response.json()["rejection_reason"] == "Wrong PO reference"
    assert edit.status_code == 200


async def test_a_rejection_needs_a_reason(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    response = await client.post(f"{INVOICES}/{invoice['id']}/reject", json={"comment": " "}, headers=staff.finance)

    assert response.status_code == 422


async def test_approval_does_not_change_any_budget(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)
    before = (await client.get("/api/v1/dashboard/summary", headers=staff.viewer)).json()

    await client.post(f"{INVOICES}/{invoice['id']}/approve", headers=staff.finance)
    after = (await client.get("/api/v1/dashboard/summary", headers=staff.viewer)).json()

    for field in ("total_purchase_orders", "pending_orders", "completed_orders", "inventory_value"):
        assert after[field] == before[field]


# --- hold, release and void ------------------------------------------------------------------------------------------


async def test_an_approved_invoice_on_hold_returns_to_approved_on_release(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await approved_invoice(client, staff, po, product)

    held = await client.post(f"{INVOICES}/{invoice['id']}/hold", json={"reason": "Disputed"}, headers=staff.finance)
    blocked = await pay(client, staff.finance, invoice["id"], "10.00")
    released = await client.post(f"{INVOICES}/{invoice['id']}/release", headers=staff.finance)

    assert held.json()["status"] == "on_hold"
    assert held.json()["hold_reason"] == "Disputed"
    assert blocked.status_code == 409
    assert released.json()["status"] == "approved"
    assert released.json()["hold_reason"] is None


async def test_a_matched_invoice_returns_to_matched_on_release(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    await client.post(f"{INVOICES}/{invoice['id']}/hold", json={"reason": "Check"}, headers=staff.finance)
    released = await client.post(f"{INVOICES}/{invoice['id']}/release", headers=staff.finance)

    assert released.json()["status"] == "matched"


async def test_holding_and_releasing_need_the_approve_permission(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    hold = await client.post(f"{INVOICES}/{invoice['id']}/hold", json={"reason": "x"}, headers=staff.officer)
    release = await client.post(f"{INVOICES}/{invoice['id']}/release", headers=staff.officer)

    assert hold.status_code == 403
    assert release.status_code == 403


async def test_a_hold_needs_a_reason(client: AsyncClient, staff: Staff, supplier: Supplier, product: Product) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await matched_invoice(client, staff, po, product)

    response = await client.post(f"{INVOICES}/{invoice['id']}/hold", json={"reason": ""}, headers=staff.finance)

    assert response.status_code == 422


async def test_a_voided_invoice_keeps_its_reason_and_cannot_be_edited_or_paid(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    voided = await client.post(f"{INVOICES}/{invoice['id']}/void", json={"reason": "Duplicate"}, headers=staff.officer)
    edit = await client.patch(f"{INVOICES}/{invoice['id']}", json={"notes": "x"}, headers=staff.officer)

    assert voided.json()["status"] == "void"
    assert voided.json()["void_reason"] == "Duplicate"
    assert edit.status_code == 409


async def test_a_void_needs_a_reason(client: AsyncClient, staff: Staff, supplier: Supplier, product: Product) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await create_invoice(client, staff.officer, invoice_body(po, product))

    response = await client.post(f"{INVOICES}/{invoice['id']}/void", json={"reason": "  "}, headers=staff.officer)

    assert response.status_code == 422


async def test_an_invoice_with_payments_cannot_be_voided(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await approved_invoice(client, staff, po, product)
    await pay(client, staff.finance, invoice["id"], "10.00")

    response = await client.post(f"{INVOICES}/{invoice['id']}/void", json={"reason": "Oops"}, headers=staff.finance)

    assert response.status_code == 409
    assert response.json()["detail"] == "An invoice with payments cannot be voided"


async def test_the_audit_trail_records_every_step_of_an_invoices_life(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    po = await received_po(client, staff, supplier, product)
    invoice = await approved_invoice(client, staff, po, product)
    await client.post(f"{INVOICES}/{invoice['id']}/hold", json={"reason": "Check"}, headers=staff.finance)
    await client.post(f"{INVOICES}/{invoice['id']}/release", headers=staff.finance)
    await client.post(f"{INVOICES}/{invoice['id']}/void", json={"reason": "Mistake"}, headers=staff.finance)

    actions = (
        await db_session.scalars(
            select(AuditLog.action).where(AuditLog.entity_type == "supplier_invoice").order_by(AuditLog.id)
        )
    ).all()

    assert list(actions) == [
        "invoice_created",
        "invoice_submitted",
        "invoice_approved",
        "invoice_held",
        "invoice_released",
        "invoice_voided",
    ]


# --- the full transition matrix -------------------------------------------------------------------------------------

ALLOWED: dict[str, set[str]] = {
    "submit": {"draft"},
    "approve": {"matched", "exception"},
    "reject": {"matched", "exception"},
    "hold": {"approved", "matched", "exception"},
    "release": {"on_hold"},
    "void": {"draft", "matched", "exception", "on_hold", "approved"},
    "pay": {"approved"},
}
STATUSES = ["draft", "matched", "exception", "approved", "on_hold", "paid", "void"]


async def _invoice_in(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, target: str
) -> dict[str, Any]:
    po = await received_po(client, staff, supplier, product)
    if target == "exception":
        invoice = await create_invoice(client, staff.officer, invoice_body(po, product, unit_price="20.00"))
        await submit_invoice(client, staff.officer, invoice["id"])
        return await get_invoice(client, staff.finance, invoice["id"])
    if target in ("draft", "void"):
        invoice = await create_invoice(client, staff.officer, invoice_body(po, product))
        if target == "void":
            await client.post(f"{INVOICES}/{invoice['id']}/void", json={"reason": "x"}, headers=staff.officer)
        return await get_invoice(client, staff.finance, invoice["id"])
    if target == "matched":
        return await matched_invoice(client, staff, po, product)
    invoice = await approved_invoice(client, staff, po, product)
    if target == "on_hold":
        await client.post(f"{INVOICES}/{invoice['id']}/hold", json={"reason": "x"}, headers=staff.finance)
    if target == "paid":
        await pay(client, staff.finance, invoice["id"], "100.00")
    return await get_invoice(client, staff.finance, invoice["id"])


async def _act(client: AsyncClient, staff: Staff, invoice_id: int, action: str) -> Response:
    url = f"{INVOICES}/{invoice_id}"
    if action == "submit":
        return await client.post(f"{url}/submit", headers=staff.finance)
    if action in ("approve", "release"):
        return await client.post(f"{url}/{action}", headers=staff.finance2)
    if action in ("reject", "hold", "void"):
        body = {"comment": "no"} if action == "reject" else {"reason": "no"}
        return await client.post(f"{url}/{action}", json=body, headers=staff.finance2)
    return await pay(client, staff.finance, invoice_id, "1.00")


ILLEGAL = [(state, action) for state in STATUSES for action in ALLOWED if state not in ALLOWED[action]]


@pytest.mark.parametrize(("state", "action"), ILLEGAL)
async def test_every_illegal_transition_is_a_conflict(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, state: str, action: str
) -> None:
    invoice = await _invoice_in(client, staff, supplier, product, state)
    assert invoice["status"] == state

    response = await _act(client, staff, invoice["id"], action)

    assert response.status_code == 409, response.text
    assert (await get_invoice(client, staff.finance, invoice["id"]))["status"] == state
