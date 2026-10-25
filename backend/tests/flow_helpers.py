"""Small helpers that drive the HTTP API the way the screens do, shared by the approval-related tests."""

from typing import Any

from httpx import AsyncClient, Response

from app.models.product import Product
from app.models.supplier import Supplier

API = "/api/v1"
Headers = dict[str, str]


async def role_id(client: AsyncClient, headers: Headers, name: str) -> int:
    roles = (await client.get(f"{API}/roles", headers=headers)).json()
    return int(next(role["id"] for role in roles if role["name"] == name))


async def user_id(client: AsyncClient, headers: Headers) -> int:
    return int((await client.get(f"{API}/auth/me", headers=headers)).json()["id"])


async def add_rule(
    client: AsyncClient,
    headers: Headers,
    *,
    document_type: str,
    roles: list[str],
    min_amount: str = "0",
    max_amount: str | None = None,
    name: str | None = None,
    is_active: bool = True,
) -> Response:
    role_ids = [await role_id(client, headers, role) for role in roles]
    payload: dict[str, Any] = {
        "name": name or f"{document_type} {min_amount}-{max_amount or 'up'}",
        "document_type": document_type,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "is_active": is_active,
        "steps": [{"approver_role_id": rid} for rid in role_ids],
    }
    return await client.post(f"{API}/approval-rules", json=payload, headers=headers)


async def draft_po(
    client: AsyncClient,
    headers: Headers,
    supplier: Supplier,
    product: Product,
    *,
    quantity: int = 10,
    unit_price: str = "10.00",
    **extra: Any,
) -> dict[str, Any]:
    response = await client.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier.id,
            "items": [{"product_id": product.id, "quantity": quantity, "unit_price": unit_price}],
            **extra,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def submitted_po(
    client: AsyncClient,
    headers: Headers,
    supplier: Supplier,
    product: Product,
    *,
    quantity: int = 10,
    unit_price: str = "10.00",
    **extra: Any,
) -> dict[str, Any]:
    po = await draft_po(client, headers, supplier, product, quantity=quantity, unit_price=unit_price, **extra)
    response = await client.post(f"{API}/purchase-orders/{po['id']}/submit", headers=headers)
    assert response.status_code == 200, response.text
    return dict(response.json())


async def approve_po(client: AsyncClient, headers: Headers, po_id: int, comment: str | None = None) -> Response:
    body = {"comment": comment} if comment else None
    return await client.post(f"{API}/purchase-orders/{po_id}/approve", json=body, headers=headers)


async def get_po(client: AsyncClient, headers: Headers, po_id: int) -> dict[str, Any]:
    return dict((await client.get(f"{API}/purchase-orders/{po_id}", headers=headers)).json())


async def approval_steps(
    client: AsyncClient, headers: Headers, document_type: str, document_id: int
) -> list[dict[str, Any]]:
    response = await client.get(f"{API}/approvals/{document_type}/{document_id}/steps", headers=headers)
    assert response.status_code == 200, response.text
    return list(response.json())


async def queue(client: AsyncClient, headers: Headers) -> dict[str, Any]:
    return dict((await client.get(f"{API}/approvals/queue", headers=headers)).json())


async def set_limit(
    client: AsyncClient, headers: Headers, target_user_id: int, document_type: str, max_amount: str
) -> Response:
    return await client.put(
        f"{API}/approval-limits",
        json={"user_id": target_user_id, "document_type": document_type, "max_amount": max_amount},
        headers=headers,
    )
