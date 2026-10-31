"""Helpers for the supplier portal tests: supplier accounts that are signed in, and what they own."""

from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utc_today
from app.core.security import hash_password
from app.models.product import Product
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User
from tests.flow_helpers import API
from tests.invoice_helpers import Staff, ordered_po
from tests.payment_file_helpers import second_supplier
from tests.sample_files import pdf_bytes

PASSWORD = "TestPass123!"
PORTAL = f"{API}/portal"


async def supplier_login(
    client: AsyncClient, db: AsyncSession, roles: dict[str, Role], supplier: Supplier, email: str
) -> dict[str, str]:
    """A supplier account linked to ``supplier``, signed in through the real login route."""
    db.add(
        User(
            email=email,
            full_name=f"Portal {email.split('@', maxsplit=1)[0]}",
            hashed_password=hash_password(PASSWORD),
            role_id=roles["supplier"].id,
            supplier_id=supplier.id,
        )
    )
    await db.commit()
    response = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@dataclass(frozen=True)
class Tenant:
    """One supplier with its portal account, an ordered purchase order and the product on it."""

    supplier: Supplier
    product: Product
    headers: dict[str, str]
    order: dict[str, Any]


async def tenant(
    client: AsyncClient,
    db: AsyncSession,
    roles: dict[str, Role],
    staff: Staff,
    supplier: Supplier,
    product: Product,
    email: str,
) -> Tenant:
    headers = await supplier_login(client, db, roles, supplier, email)
    order = await ordered_po(client, staff, supplier, product)
    return Tenant(supplier, product, headers, order)


async def two_tenants(
    client: AsyncClient,
    db: AsyncSession,
    roles: dict[str, Role],
    staff: Staff,
    supplier: Supplier,
    product: Product,
) -> tuple[Tenant, Tenant]:
    other, other_product = await second_supplier(db)
    first = await tenant(client, db, roles, staff, supplier, product, "portal.a@supplier-a.example.com")
    second = await tenant(client, db, roles, staff, other, other_product, "portal.b@supplier-b.example.com")
    return first, second


def invoice_payload(owner: Tenant, number: str = "S-INV-1", **extra: Any) -> dict[str, Any]:
    return {
        "po_id": owner.order["id"],
        "invoice_number": number,
        "invoice_date": utc_today().isoformat(),
        "lines": [{"product_id": owner.product.id, "quantity": 10, "unit_price": "10.00"}],
    } | extra


async def draft_invoice(client: AsyncClient, owner: Tenant, number: str = "S-INV-1") -> dict[str, Any]:
    response = await client.post(f"{PORTAL}/invoices", json=invoice_payload(owner, number), headers=owner.headers)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def invoice_file(client: AsyncClient, owner: Tenant, invoice_id: int) -> dict[str, Any]:
    response = await client.post(
        f"{PORTAL}/invoices/{invoice_id}/files",
        files={"file": ("invoice.pdf", pdf_bytes(), "application/pdf")},
        headers=owner.headers,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def document(client: AsyncClient, owner: Tenant, document_type: str = "w9") -> dict[str, Any]:
    response = await client.post(
        f"{PORTAL}/documents",
        data={"document_type": document_type},
        files={"file": ("w9.pdf", pdf_bytes(), "application/pdf")},
        headers=owner.headers,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())
