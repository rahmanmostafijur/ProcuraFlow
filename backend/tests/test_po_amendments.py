from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from tests.fixture_types import AuthHeaders
from tests.flow_helpers import API, approval_steps, approve_po, draft_po, get_po, queue

PO_URL = f"{API}/purchase-orders"


async def _ordered(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    supplier: Supplier,
    product: Product,
    *,
    quantity: int = 10,
    unit_price: str = "10.00",
    **extra: Any,
) -> dict[str, Any]:
    """A purchase order that has been approved and sent to the supplier."""
    # Its own people, so a test can sign in as an officer or manager of its own without clashing with them.
    officer = await auth_headers("purchasing_officer", email="orderer@example.com")
    manager = await auth_headers("procurement_manager", email="orderer-approver@example.com")
    po = await draft_po(client, officer, supplier, product, quantity=quantity, unit_price=unit_price, **extra)
    await client.post(f"{PO_URL}/{po['id']}/submit", headers=officer)
    assert (await approve_po(client, manager, po["id"])).status_code == 200
    ordered = await client.post(f"{PO_URL}/{po['id']}/order", headers=officer)
    assert ordered.status_code == 200, ordered.text
    return dict(ordered.json())


async def _amend(client: AsyncClient, headers: dict[str, str], po_id: int, **fields: Any) -> Response:
    return await client.post(
        f"{PO_URL}/{po_id}/amend", json={"reason": "Supplier asked for a change", **fields}, headers=headers
    )


def _lines(product: Product, quantity: int, unit_price: str = "10.00") -> list[dict[str, Any]]:
    return [{"product_id": product.id, "quantity": quantity, "unit_price": unit_price}]


