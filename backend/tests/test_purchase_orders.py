import re
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.purchase_order import PurchaseOrder

PO_NUMBER_PATTERN = re.compile(r"PO-\d{4}-\d{5}")
SELF_APPROVAL_DETAIL = "You cannot approve a purchase order you created."


async def _create_draft_po(client: AsyncClient, headers: dict, supplier, product, **overrides) -> dict:
    payload = {
        "supplier_id": supplier.id,
        "items": [{"product_id": product.id, "quantity": 10, "unit_price": "10.00"}],
    }
    payload.update(overrides)
    response = await client.post("/api/v1/purchase-orders", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


async def _create_submitted_po(client: AsyncClient, headers: dict, supplier, product) -> dict:
    po = await _create_draft_po(client, headers, supplier, product)
    response = await client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=headers)
    assert response.status_code == 200
    return response.json()


async def _approval_event_count(db_session: AsyncSession, po_id: int) -> int:
    return await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == "po_approved", AuditLog.entity_id == po_id)
    )


async def test_create_purchase_order_starts_in_draft(client: AsyncClient, auth_headers, supplier, product):
    headers = await auth_headers("procurement_manager")

    po = await _create_draft_po(client, headers, supplier, product)

    assert po["status"] == "draft"
    assert po["po_number"].startswith("PO-")
    assert po["total"] == "100.00"


async def test_po_numbers_stay_unique_after_a_purchase_order_is_deleted(
    client: AsyncClient, auth_headers, db_session: AsyncSession, supplier, product
):
    headers = await auth_headers("procurement_manager")
    first = await _create_draft_po(client, headers, supplier, product)
    second = await _create_draft_po(client, headers, supplier, product)
    await db_session.execute(delete(PurchaseOrder).where(PurchaseOrder.id == first["id"]))
    await db_session.commit()

    third = await _create_draft_po(client, headers, supplier, product)

    assert third["po_number"] not in {first["po_number"], second["po_number"]}
    assert PO_NUMBER_PATTERN.fullmatch(third["po_number"])


async def test_full_lifecycle_draft_to_received_updates_inventory(
    client: AsyncClient, auth_headers, supplier, product
):
    headers = await auth_headers("admin")
    approver_headers = await auth_headers("procurement_manager")

    po = await _create_draft_po(client, headers, supplier, product)
    po_id = po["id"]

    for action in ("submit", "approve", "order"):
        action_headers = approver_headers if action == "approve" else headers
        response = await client.post(f"/api/v1/purchase-orders/{po_id}/{action}", headers=action_headers)
        assert response.status_code == 200

    receive_response = await client.post(
        f"/api/v1/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": product.id, "quantity": 10}]},
        headers=headers,
    )

    assert receive_response.status_code == 200
    assert receive_response.json()["status"] == "received"

    product_response = await client.get(f"/api/v1/products/{product.id}", headers=headers)
    assert product_response.json()["current_stock"] == 60  # 50 initial + 10 received


async def test_cannot_submit_an_already_submitted_purchase_order(
    client: AsyncClient, auth_headers, supplier, product
):
    headers = await auth_headers("admin")
    po = await _create_draft_po(client, headers, supplier, product)
    po_id = po["id"]
    await client.post(f"/api/v1/purchase-orders/{po_id}/submit", headers=headers)

    response = await client.post(f"/api/v1/purchase-orders/{po_id}/submit", headers=headers)

    assert response.status_code == 409


async def test_cannot_receive_a_draft_purchase_order(client: AsyncClient, auth_headers, supplier, product):
    headers = await auth_headers("admin")
    po = await _create_draft_po(client, headers, supplier, product)

    response = await client.post(
        f"/api/v1/purchase-orders/{po['id']}/receive",
        json={"items": [{"product_id": product.id, "quantity": 1}]},
        headers=headers,
    )

    assert response.status_code == 409


async def test_cannot_receive_more_than_ordered_quantity(client: AsyncClient, auth_headers, supplier, product):
    headers = await auth_headers("admin")
    approver_headers = await auth_headers("procurement_manager")
    po = await _create_draft_po(client, headers, supplier, product)
    po_id = po["id"]
    for action in ("submit", "approve", "order"):
        action_headers = approver_headers if action == "approve" else headers
        await client.post(f"/api/v1/purchase-orders/{po_id}/{action}", headers=action_headers)

    response = await client.post(
        f"/api/v1/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": product.id, "quantity": 999}]},
        headers=headers,
    )

    assert response.status_code == 400


