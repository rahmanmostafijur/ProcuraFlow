from collections.abc import Callable

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.inventory import InventoryTransaction
from app.models.product import Product
from app.models.supplier import Supplier
from app.services.inventory_service import record_opening_balance

OPENING_BALANCE_URL = "/api/v1/inventory/opening-balance"
ALREADY_HAS_MOVEMENTS_DETAIL = (
    "Product 'NEW-001' already has inventory movements, so it cannot get an opening balance. "
    "Record an adjustment instead."
)


@pytest_asyncio.fixture
async def new_product(db_session: AsyncSession, supplier: Supplier) -> Product:
    product_obj = Product(sku="NEW-001", name="New Widget", cost=5, minimum_stock=0, supplier_id=supplier.id)
    db_session.add(product_obj)
    await db_session.commit()
    await db_session.refresh(product_obj)
    return product_obj


async def _ledger_rows(db_session: AsyncSession, product_id: int) -> list[InventoryTransaction]:
    result = await db_session.execute(
        select(InventoryTransaction)
        .where(InventoryTransaction.product_id == product_id)
        .order_by(InventoryTransaction.id)
    )
    return list(result.scalars())


async def _post_opening_balance(client: AsyncClient, headers: dict, product_id: int, quantity: int) -> Response:
    payload = {"product_id": product_id, "quantity": quantity}
    return await client.post(OPENING_BALANCE_URL, json=payload, headers=headers)


async def _product_stock(client: AsyncClient, headers: dict, product_id: int) -> int:
    response = await client.get(f"/api/v1/products/{product_id}", headers=headers)
    return response.json()["current_stock"]


async def test_create_product_rejects_current_stock(client: AsyncClient, auth_headers, db_session: AsyncSession):
    headers = await auth_headers("procurement_manager")

    response = await client.post(
        "/api/v1/products",
        json={"sku": "STK-001", "name": "Stocked Widget", "cost": "1.00", "current_stock": 25},
        headers=headers,
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert [(error["type"], error["loc"]) for error in errors] == [("extra_forbidden", ["body", "current_stock"])]
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 0


async def test_created_product_starts_with_zero_stock(
    client: AsyncClient, auth_headers, assert_stock_matches_ledger
):
    headers = await auth_headers("procurement_manager")

    response = await client.post(
        "/api/v1/products", json={"sku": "STK-002", "name": "Empty Widget", "cost": "1.00"}, headers=headers
    )

    assert response.status_code == 201
    assert response.json()["current_stock"] == 0
    await assert_stock_matches_ledger(response.json()["id"])


async def test_warehouse_manager_records_opening_balance(
    client: AsyncClient, auth_headers, db_session: AsyncSession, new_product, assert_stock_matches_ledger
):
    headers = await auth_headers("warehouse_manager")

    response = await client.post(
        OPENING_BALANCE_URL,
        json={"product_id": new_product.id, "quantity": 40, "reason": "Stock take at go-live"},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "opening_balance"
    assert body["product_id"] == new_product.id
    assert body["quantity_delta"] == 40
    assert body["resulting_stock"] == 40
    assert body["reason"] == "Stock take at go-live"
    assert await _product_stock(client, headers, new_product.id) == 40
    await assert_stock_matches_ledger(new_product.id)

    audit_event = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "inventory_opening_balance", AuditLog.entity_id == new_product.id)
    )
    assert audit_event is not None
    assert audit_event.entity_type == "product"
    assert audit_event.user_id == body["created_by"]
    assert audit_event.extra_data == {"quantity": 40, "reason": "Stock take at go-live"}


async def test_opening_balance_reason_is_optional(client: AsyncClient, auth_headers, new_product):
    headers = await auth_headers("warehouse_manager")

    response = await _post_opening_balance(client, headers, new_product.id, 5)

    assert response.status_code == 201
    assert response.json()["reason"] is None


@pytest.mark.parametrize("role_name", ["procurement_manager", "viewer"])
async def test_opening_balance_requires_inventory_write(
    client: AsyncClient, auth_headers, db_session: AsyncSession, new_product, role_name: str
):
    headers = await auth_headers(role_name)

    response = await _post_opening_balance(client, headers, new_product.id, 40)

    assert response.status_code == 403
    assert await _product_stock(client, headers, new_product.id) == 0
    assert await _ledger_rows(db_session, new_product.id) == []


async def test_second_opening_balance_is_rejected(
    client: AsyncClient, auth_headers, db_session: AsyncSession, new_product, assert_stock_matches_ledger
):
    headers = await auth_headers("warehouse_manager")
    first = await _post_opening_balance(client, headers, new_product.id, 40)
    assert first.status_code == 201

    second = await _post_opening_balance(client, headers, new_product.id, 15)

    assert second.status_code == 409
    assert second.json() == {"detail": ALREADY_HAS_MOVEMENTS_DETAIL}
    assert await _product_stock(client, headers, new_product.id) == 40
    assert len(await _ledger_rows(db_session, new_product.id)) == 1
    await assert_stock_matches_ledger(new_product.id)


async def test_opening_balance_is_rejected_after_any_other_movement(
    client: AsyncClient, auth_headers, new_product, assert_stock_matches_ledger
):
    headers = await auth_headers("warehouse_manager")
    adjustment = await client.post(
        "/api/v1/inventory/adjustments",
        json={"product_id": new_product.id, "quantity_delta": 5, "reason": "Found in back room"},
        headers=headers,
    )
    assert adjustment.status_code == 201

    response = await _post_opening_balance(client, headers, new_product.id, 40)

    assert response.status_code == 409
    assert response.json() == {"detail": ALREADY_HAS_MOVEMENTS_DETAIL}
    assert await _product_stock(client, headers, new_product.id) == 5
    await assert_stock_matches_ledger(new_product.id)


@pytest.mark.parametrize("quantity", [0, -5])
async def test_opening_balance_quantity_must_be_positive(
    client: AsyncClient, auth_headers, db_session: AsyncSession, new_product, quantity: int
):
    headers = await auth_headers("warehouse_manager")

    response = await _post_opening_balance(client, headers, new_product.id, quantity)

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["detail"]] == [["body", "quantity"]]
    assert await _ledger_rows(db_session, new_product.id) == []


async def test_opening_balance_for_unknown_product_is_not_found(client: AsyncClient, auth_headers):
    headers = await auth_headers("warehouse_manager")

    response = await _post_opening_balance(client, headers, 999999, 5)

    assert response.status_code == 404
    assert response.json() == {"detail": "Product not found"}


@pytest.mark.parametrize("quantity", [0, -5])
async def test_service_rejects_non_positive_opening_balance(
    db_session: AsyncSession, make_user: Callable, new_product, quantity: int
):
    user = await make_user("stock@example.com", "warehouse_manager")

    with pytest.raises(HTTPException) as rejected:
        await record_opening_balance(db_session, product_id=new_product.id, quantity=quantity, created_by=user.id)

    assert rejected.value.status_code == 422
    assert rejected.value.detail == "Opening balance quantity must be greater than zero."


async def test_product_fixture_satisfies_the_ledger_invariant(
    db_session: AsyncSession, product, assert_stock_matches_ledger
):
    rows = await _ledger_rows(db_session, product.id)

    assert product.current_stock == 50
    assert [(row.type.value, row.quantity_delta) for row in rows] == [("opening_balance", 50)]
    await assert_stock_matches_ledger(product.id)
