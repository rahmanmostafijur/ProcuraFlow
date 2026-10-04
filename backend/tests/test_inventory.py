from httpx import AsyncClient


async def test_inventory_adjustment_increases_stock_and_records_transaction(
    client: AsyncClient, auth_headers, product
):
    headers = await auth_headers("warehouse_manager")

    response = await client.post(
        "/api/v1/inventory/adjustments",
        json={"product_id": product.id, "quantity_delta": 25, "reason": "Cycle count correction"},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["resulting_stock"] == 75  # 50 initial + 25
    assert body["type"] == "adjustment"

    product_response = await client.get(f"/api/v1/products/{product.id}", headers=headers)
    assert product_response.json()["current_stock"] == 75


async def test_inventory_adjustment_rejects_negative_resulting_stock(
    client: AsyncClient, auth_headers, product
):
    headers = await auth_headers("warehouse_manager")

    response = await client.post(
        "/api/v1/inventory/adjustments",
        json={"product_id": product.id, "quantity_delta": -999, "reason": "Too much shrinkage"},
        headers=headers,
    )

    assert response.status_code == 409

    product_response = await client.get(f"/api/v1/products/{product.id}", headers=headers)
    assert product_response.json()["current_stock"] == 50  # unchanged


async def test_viewer_cannot_adjust_inventory(client: AsyncClient, auth_headers, product):
    headers = await auth_headers("viewer")

    response = await client.post(
        "/api/v1/inventory/adjustments",
        json={"product_id": product.id, "quantity_delta": 5, "reason": "Should be blocked"},
        headers=headers,
    )

    assert response.status_code == 403


async def test_adjustment_creates_auditable_transaction_history(client: AsyncClient, auth_headers, product):
    headers = await auth_headers("admin")
    await client.post(
        "/api/v1/inventory/adjustments",
        json={"product_id": product.id, "quantity_delta": 10, "reason": "Restock"},
        headers=headers,
    )

    response = await client.get(
        f"/api/v1/inventory/transactions?product_id={product.id}", headers=headers
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2  # the fixture's opening balance, then this adjustment
    assert items[0]["reason"] == "Restock"
    assert items[1]["type"] == "opening_balance"