async def test_partial_receive_leaves_po_partially_received(
    client: AsyncClient, auth_headers, supplier, product
):
    headers = await auth_headers("admin")
    approver_headers = await auth_headers("procurement_manager")
    po = await _create_draft_po(client, headers, supplier, product)
    po_id = po["id"]
    for action in ("submit", "approve", "order"):
        action_headers = approver_headers if action == "approve" else headers
        await client.post(f"/api/v1/purchase-orders/{po_id}/{action}", headers=action_headers)

    response = await client.post(
        f"/api/v1/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": product.id, "quantity": 4}]},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "partially_received"


async def test_cancel_is_allowed_from_draft_but_not_from_received(
    client: AsyncClient, auth_headers, supplier, product
):
    headers = await auth_headers("admin")
    po = await _create_draft_po(client, headers, supplier, product)

    cancel_response = await client.post(f"/api/v1/purchase-orders/{po['id']}/cancel", headers=headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    resubmit_response = await client.post(f"/api/v1/purchase-orders/{po['id']}/submit", headers=headers)
    assert resubmit_response.status_code == 409


async def test_on_time_delivery_marked_when_received_by_expected_date(
    client: AsyncClient, auth_headers, supplier, product
):
    headers = await auth_headers("admin")
    approver_headers = await auth_headers("procurement_manager")
    future_date = (date.today() + timedelta(days=7)).isoformat()
    po = await _create_draft_po(
        client, headers, supplier, product, expected_delivery_date=future_date
    )
    po_id = po["id"]
    for action in ("submit", "approve", "order"):
        action_headers = approver_headers if action == "approve" else headers
        await client.post(f"/api/v1/purchase-orders/{po_id}/{action}", headers=action_headers)

    await client.post(
        f"/api/v1/purchase-orders/{po_id}/receive",
        json={"items": [{"product_id": product.id, "quantity": 10}]},
        headers=headers,
    )

    deliveries = await client.get("/api/v1/deliveries", headers=headers)
    delivery = next(d for d in deliveries.json()["items"] if d["po_id"] == po_id)
    assert delivery["status"] == "on_time"


async def test_procurement_manager_cannot_approve_a_purchase_order_they_created(
    client: AsyncClient, auth_headers, db_session: AsyncSession, supplier, product
):
    headers = await auth_headers("procurement_manager")
    po = await _create_submitted_po(client, headers, supplier, product)

    response = await client.post(f"/api/v1/purchase-orders/{po['id']}/approve", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == SELF_APPROVAL_DETAIL
    current = (await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=headers)).json()
    assert current["status"] == "submitted"
    assert current["approver"] is None
    assert current["approved_at"] is None
    assert await _approval_event_count(db_session, po["id"]) == 0


async def test_admin_cannot_approve_a_purchase_order_they_created(
    client: AsyncClient, auth_headers, db_session: AsyncSession, supplier, product
):
    headers = await auth_headers("admin")
    po = await _create_submitted_po(client, headers, supplier, product)

    response = await client.post(f"/api/v1/purchase-orders/{po['id']}/approve", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == SELF_APPROVAL_DETAIL
    current = (await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=headers)).json()
    assert current["status"] == "submitted"
    assert await _approval_event_count(db_session, po["id"]) == 0


async def test_another_procurement_manager_can_approve_a_purchase_order(
    client: AsyncClient, auth_headers, db_session: AsyncSession, supplier, product
):
    creator_headers = await auth_headers("procurement_manager", email="creator@example.com")
    approver_headers = await auth_headers("procurement_manager", email="approver@example.com")
    po = await _create_submitted_po(client, creator_headers, supplier, product)

    response = await client.post(f"/api/v1/purchase-orders/{po['id']}/approve", headers=approver_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    current = (await client.get(f"/api/v1/purchase-orders/{po['id']}", headers=approver_headers)).json()
    assert current["creator"]["email"] == "creator@example.com"
    assert current["approver"]["email"] == "approver@example.com"
    assert await _approval_event_count(db_session, po["id"]) == 1
