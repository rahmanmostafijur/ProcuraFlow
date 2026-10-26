from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from tests.invoice_helpers import RETURNS, Staff, ordered_po, receive


async def _po_with_rejections(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, rejected: int = 4
) -> dict[str, Any]:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 10, rejected=rejected, condition="damaged")
    return po


def _body(po: dict[str, Any], product: Product, quantity: int = 2, **extra: Any) -> dict[str, Any]:
    return {
        "po_id": po["id"],
        "product_id": product.id,
        "quantity": quantity,
        "reason": "Cracked housing",
        "resolution": "credit_note",
        **extra,
    }


async def _return(client: AsyncClient, staff: Staff, po: dict[str, Any], product: Product, **kwargs: Any) -> Response:
    return await client.post(RETURNS, json=_body(po, product, **kwargs), headers=staff.warehouse)


async def _move(client: AsyncClient, staff: Staff, return_id: int, target: str) -> Response:
    return await client.post(f"{RETURNS}/{return_id}/status", json={"status": target}, headers=staff.warehouse)


async def test_a_return_is_created_from_rejected_units(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product)

    response = await _return(client, staff, po, product, quantity=3)

    body = response.json()
    assert response.status_code == 201
    assert (body["status"], body["quantity"], body["resolution"]) == ("open", 3, "credit_note")
    assert body["po_number"] == po["po_number"]
    assert body["supplier_name"] == supplier.name
    assert body["product_sku"] == product.sku
    assert body["created_by"]["full_name"] == "Warehouse_Manager User"
    assert body["resolved_at"] is None


async def test_returns_cannot_exceed_the_rejected_units_not_yet_returned(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product, rejected=4)
    await _return(client, staff, po, product, quantity=3)

    too_many = await _return(client, staff, po, product, quantity=2)
    exact = await _return(client, staff, po, product, quantity=1)

    assert too_many.status_code == 422
    assert "only 1 rejected units are not yet returned" in too_many.json()["detail"]
    assert exact.status_code == 201


async def test_nothing_can_be_returned_when_nothing_was_rejected(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await ordered_po(client, staff, supplier, product)
    await receive(client, staff, po["id"], product, 10)

    response = await _return(client, staff, po, product, quantity=1)

    assert response.status_code == 422


async def test_a_cancelled_return_frees_its_units_again(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product, rejected=4)
    first = (await _return(client, staff, po, product, quantity=4)).json()

    await _move(client, staff, first["id"], "cancelled")
    again = await _return(client, staff, po, product, quantity=4)

    assert again.status_code == 201


async def test_a_resolved_return_keeps_its_units_claimed(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product, rejected=4)
    first = (await _return(client, staff, po, product, quantity=4)).json()
    await _move(client, staff, first["id"], "sent")
    await _move(client, staff, first["id"], "resolved")

    again = await _return(client, staff, po, product, quantity=1)

    assert again.status_code == 422


async def test_a_return_moves_forward_and_records_when_it_was_resolved(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product)
    created = (await _return(client, staff, po, product)).json()

    sent = await _move(client, staff, created["id"], "sent")
    resolved = await client.post(
        f"{RETURNS}/{created['id']}/status",
        json={"status": "resolved", "note": "Credit note CN-7 received"},
        headers=staff.warehouse,
    )

    assert sent.json()["status"] == "sent"
    assert sent.json()["resolved_at"] is None
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None
    assert resolved.json()["note"] == "Credit note CN-7 received"
    actions = (await db_session.scalars(select(AuditLog.action).where(AuditLog.entity_type == "supplier_return"))).all()
    assert actions.count("supplier_return_status_changed") == 2
    assert "supplier_return_created" in actions


@pytest.mark.parametrize(
    ("path", "target"),
    [
        (["sent"], "open"),
        ([], "resolved"),
        (["sent", "resolved"], "sent"),
        (["sent", "resolved"], "cancelled"),
        (["cancelled"], "sent"),
        (["cancelled"], "open"),
        ([], "open"),
    ],
)
async def test_illegal_status_changes_are_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, path: list[str], target: str
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product)
    created = (await _return(client, staff, po, product)).json()
    for step in path:
        assert (await _move(client, staff, created["id"], step)).status_code == 200

    response = await _move(client, staff, created["id"], target)

    assert response.status_code == 409
    assert "Cannot move a return from" in response.json()["detail"]