async def test_a_change_that_does_not_raise_the_total_is_applied_straight_away(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    po = await _ordered(client, auth_headers, supplier, product)

    response = await _amend(client, officer, po["id"], items=_lines(product, 8))

    assert response.status_code == 201
    body = response.json()
    assert (body["version"], body["status"], body["reason"]) == (2, "applied", "Supplier asked for a change")
    current = await get_po(client, officer, po["id"])
    assert (current["version"], current["grand_total"], current["base_grand_total"]) == (2, "80.00", "80.00")
    assert current["items"][0]["quantity"] == 8
    assert current["status"] == "ordered"
    deliveries = (await client.get(f"{API}/deliveries", headers=officer)).json()["items"]
    assert [d["ordered_quantity"] for d in deliveries if d["po_id"] == po["id"]] == [8]


async def test_the_version_history_has_the_original_and_a_readable_diff(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    viewer = await auth_headers("viewer")
    po = await _ordered(client, auth_headers, supplier, product)
    await _amend(
        client,
        officer,
        po["id"],
        items=_lines(product, 8, "9.50"),
        notes="Smaller batch",
        expected_delivery_date="2027-01-15",
    )

    versions = (await client.get(f"{PO_URL}/{po['id']}/versions", headers=viewer)).json()

    assert [(v["version"], v["status"]) for v in versions] == [(1, "applied"), (2, "applied")]
    assert versions[0]["reason"] == "Order as first approved"
    assert versions[0]["changes"] == []
    assert versions[0]["snapshot"]["grand_total"] == "100.00"
    changes = {(c["kind"], c.get("field") or c.get("label")): c for c in versions[1]["changes"]}
    assert changes[("field", "notes")]["to"] == "Smaller batch"
    assert changes[("field", "expected_delivery_date")]["to"] == "2027-01-15"
    line = changes[("line_changed", "Test Widget (TEST-001)")]
    assert {(c["field"], c["from"], c["to"]) for c in line["changes"]} == {
        ("quantity", 10, 8),
        ("unit_price", "10.00", "9.50"),
    }
    assert (changes[("total", "Total")]["from"], changes[("total", "Total")]["to"]) == ("100.00", "76.00")
    assert versions[1]["created_by_person"]["full_name"] == "Purchasing_Officer User"


async def test_a_change_that_raises_the_total_waits_for_approval_and_leaves_the_order_alone(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    po = await _ordered(client, auth_headers, supplier, product)

    proposed = await _amend(client, officer, po["id"], items=_lines(product, 15))
    unchanged = await get_po(client, officer, po["id"])
    waiting = await queue(client, manager)
    steps = await approval_steps(client, manager, "purchase_order_amendment", proposed.json()["id"])

    assert proposed.status_code == 201
    assert proposed.json()["status"] == "pending_approval"
    assert (unchanged["version"], unchanged["grand_total"], unchanged["items"][0]["quantity"]) == (1, "100.00", 10)
    assert [(item["document_type"], item["label"]) for item in waiting["items"]] == [
        ("purchase_order_amendment", f"{po['po_number']} v2")
    ]
    assert waiting["items"][0]["amount_base"] == "150.00"
    assert waiting["items"][0]["po_id"] == po["id"]
    assert [(s["status"], s["required_permission"]) for s in steps] == [("pending", "po:approve")]


async def test_approving_an_increase_applies_it_with_the_original_exchange_rate(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    today = utc_today()
    await client.post(
        f"{API}/exchange-rates",
        json={"currency_code": "EUR", "rate": "1.1", "effective_date": (today - timedelta(days=2)).isoformat()},
        headers=finance,
    )
    po = await _ordered(client, auth_headers, supplier, product, currency_code="EUR")
    proposed = await _amend(client, officer, po["id"], items=_lines(product, 20))
    # A newer rate must not leak into an order that locked its rate when it was approved.
    await client.post(
        f"{API}/exchange-rates",
        json={"currency_code": "EUR", "rate": "2", "effective_date": today.isoformat()},
        headers=finance,
    )

    approved = await client.post(f"{API}/po-amendments/{proposed.json()['id']}/approve", headers=manager)
    current = await get_po(client, officer, po["id"])

    assert approved.status_code == 200
    assert approved.json()["status"] == "applied"
    assert (current["version"], current["grand_total"], current["currency_code"]) == (2, "200.00", "EUR")
    assert Decimal(current["exchange_rate"]) == Decimal("1.1")
    assert current["base_grand_total"] == "220.00"


async def test_the_person_who_proposed_an_amendment_cannot_approve_it(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    po = await _ordered(client, auth_headers, supplier, product)
    proposed = await _amend(client, officer, po["id"], items=_lines(product, 15))

    response = await client.post(f"{API}/po-amendments/{proposed.json()['id']}/approve", headers=officer)

    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot approve an amendment you created."


async def test_a_role_that_cannot_approve_orders_cannot_approve_an_amendment(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    other_officer = await auth_headers("purchasing_officer", email="officer2@example.com")
    po = await _ordered(client, auth_headers, supplier, product)
    proposed = await _amend(client, officer, po["id"], items=_lines(product, 15))

    response = await client.post(f"{API}/po-amendments/{proposed.json()['id']}/approve", headers=other_officer)

    assert response.status_code == 403
    assert "po:approve" in response.json()["detail"]


async def test_a_rejected_increase_leaves_the_order_as_it_was_and_a_new_one_can_be_proposed(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    po = await _ordered(client, auth_headers, supplier, product)
    proposed = await _amend(client, officer, po["id"], items=_lines(product, 15))

    rejected = await client.post(
        f"{API}/po-amendments/{proposed.json()['id']}/reject", json={"comment": "Too expensive"}, headers=manager
    )
    again = await _amend(client, officer, po["id"], items=_lines(product, 12))
    current = await get_po(client, officer, po["id"])

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert again.status_code == 201
    assert again.json()["version"] == 3
    assert (current["version"], current["grand_total"]) == (1, "100.00")


async def test_only_one_amendment_can_wait_at_a_time_and_the_proposer_can_withdraw_it(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    other_officer = await auth_headers("purchasing_officer", email="officer2@example.com")
    po = await _ordered(client, auth_headers, supplier, product)
    first = await _amend(client, officer, po["id"], items=_lines(product, 15))

    second = await _amend(client, officer, po["id"], items=_lines(product, 16))
    withdrawn_by_other = await client.post(f"{API}/po-amendments/{first.json()['id']}/withdraw", headers=other_officer)
    withdrawn = await client.post(f"{API}/po-amendments/{first.json()['id']}/withdraw", headers=officer)
    withdrawn_twice = await client.post(f"{API}/po-amendments/{first.json()['id']}/withdraw", headers=officer)
    after = await _amend(client, officer, po["id"], items=_lines(product, 16))

    assert second.status_code == 409
    assert withdrawn_by_other.status_code == 403
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "rejected"
    assert withdrawn_twice.status_code == 409
    assert after.status_code == 201


async def test_cancelling_the_order_closes_a_waiting_amendment(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    po = await _ordered(client, auth_headers, supplier, product)
    proposed = await _amend(client, officer, po["id"], items=_lines(product, 15))

    await client.post(f"{PO_URL}/{po['id']}/cancel", headers=officer)
    versions = (await client.get(f"{PO_URL}/{po['id']}/versions", headers=officer)).json()
    approve = await client.post(f"{API}/po-amendments/{proposed.json()['id']}/approve", headers=manager)

    assert versions[-1]["status"] == "rejected"
    assert approve.status_code == 409
    assert (await queue(client, manager))["total"] == 0


@pytest.mark.parametrize("status", ["draft", "submitted", "cancelled"])
async def test_only_a_placed_order_can_be_amended(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product, status: str
) -> None:
    officer = await auth_headers("purchasing_officer")
    po = await draft_po(client, officer, supplier, product)
    if status in {"submitted", "cancelled"}:
        await client.post(f"{PO_URL}/{po['id']}/submit", headers=officer)
    if status == "cancelled":
        await client.post(f"{PO_URL}/{po['id']}/cancel", headers=officer)

    response = await _amend(client, officer, po["id"], items=_lines(product, 5))

    assert response.status_code == 409


async def test_amending_needs_the_transition_permission(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    po = await _ordered(client, auth_headers, supplier, product)
    viewer = await auth_headers("viewer")
    warehouse = await auth_headers("warehouse_manager")

    assert (await _amend(client, viewer, po["id"], items=_lines(product, 5))).status_code == 403
    assert (await _amend(client, warehouse, po["id"], items=_lines(product, 5))).status_code == 403
    assert (await client.post(f"{PO_URL}/{po['id']}/amend", json={"reason": "x"})).status_code == 401


async def test_an_amendment_needs_a_reason_and_a_real_change(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    po = await _ordered(client, auth_headers, supplier, product)

    no_reason = await client.post(f"{PO_URL}/{po['id']}/amend", json={"items": _lines(product, 5)}, headers=officer)
    blank_reason = await client.post(
        f"{PO_URL}/{po['id']}/amend", json={"reason": "  ", "items": _lines(product, 5)}, headers=officer
    )
    no_change = await _amend(client, officer, po["id"], items=_lines(product, 10))
    nothing_at_all = await _amend(client, officer, po["id"])

    assert no_reason.status_code == 422
    assert blank_reason.status_code == 422
    assert no_change.status_code == 422
    assert nothing_at_all.status_code == 422


async def test_lines_that_were_received_cannot_be_removed_or_cut_below_what_arrived(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    supplier: Supplier,
    product: Product,
) -> None:
    officer = await auth_headers("purchasing_officer")
    warehouse = await auth_headers("warehouse_manager")
    other = Product(sku="TEST-002", name="Second Widget", cost=5, minimum_stock=1, supplier_id=supplier.id)
    db_session.add(other)
    await db_session.commit()
    po = await _ordered(client, auth_headers, supplier, product)
    await client.post(
        f"{PO_URL}/{po['id']}/receive", json={"items": [{"product_id": product.id, "quantity": 4}]}, headers=warehouse
    )

    below_received = await _amend(client, officer, po["id"], items=_lines(product, 3))
    removed = await _amend(client, officer, po["id"], items=_lines(other, 5))
    to_what_arrived = await _amend(client, officer, po["id"], items=_lines(product, 4))
    grown_with_new_line = await _amend(
        client,
        officer,
        po["id"],
        items=[*_lines(product, 10), {"product_id": other.id, "quantity": 2, "unit_price": "5.00"}],
    )

    assert below_received.status_code == 422
    assert "cannot be reduced below the 4 already received" in below_received.json()["detail"]
    assert removed.status_code == 422
    assert "cannot be removed" in removed.json()["detail"]
    assert to_what_arrived.status_code == 422
    assert grown_with_new_line.status_code == 201
    assert grown_with_new_line.json()["status"] == "pending_approval"


async def test_received_quantities_survive_an_amendment(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    warehouse = await auth_headers("warehouse_manager")
    po = await _ordered(client, auth_headers, supplier, product)
    await client.post(
        f"{PO_URL}/{po['id']}/receive", json={"items": [{"product_id": product.id, "quantity": 4}]}, headers=warehouse
    )

    await _amend(client, officer, po["id"], items=_lines(product, 6, "10.00"))
    current = await get_po(client, officer, po["id"])

    assert current["status"] == "partially_received"
    assert [(i["quantity"], i["received_quantity"]) for i in current["items"]] == [(6, 4)]


async def test_an_increase_that_breaks_a_blocking_budget_cannot_be_approved(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    admin = await auth_headers("admin")
    finance = await auth_headers("finance")
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    centre = (
        await client.post(f"{API}/cost-centres", json={"code": "MKT", "name": "Marketing"}, headers=finance)
    ).json()
    await client.put(
        f"{API}/budgets",
        json={"cost_centre_id": centre["id"], "fiscal_year": utc_today().year, "amount": "150"},
        headers=finance,
    )
    await client.patch(f"{API}/company-settings", json={"budget_block_over_budget": True}, headers=admin)
    po = await _ordered(client, auth_headers, supplier, product, cost_centre_id=centre["id"])
    # 100 committed, 50 left: a 30 increase fits; after it only 20 is left, so a 70 increase does not.
    fits = await _amend(client, officer, po["id"], items=_lines(product, 13))
    approved_fit = await client.post(f"{API}/po-amendments/{fits.json()['id']}/approve", headers=manager)
    too_much = await _amend(client, officer, po["id"], items=_lines(product, 20))
    refused = await client.post(f"{API}/po-amendments/{too_much.json()['id']}/approve", headers=manager)

    assert approved_fit.status_code == 200
    assert refused.status_code == 409
    assert "over its" in refused.json()["detail"]
    assert (await get_po(client, officer, po["id"]))["grand_total"] == "130.00"


async def test_amendments_are_audited(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier, product: Product
) -> None:
    officer = await auth_headers("purchasing_officer")
    manager = await auth_headers("procurement_manager")
    po = await _ordered(client, auth_headers, supplier, product)
    await _amend(client, officer, po["id"], items=_lines(product, 8))
    proposed = await _amend(client, officer, po["id"], items=_lines(product, 30))
    await client.post(f"{API}/po-amendments/{proposed.json()['id']}/approve", headers=manager)

    actions = (await db_session.scalars(select(AuditLog.action).where(AuditLog.entity_id == po["id"]))).all()

    assert actions.count("po_amended") == 2
    assert actions.count("po_amendment_submitted") == 1


async def test_versions_require_sign_in_and_an_existing_order(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    viewer = await auth_headers("viewer")

    assert (await client.get(f"{PO_URL}/1/versions")).status_code == 401
    assert (await client.get(f"{PO_URL}/99999/versions", headers=viewer)).status_code == 404
    assert (await client.post(f"{API}/po-amendments/99999/approve", headers=viewer)).status_code == 404
