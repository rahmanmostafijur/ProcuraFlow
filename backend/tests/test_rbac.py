from httpx import AsyncClient


async def test_viewer_cannot_create_supplier(client: AsyncClient, auth_headers):
    headers = await auth_headers("viewer")

    response = await client.post(
        "/api/v1/suppliers", json={"name": "New Supplier"}, headers=headers
    )

    assert response.status_code == 403


async def test_procurement_manager_can_create_supplier(client: AsyncClient, auth_headers):
    headers = await auth_headers("procurement_manager")

    response = await client.post(
        "/api/v1/suppliers", json={"name": "New Supplier"}, headers=headers
    )

    assert response.status_code == 201


async def test_all_authenticated_roles_can_read_suppliers(client: AsyncClient, auth_headers):
    headers = await auth_headers("viewer")

    response = await client.get("/api/v1/suppliers", headers=headers)

    assert response.status_code == 200


async def test_purchasing_officer_cannot_approve_purchase_order(
    client: AsyncClient, auth_headers, supplier, product
):
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


async def test_warehouse_manager_cannot_create_purchase_order(client: AsyncClient, auth_headers, supplier):
    headers = await auth_headers("warehouse_manager")

    response = await client.post(
        "/api/v1/purchase-orders", json={"supplier_id": supplier.id, "items": []}, headers=headers
    )

    assert response.status_code == 403


async def test_only_admin_can_manage_users(client: AsyncClient, auth_headers):
    procurement_headers = await auth_headers("procurement_manager")

    response = await client.get("/api/v1/users", headers=procurement_headers)

    assert response.status_code == 403


async def test_unauthenticated_request_is_rejected(client: AsyncClient):
    response = await client.get("/api/v1/suppliers")

    assert response.status_code == 401
