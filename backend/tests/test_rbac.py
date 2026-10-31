import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PERMISSIONS, ROLE_PERMISSIONS, SUPPLIER_ROLE
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from tests.fixture_types import AuthHeaders


async def test_viewer_cannot_create_supplier(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("viewer")

    response = await client.post("/api/v1/suppliers", json={"name": "New Supplier"}, headers=headers)

    assert response.status_code == 403


async def test_procurement_manager_can_create_supplier(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("procurement_manager")

    response = await client.post("/api/v1/suppliers", json={"name": "New Supplier"}, headers=headers)

    assert response.status_code == 201


async def test_all_authenticated_roles_can_read_suppliers(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("viewer")

    response = await client.get("/api/v1/suppliers", headers=headers)

    assert response.status_code == 200


async def test_purchasing_officer_cannot_approve_purchase_order(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier, product: Product
) -> None:
    officer_headers = await auth_headers("purchasing_officer")

    create_response = await client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": product.id, "quantity": 5, "unit_price": "10.00"}],
        },
        headers=officer_headers,
    )
    po_id = create_response.json()["id"]
    await client.post(f"/api/v1/purchase-orders/{po_id}/submit", headers=officer_headers)

    response = await client.post(f"/api/v1/purchase-orders/{po_id}/approve", headers=officer_headers)

    assert response.status_code == 403


async def test_warehouse_manager_cannot_create_purchase_order(
    client: AsyncClient, auth_headers: AuthHeaders, supplier: Supplier
) -> None:
    headers = await auth_headers("warehouse_manager")

    response = await client.post(
        "/api/v1/purchase-orders", json={"supplier_id": supplier.id, "items": []}, headers=headers
    )

    assert response.status_code == 403


async def test_only_admin_can_manage_users(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    procurement_headers = await auth_headers("procurement_manager")

    response = await client.get("/api/v1/users", headers=procurement_headers)

    assert response.status_code == 403


async def test_unauthenticated_request_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/suppliers")

    assert response.status_code == 401


PHASE_6_PERMISSIONS = {
    "export:read": {"admin", "finance"},
    "gdpr:manage": {"admin"},
    "payment:export": {"admin", "finance"},
    "supplier:bank_details": {"admin", "finance", "procurement_manager"},
    "portal:access": {"supplier"},
}


@pytest.mark.parametrize(("code", "holders"), sorted(PHASE_6_PERMISSIONS.items()))
def test_phase_6_permissions_are_held_by_exactly_the_intended_roles(code: str, holders: set[str]) -> None:
    assert {role for role, codes in ROLE_PERMISSIONS.items() if code in codes} == holders
    assert code in PERMISSIONS


def test_the_supplier_role_has_only_the_portal_permission() -> None:
    assert ROLE_PERMISSIONS[SUPPLIER_ROLE] == ["portal:access"]


async def test_the_roles_screen_lists_the_supplier_role_with_its_single_permission(
    client: AsyncClient, auth_headers: AuthHeaders
) -> None:
    headers = await auth_headers("admin")

    response = await client.get("/api/v1/roles", headers=headers)

    supplier_role = next(role for role in response.json() if role["name"] == "supplier")
    assert [permission["code"] for permission in supplier_role["permissions"]] == ["portal:access"]


@pytest.mark.parametrize("role_name", ["admin", "finance", "procurement_manager", "viewer"])
async def test_internal_roles_cannot_use_the_portal(
    client: AsyncClient, auth_headers: AuthHeaders, role_name: str
) -> None:
    headers = await auth_headers(role_name)

    assert (await client.get("/api/v1/portal/orders", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/portal/me", headers=headers)).status_code == 403


async def test_a_supplier_account_cannot_read_the_supplier_list(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession, supplier: Supplier
) -> None:
    headers = await auth_headers("supplier")
    user = await db_session.scalar(select(User).where(User.email == "supplier@example.com"))
    assert user is not None
    user.supplier_id = supplier.id
    await db_session.commit()

    assert (await client.get("/api/v1/suppliers", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/portal/me", headers=headers)).status_code == 200