async def test_a_sent_return_can_still_be_cancelled(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product)
    created = (await _return(client, staff, po, product)).json()
    await _move(client, staff, created["id"], "sent")

    response = await _move(client, staff, created["id"], "cancelled")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


async def test_returns_are_listed_and_filtered_by_status_order_and_supplier(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, db_session: AsyncSession
) -> None:
    other_supplier = Supplier(name="Other Supplier")
    db_session.add(other_supplier)
    await db_session.flush()
    other_product = Product(sku="OTH-1", name="Other", cost=1, minimum_stock=0, supplier_id=other_supplier.id)
    db_session.add(other_product)
    await db_session.commit()
    po_one = await _po_with_rejections(client, staff, supplier, product)
    po_two = await _po_with_rejections(client, staff, other_supplier, other_product)
    first = (await _return(client, staff, po_one, product)).json()
    await _return(client, staff, po_two, other_product)
    await _move(client, staff, first["id"], "sent")

    everything = (await client.get(RETURNS, headers=staff.viewer)).json()
    sent = (await client.get(RETURNS, params={"status": "sent"}, headers=staff.viewer)).json()
    by_order = (await client.get(RETURNS, params={"po_id": po_two["id"]}, headers=staff.viewer)).json()
    by_supplier = (await client.get(RETURNS, params={"supplier_id": supplier.id}, headers=staff.viewer)).json()

    assert everything["total"] == 2
    assert [row["id"] for row in sent["items"]] == [first["id"]]
    assert [row["po_id"] for row in by_order["items"]] == [po_two["id"]]
    assert [row["id"] for row in by_supplier["items"]] == [first["id"]]


async def test_any_signed_in_user_can_read_a_return(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product)
    created = (await _return(client, staff, po, product)).json()

    response = await client.get(f"{RETURNS}/{created['id']}", headers=staff.viewer)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_an_unknown_return_is_not_found(client: AsyncClient, staff: Staff) -> None:
    assert (await client.get(f"{RETURNS}/9999", headers=staff.viewer)).status_code == 404
    assert (await _move(client, staff, 9999, "sent")).status_code == 404


async def test_writing_returns_needs_the_inventory_permission(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product)
    created = (await _return(client, staff, po, product)).json()

    create = await client.post(RETURNS, json=_body(po, product), headers=staff.officer)
    change = await client.post(f"{RETURNS}/{created['id']}/status", json={"status": "sent"}, headers=staff.finance)

    assert create.status_code == 403
    assert change.status_code == 403


async def test_returns_need_sign_in(client: AsyncClient) -> None:
    assert (await client.get(RETURNS)).status_code == 401
    assert (await client.post(RETURNS, json={})).status_code == 401
    assert (await client.post(f"{RETURNS}/1/status", json={"status": "sent"})).status_code == 401


@pytest.mark.parametrize(
    "override",
    [{"quantity": 0}, {"quantity": -1}, {"reason": "  "}, {"resolution": "refund"}, {"reason": "x" * 501}],
)
async def test_invalid_returns_are_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product, override: dict[str, Any]
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product)

    response = await client.post(RETURNS, json={**_body(po, product), **override}, headers=staff.warehouse)

    assert response.status_code == 422


async def test_a_return_for_an_unknown_order_or_product_is_refused(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Product
) -> None:
    po = await _po_with_rejections(client, staff, supplier, product)

    no_order = await client.post(RETURNS, json={**_body(po, product), "po_id": 9999}, headers=staff.warehouse)
    no_product = await client.post(RETURNS, json={**_body(po, product), "product_id": 9999}, headers=staff.warehouse)

    assert no_order.status_code == 404
    assert no_product.status_code == 400
