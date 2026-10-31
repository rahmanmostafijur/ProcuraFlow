"""Supplier isolation: a supplier never reads or changes another supplier's data, internal users stay out of the
portal, and a supplier account is refused by every internal endpoint."""

import re
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.main import app
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.supplier_document import SupplierDocument
from app.models.supplier_invoice import SupplierInvoice
from app.models.user import User
from tests.flow_helpers import API
from tests.invoice_helpers import Staff
from tests.portal_helpers import (
    PORTAL,
    Tenant,
    document,
    draft_invoice,
    invoice_file,
    invoice_payload,
    supplier_login,
    two_tenants,
)
from tests.sample_files import pdf_bytes

METHODS_WITH_BODY = {"post", "put", "patch"}
OPERATION_METHODS = {"get", "post", "put", "patch", "delete"}
# Outside the portal, sign-in and health probes. The first two public routes feed the sign-in page.
EXCLUDED_PREFIXES = (f"{API}/portal", f"{API}/auth", "/api/health", "/api/ready", "/health")
EXPECTED_PUBLIC = {("get", f"{API}/company-settings/branding"), ("get", f"{API}/company-settings/logo")}


def _operations() -> list[tuple[str, str, bool]]:
    """Every (method, concrete path, requires sign-in) the application exposes, from its OpenAPI description."""
    found = []
    for path, item in app.openapi()["paths"].items():
        for method, operation in item.items():
            if method in OPERATION_METHODS:
                found.append((method, re.sub(r"\{[^}]+\}", "1", path), bool(operation.get("security"))))
    return found


async def _call(client: AsyncClient, method: str, path: str, headers: dict[str, str] | None = None) -> int:
    body: dict[str, Any] | None = {} if method in METHODS_WITH_BODY else None
    return (await client.request(method, path, json=body, headers=headers)).status_code


@pytest.fixture
async def tenants(
    client: AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    staff: Staff,
    supplier: Supplier,
    product: Product,
) -> tuple[Tenant, Tenant]:
    return await two_tenants(client, db_session, roles, staff, supplier, product)


async def test_the_route_enumeration_sees_the_whole_application() -> None:
    operations = _operations()
    paths = {path for _, path, _ in operations}

    assert len(operations) > 150
    assert f"{API}/portal/orders" in paths
    assert f"{API}/suppliers/1/portal-invite" in paths
    assert f"{API}/payment-runs/1/file/download" in paths


