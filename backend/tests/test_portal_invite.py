"""Inviting a supplier's contact to the portal, and the rules for supplier accounts."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.email import EmailOutbox, UserToken
from app.models.product import Product
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User
from tests.flow_helpers import API
from tests.invoice_helpers import Staff
from tests.portal_helpers import PASSWORD, PORTAL, Tenant, tenant


@pytest.fixture
async def acme(
    client: AsyncClient,
    db_session: AsyncSession,
    roles: dict[str, Role],
    staff: Staff,
    supplier: Supplier,
    product: Product,
) -> Tenant:
    return await tenant(client, db_session, roles, staff, supplier, product, "portal@acme.example.com")


async def test_inviting_a_contact_creates_a_supplier_account_and_queues_the_email(
    client: AsyncClient, staff: Staff, supplier: Supplier, db_session: AsyncSession
) -> None:
    response = await client.post(
        f"{API}/suppliers/{supplier.id}/portal-invite",
        json={"email": "buyer@acme-supplies.example.com", "full_name": "Pat Buyer"},
        headers=staff.manager,
    )

    assert response.status_code == 201
    assert response.json()["email"] == "buyer@acme-supplies.example.com"
    user = await db_session.scalar(select(User).where(User.email == "buyer@acme-supplies.example.com"))
    assert user is not None
    assert (user.supplier_id, user.is_active) == (supplier.id, True)
    role = await db_session.get(Role, user.role_id)
    assert role is not None
    assert role.name == "supplier"
    mail = await db_session.scalar(select(EmailOutbox))
    assert mail is not None
    assert (mail.to_address, mail.template_key) == ("buyer@acme-supplies.example.com", "invitation")
    assert "accept-invitation?token=" in mail.body
    assert await db_session.scalar(select(func.count()).select_from(UserToken)) == 1
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.action == "supplier_portal_invited"))
    assert audit is not None
    assert (audit.entity_type, audit.entity_id) == ("supplier", supplier.id)
    accounts = await client.get(f"{API}/suppliers/{supplier.id}/portal-users", headers=staff.manager)
    assert [row["email"] for row in accounts.json()] == ["buyer@acme-supplies.example.com"]


async def test_the_invited_contact_accepts_and_lands_in_the_portal(
    client: AsyncClient, staff: Staff, supplier: Supplier, db_session: AsyncSession
) -> None:
    await client.post(
        f"{API}/suppliers/{supplier.id}/portal-invite",
        json={"email": "buyer@acme-supplies.example.com", "full_name": "Pat Buyer"},
        headers=staff.manager,
    )
    mail = await db_session.scalar(select(EmailOutbox))
    assert mail is not None
    token = mail.body.split("token=")[1].split()[0].strip()

    accepted = await client.post(f"{API}/auth/invitations/accept", json={"token": token, "password": PASSWORD})
    login = await client.post(
        f"{API}/auth/login", json={"email": "buyer@acme-supplies.example.com", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get(f"{PORTAL}/me", headers=headers)
    auth_me = await client.get(f"{API}/auth/me", headers=headers)

    assert accepted.status_code == 204
    assert me.json()["supplier"]["id"] == supplier.id
    assert auth_me.json()["supplier_id"] == supplier.id
    assert auth_me.json()["role"]["name"] == "supplier"


async def test_only_supplier_managers_can_invite_and_each_email_once(
    client: AsyncClient, staff: Staff, supplier: Supplier, db_session: AsyncSession
) -> None:
    url = f"{API}/suppliers/{supplier.id}/portal-invite"
    body = {"email": "buyer@acme-supplies.example.com", "full_name": "Pat Buyer"}

    for outsider in (staff.officer, staff.finance, staff.warehouse, staff.viewer):
        assert (await client.post(url, json=body, headers=outsider)).status_code == 403
        assert (await client.get(f"{API}/suppliers/{supplier.id}/portal-users", headers=outsider)).status_code == 403
    assert (await client.post(url, json=body)).status_code == 401
    assert (await client.post(url, json=body, headers=staff.admin)).status_code == 201
    assert (await client.post(url, json=body, headers=staff.manager)).status_code == 409
    taken = await client.post(url, json={"email": "admin@example.com", "full_name": "X"}, headers=staff.manager)
    assert taken.status_code == 409
    assert (
        await client.post(f"{API}/suppliers/9999/portal-invite", json=body, headers=staff.manager)
    ).status_code == 404
    assert (
        await client.post(url, json={"email": "not-an-email", "full_name": "X"}, headers=staff.manager)
    ).status_code == 422
    supplier.is_active = False
    await db_session.commit()
    inactive = await client.post(url, json={**body, "email": "other@acme-supplies.example.com"}, headers=staff.manager)
    assert inactive.status_code == 409


async def test_supplier_accounts_cannot_be_made_through_the_user_screens(
    client: AsyncClient, staff: Staff, roles: dict[str, Role], acme: Tenant, db_session: AsyncSession
) -> None:
    supplier_role = roles["supplier"].id
    create = await client.post(
        f"{API}/users",
        json={"email": "x@example.com", "full_name": "X", "password": "Password123!", "role_id": supplier_role},
        headers=staff.admin,
    )
    invite = await client.post(
        f"{API}/users/invite",
        json={"email": "y@example.com", "full_name": "Y", "role_id": supplier_role},
        headers=staff.admin,
    )
    viewer = await db_session.scalar(select(User).where(User.email == "viewer@example.com"))
    assert viewer is not None
    promote = await client.patch(f"{API}/users/{viewer.id}", json={"role_id": supplier_role}, headers=staff.admin)
    portal_user = await db_session.scalar(select(User).where(User.supplier_id == acme.supplier.id))
    assert portal_user is not None
    demote = await client.patch(
        f"{API}/users/{portal_user.id}", json={"role_id": roles["admin"].id}, headers=staff.admin
    )
    deactivate = await client.patch(f"{API}/users/{portal_user.id}", json={"is_active": False}, headers=staff.admin)

    assert (create.status_code, invite.status_code, promote.status_code, demote.status_code) == (400, 400, 400, 400)
    assert deactivate.status_code == 200
    assert (await client.get(f"{PORTAL}/me", headers=acme.headers)).status_code == 401


async def test_a_deactivated_supplier_locks_its_accounts_out_of_the_portal(
    client: AsyncClient, acme: Tenant, db_session: AsyncSession
) -> None:
    acme.supplier.is_active = False
    await db_session.commit()

    for path in ("/me", "/orders", "/invoices", "/documents"):
        assert (await client.get(f"{PORTAL}{path}", headers=acme.headers)).status_code == 403


async def test_a_supplier_account_can_change_its_own_password_and_read_its_profile(
    client: AsyncClient, acme: Tenant
) -> None:
    me = await client.get(f"{API}/auth/me", headers=acme.headers)
    changed = await client.post(
        f"{API}/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "BrandNewSecret99!"},
        headers=acme.headers,
    )

    assert me.status_code == 200
    assert changed.status_code == 204