async def test_a_supplier_account_is_refused_by_every_internal_endpoint(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    supplier_headers = tenants[0].headers
    internal = [op for op in _operations() if not op[1].startswith(EXCLUDED_PREFIXES)]
    public = {(method, path) for method, path, signed_in in internal if not signed_in}
    leaks = []

    for method, path, signed_in in internal:
        if not signed_in:
            continue
        status = await _call(client, method, path, supplier_headers)
        if status != 403:
            leaks.append(f"{method.upper()} {path} -> {status}")

    assert not leaks, "internal endpoints that did not refuse a supplier account:\n" + "\n".join(leaks)
    # Routes that need no sign-in at all are an explicit, reviewed list, so a new open route cannot slip in.
    assert public == EXPECTED_PUBLIC
    assert len(internal) > 100


async def test_every_internal_endpoint_still_needs_a_sign_in(client: AsyncClient) -> None:
    unauthenticated = []

    for method, path, signed_in in _operations():
        if path.startswith(EXCLUDED_PREFIXES) or not signed_in:
            continue
        status = await _call(client, method, path)
        if status != 401:
            unauthenticated.append(f"{method.upper()} {path} -> {status}")

    assert not unauthenticated, "\n".join(unauthenticated)


async def test_the_public_routes_work_without_a_token(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/company-settings/branding")).status_code == 200
    assert (await client.get(f"{API}/company-settings/logo")).status_code in (200, 404)


async def test_internal_users_of_every_kind_are_refused_by_every_portal_endpoint(
    client: AsyncClient, staff: Staff, tenants: tuple[Tenant, Tenant]
) -> None:
    portal = [op for op in _operations() if op[1].startswith(f"{API}/portal")]
    refused = []

    for headers in (staff.admin, staff.manager, staff.officer, staff.finance, staff.warehouse, staff.viewer):
        for method, path, _ in portal:
            status = await _call(client, method, path, headers)
            if status != 403:
                refused.append(f"{method.upper()} {path} -> {status}")
    for method, path, _ in portal:
        if await _call(client, method, path) != 401:
            refused.append(f"anonymous {method.upper()} {path}")

    assert not refused, "\n".join(refused)
    assert len(portal) >= 14


async def test_a_supplier_role_without_a_supplier_reaches_neither_area(
    client: AsyncClient, db_session: AsyncSession, roles: dict[str, Role]
) -> None:
    orphan = User(email="orphan@example.com", full_name="Orphan", hashed_password="x", role_id=roles["supplier"].id)
    db_session.add(orphan)
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(str(orphan.id), 'supplier')}"}

    assert (await client.get(f"{PORTAL}/orders", headers=headers)).status_code == 403
    assert (await client.get(f"{API}/suppliers", headers=headers)).status_code == 403


async def test_the_role_claim_in_a_token_is_not_trusted(
    client: AsyncClient, tenants: tuple[Tenant, Tenant], db_session: AsyncSession
) -> None:
    portal_user = await db_session.scalar(select(User).where(User.supplier_id == tenants[0].supplier.id))
    assert portal_user is not None
    forged = {"Authorization": f"Bearer {create_access_token(str(portal_user.id), 'admin')}"}

    assert (await client.get(f"{API}/users", headers=forged)).status_code == 403
    assert (await client.get(f"{API}/suppliers", headers=forged)).status_code == 403
    assert (await client.get(f"{PORTAL}/me", headers=forged)).status_code == 200


async def test_a_supplier_sees_only_its_own_records_in_every_list(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    mine, theirs = tenants
    my_invoice = await draft_invoice(client, mine, "MINE-1")
    their_invoice = await draft_invoice(client, theirs, "THEIRS-1")
    my_document = await document(client, mine)
    their_document = await document(client, theirs)

    orders = (await client.get(f"{PORTAL}/orders", headers=mine.headers)).json()["items"]
    invoices = (await client.get(f"{PORTAL}/invoices", headers=mine.headers)).json()["items"]
    documents = (await client.get(f"{PORTAL}/documents", headers=mine.headers)).json()

    assert [row["id"] for row in orders] == [mine.order["id"]]
    assert [row["id"] for row in invoices] == [my_invoice["id"]]
    assert [row["id"] for row in documents] == [my_document["id"]]
    assert their_invoice["id"] not in {row["id"] for row in invoices}
    assert their_document["id"] not in {row["id"] for row in documents}


async def test_every_id_in_a_portal_url_is_checked_against_the_signed_in_supplier(
    client: AsyncClient, tenants: tuple[Tenant, Tenant], db_session: AsyncSession
) -> None:
    mine, theirs = tenants
    my_invoice = await draft_invoice(client, mine, "MINE-1")
    their_invoice = await draft_invoice(client, theirs, "THEIRS-1")
    my_file = await invoice_file(client, mine, my_invoice["id"])
    their_file = await invoice_file(client, theirs, their_invoice["id"])
    their_document = await document(client, theirs)
    pdf = {"file": ("x.pdf", pdf_bytes(), "application/pdf")}
    h = mine.headers

    calls = [
        client.get(f"{PORTAL}/orders/{theirs.order['id']}", headers=h),
        client.post(f"{PORTAL}/orders/{theirs.order['id']}/acknowledge", headers=h),
        client.get(f"{PORTAL}/invoices/{their_invoice['id']}", headers=h),
        client.get(f"{PORTAL}/invoices/{their_invoice['id']}/files", headers=h),
        client.post(f"{PORTAL}/invoices/{their_invoice['id']}/files", files=pdf, headers=h),
        client.get(f"{PORTAL}/invoices/{their_invoice['id']}/files/{their_file['id']}/download", headers=h),
        # Their file through my invoice, and my file through their invoice.
        client.get(f"{PORTAL}/invoices/{my_invoice['id']}/files/{their_file['id']}/download", headers=h),
        client.get(f"{PORTAL}/invoices/{their_invoice['id']}/files/{my_file['id']}/download", headers=h),
        client.get(f"{PORTAL}/documents/{their_document['id']}/download", headers=h),
        client.delete(f"{PORTAL}/documents/{their_document['id']}", headers=h),
        client.post(f"{PORTAL}/invoices", json=invoice_payload(theirs, "STOLEN-1"), headers=h),
    ]
    statuses = [(await call).status_code for call in calls]

    assert statuses == [404] * len(calls)
    # Nothing of theirs changed.
    db_session.expire_all()
    their_order = await db_session.get(PurchaseOrder, theirs.order["id"])
    assert their_order is not None
    assert their_order.acknowledged_at is None
    assert await db_session.get(SupplierDocument, their_document["id"]) is not None
    invoices = (
        (await db_session.execute(select(SupplierInvoice.invoice_number).order_by(SupplierInvoice.id))).scalars().all()
    )
    assert list(invoices) == ["MINE-1", "THEIRS-1"]
    still_there = await client.get(f"{PORTAL}/invoices/{their_invoice['id']}/files", headers=theirs.headers)
    assert [row["id"] for row in still_there.json()] == [their_file["id"]]


async def test_a_supplier_id_in_the_request_changes_nothing(
    client: AsyncClient, tenants: tuple[Tenant, Tenant]
) -> None:
    mine, theirs = tenants
    spoof: dict[str, Any] = {"supplier_id": theirs.supplier.id}

    orders = await client.get(f"{PORTAL}/orders", params=spoof, headers=mine.headers)
    invoices = await client.get(f"{PORTAL}/invoices", params=spoof, headers=mine.headers)
    created = await client.post(
        f"{PORTAL}/invoices", params=spoof, json=invoice_payload(mine, "SPOOF-1", **spoof), headers=mine.headers
    )
    me = await client.get(f"{PORTAL}/me", params=spoof, headers=mine.headers)

    assert [row["id"] for row in orders.json()["items"]] == [mine.order["id"]]
    assert invoices.json()["items"] == []
    assert created.status_code == 201
    assert me.json()["supplier"]["id"] == mine.supplier.id
    listed_for_them = await client.get(f"{PORTAL}/invoices", headers=theirs.headers)
    assert listed_for_them.json()["items"] == []


async def test_two_accounts_of_one_supplier_share_that_suppliers_data_and_nothing_else(
    client: AsyncClient, tenants: tuple[Tenant, Tenant], db_session: AsyncSession, roles: dict[str, Role]
) -> None:
    mine, theirs = tenants
    colleague = await supplier_login(client, db_session, roles, mine.supplier, "colleague@supplier-a.example.com")
    invoice = await draft_invoice(client, mine, "SHARED-1")

    seen_by_colleague = await client.get(f"{PORTAL}/invoices/{invoice['id']}", headers=colleague)
    other = await client.get(f"{PORTAL}/invoices/{invoice['id']}", headers=theirs.headers)

    assert seen_by_colleague.status_code == 200
    assert other.status_code == 404
