"""GDPR: export and anonymisation of a person's data, with the financial record left intact."""

import json
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookie import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH
from app.main import app
from app.models.audit import AuditLog
from app.models.email import EmailOutbox
from app.models.notification import Notification
from app.models.purchase_order import PurchaseOrder
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.user import User
from app.services.gdpr_anonymise_service import ANONYMISED_CONTACT, ANONYMISED_NAME
from app.services.gdpr_redaction import redact_json
from tests.fixture_types import AuthHeaders, MakeUser
from tests.flow_helpers import API
from tests.invoice_helpers import Staff, ordered_po

GDPR = f"{API}/gdpr"
PASSWORD = "TestPass123!"


async def _login_cookie(email: str) -> str:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as device:
        response = await device.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
        assert response.status_code == 200
        return response.headers["set-cookie"].split(";")[0].split("=", 1)[1]


async def _refresh_status(token: str) -> int:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as device:
        device.cookies.set(REFRESH_COOKIE_NAME, token, path=REFRESH_COOKIE_PATH)
        return (await device.post(f"{API}/auth/refresh")).status_code


async def _anonymise(client: AsyncClient, admin: dict[str, str], user_id: int) -> Response:
    return await client.post(f"{GDPR}/users/{user_id}/anonymise", headers=admin)


async def _audit_count(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(AuditLog)) or 0)


async def test_only_an_admin_can_use_the_gdpr_endpoints(
    client: AsyncClient, staff: Staff, make_user: MakeUser, supplier: Supplier
) -> None:
    target = await make_user("target@example.com", "viewer")
    urls = [
        ("GET", f"{GDPR}/users/{target.id}/export"),
        ("POST", f"{GDPR}/users/{target.id}/anonymise"),
        ("GET", f"{GDPR}/suppliers/{supplier.id}/contact/export"),
        ("POST", f"{GDPR}/suppliers/{supplier.id}/contact/anonymise"),
    ]

    for method, url in urls:
        for outsider in (staff.finance, staff.manager, staff.officer, staff.viewer):
            assert (await client.request(method, url, headers=outsider)).status_code == 403
        assert (await client.request(method, url)).status_code == 401
        assert (await client.request(method, url, headers=staff.admin)).status_code == 200


async def test_unknown_users_and_suppliers_are_404(client: AsyncClient, staff: Staff) -> None:
    assert (await client.get(f"{GDPR}/users/9999/export", headers=staff.admin)).status_code == 404
    assert (await _anonymise(client, staff.admin, 9999)).status_code == 404
    assert (await client.get(f"{GDPR}/suppliers/9999/contact/export", headers=staff.admin)).status_code == 404
    assert (await client.post(f"{GDPR}/suppliers/9999/contact/anonymise", headers=staff.admin)).status_code == 404


async def test_the_user_export_lists_their_data_and_never_the_password_hash(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Any, db_session: AsyncSession
) -> None:
    officer = (await client.get(f"{API}/auth/me", headers=staff.officer)).json()
    po = await ordered_po(client, staff, supplier, product)
    db_session.add(Notification(user_id=officer["id"], message="Something to look at"))
    await db_session.commit()

    response = await client.get(f"{GDPR}/users/{officer['id']}/export", headers=staff.admin)

    body = response.json()
    assert response.status_code == 200
    assert body["subject"] == {"type": "user", "id": officer["id"]}
    assert body["profile"]["email"] == officer["email"]
    assert body["profile"]["role"] == "purchasing_officer"
    assert po["id"] in body["records_created"]["purchase_orders"]
    assert [row["message"] for row in body["notifications"]] == ["Something to look at"]
    assert {entry["action"] for entry in body["audit_entries"]} >= {"login"}
    assert "hashed_password" not in json.dumps(body)
    assert "$2b$" not in json.dumps(body)


async def test_exporting_is_recorded_in_the_audit_log(
    client: AsyncClient, staff: Staff, make_user: MakeUser, db_session: AsyncSession
) -> None:
    target = await make_user("target@example.com", "viewer")

    await client.get(f"{GDPR}/users/{target.id}/export", headers=staff.admin)

    entry = await db_session.scalar(select(AuditLog).where(AuditLog.action == "gdpr_exported"))
    assert entry is not None
    assert (entry.entity_type, entry.entity_id) == ("user", target.id)


async def test_anonymising_replaces_the_identity_closes_the_account_and_keeps_the_records(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Any, db_session: AsyncSession
) -> None:
    officer = (await client.get(f"{API}/auth/me", headers=staff.officer)).json()
    po = await ordered_po(client, staff, supplier, product)
    session_token = await _login_cookie(officer["email"])
    db_session.add(Notification(user_id=officer["id"], message="Private note"))
    await db_session.commit()

    response = await _anonymise(client, staff.admin, officer["id"])

    assert response.status_code == 200
    assert response.json()["already_anonymised"] is False
    db_session.expire_all()
    user = await db_session.get(User, officer["id"])
    assert user is not None
    assert user.full_name == ANONYMISED_NAME
    assert user.email == f"anonymised-user-{officer['id']}@anonymised.example.com"
    assert user.is_active is False
    # The record stays and still points at the same (now anonymous) person.
    order = await db_session.get(PurchaseOrder, po["id"])
    assert order is not None
    assert order.created_by == officer["id"]
    reread = await client.get(f"{API}/purchase-orders/{po['id']}", headers=staff.admin)
    assert reread.json()["creator"]["full_name"] == ANONYMISED_NAME
    assert await db_session.scalar(select(func.count()).select_from(Notification)) == 0
    # The old credentials and sessions no longer work.
    assert await _refresh_status(session_token) == 401
    login = await client.post(f"{API}/auth/login", json={"email": officer["email"], "password": PASSWORD})
    assert login.status_code == 401
    assert (await client.get(f"{API}/auth/me", headers=staff.officer)).status_code == 401


async def test_the_person_is_removed_from_audit_entries_about_them_but_the_entries_stay(
    client: AsyncClient, staff: Staff, make_user: MakeUser, db_session: AsyncSession
) -> None:
    target = await make_user("jane.doe@example.com", "viewer")
    target.full_name = "Jane Doe"
    await db_session.commit()
    await client.patch(f"{API}/users/{target.id}", json={"full_name": "Jane Q. Doe"}, headers=staff.admin)
    about = select(AuditLog).where(AuditLog.entity_type == "user", AuditLog.entity_id == target.id)
    before = (await db_session.execute(about)).scalars().all()
    assert "Jane Doe" in json.dumps([entry.extra_data for entry in before])
    unrelated = await _audit_count(db_session) - len(before)
    before_ids = {entry.id for entry in before}

    await _anonymise(client, staff.admin, target.id)

    db_session.expire_all()
    after = (await db_session.execute(about)).scalars().all()
    stored = json.dumps([entry.extra_data for entry in after])
    assert "Jane Doe" not in stored
    assert "jane.doe@example.com" not in stored
    assert before_ids <= {entry.id for entry in after}
    # Nothing else was deleted: one new entry for the anonymisation itself.
    assert await _audit_count(db_session) == unrelated + len(after)


async def test_the_anonymisation_is_audited_without_personal_data(
    client: AsyncClient, staff: Staff, make_user: MakeUser, db_session: AsyncSession
) -> None:
    target = await make_user("jane.doe@example.com", "viewer")

    await _anonymise(client, staff.admin, target.id)

    entry = await db_session.scalar(select(AuditLog).where(AuditLog.action == "user_anonymised"))
    assert entry is not None
    assert entry.entity_id == target.id
    assert "jane.doe" not in json.dumps(entry.extra_data)


async def test_anonymising_twice_changes_nothing_the_second_time(
    client: AsyncClient, staff: Staff, make_user: MakeUser, db_session: AsyncSession
) -> None:
    target = await make_user("jane.doe@example.com", "viewer")
    await _anonymise(client, staff.admin, target.id)
    audit_entries = await _audit_count(db_session)

    again = await _anonymise(client, staff.admin, target.id)

    assert again.status_code == 200
    assert again.json() == {"user_id": target.id, "already_anonymised": True}
    assert await _audit_count(db_session) == audit_entries


async def test_emails_sent_to_the_person_are_redacted(
    client: AsyncClient, staff: Staff, roles: dict[str, Role], db_session: AsyncSession
) -> None:
    invited = await client.post(
        f"{API}/users/invite",
        json={"email": "new.hire@example.com", "full_name": "New Hire", "role_id": roles["viewer"].id},
        headers=staff.admin,
    )
    assert invited.status_code == 201
    assert await db_session.scalar(select(func.count()).select_from(EmailOutbox)) == 1

    await _anonymise(client, staff.admin, invited.json()["id"])

    db_session.expire_all()
    message = await db_session.scalar(select(EmailOutbox))
    assert message is not None
    assert "new.hire" not in message.to_address
    assert "New Hire" not in message.body
    assert "token=" not in message.body


async def test_the_last_active_admin_cannot_be_anonymised(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser
) -> None:
    admin = await auth_headers("admin")
    admin_id = (await client.get(f"{API}/auth/me", headers=admin)).json()["id"]

    refused = await _anonymise(client, admin, admin_id)
    await make_user("second.admin@example.com", "admin")
    allowed = await _anonymise(client, admin, admin_id)

    assert refused.status_code == 409
    assert "last active administrator" in refused.json()["detail"]
    assert allowed.status_code == 200


async def test_an_inactive_admin_does_not_count_as_the_last_one(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser, db_session: AsyncSession
) -> None:
    admin = await auth_headers("admin")
    retired = await make_user("retired.admin@example.com", "admin")
    retired.is_active = False
    await db_session.commit()

    response = await _anonymise(client, admin, retired.id)

    assert response.status_code == 200


async def test_supplier_contact_export_and_anonymisation_keep_the_supplier_and_its_orders(
    client: AsyncClient, staff: Staff, supplier: Supplier, product: Any, db_session: AsyncSession
) -> None:
    supplier.contact_name = "Sam Supplier"
    supplier.phone = "555-0100"
    supplier.address = "1 Warehouse Road"
    await db_session.commit()
    po = await ordered_po(client, staff, supplier, product)
    await client.patch(f"{API}/suppliers/{supplier.id}", json={"contact_name": "Sam Q. Supplier"}, headers=staff.admin)

    supplier_id = supplier.id
    exported = await client.get(f"{GDPR}/suppliers/{supplier_id}/contact/export", headers=staff.admin)
    response = await client.post(f"{GDPR}/suppliers/{supplier_id}/contact/anonymise", headers=staff.admin)

    assert exported.json()["contact"]["email"] == "supplier@example.com"
    assert exported.json()["contact"]["contact_name"] == "Sam Q. Supplier"
    assert response.json()["already_anonymised"] is False
    db_session.expire_all()
    kept = await db_session.get(Supplier, supplier_id)
    assert kept is not None
    assert (kept.name, kept.address) == ("Test Supplier", "1 Warehouse Road")
    assert (kept.contact_name, kept.email, kept.phone) == (ANONYMISED_CONTACT, None, None)
    assert (await db_session.get(PurchaseOrder, po["id"])) is not None
    audit = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.entity_type == "supplier", AuditLog.entity_id == supplier_id)
            )
        )
        .scalars()
        .all()
    )
    assert "Sam" not in json.dumps([entry.extra_data for entry in audit])
    again = await client.post(f"{GDPR}/suppliers/{supplier_id}/contact/anonymise", headers=staff.admin)
    assert again.json() == {"supplier_id": supplier_id, "already_anonymised": True}


async def test_supplier_contact_anonymisation_also_closes_the_suppliers_portal_accounts(
    client: AsyncClient, staff: Staff, supplier: Supplier, roles: dict[str, Role], db_session: AsyncSession
) -> None:
    portal_user = User(
        email="portal@supplier.example",
        full_name="Portal Person",
        hashed_password="x",
        role_id=roles["supplier"].id,
        supplier_id=supplier.id,
    )
    db_session.add(portal_user)
    await db_session.commit()
    portal_user_id, supplier_id = portal_user.id, supplier.id

    exported = await client.get(f"{GDPR}/suppliers/{supplier_id}/contact/export", headers=staff.admin)
    await client.post(f"{GDPR}/suppliers/{supplier_id}/contact/anonymise", headers=staff.admin)

    assert exported.json()["portal_accounts"][0]["profile"]["email"] == "portal@supplier.example"
    db_session.expire_all()
    closed = await db_session.get(User, portal_user_id)
    assert closed is not None
    assert (closed.is_active, closed.full_name, closed.supplier_id) == (False, ANONYMISED_NAME, supplier_id)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            {"changes": {"full_name": {"from": "Jane Doe", "to": "J. Doe"}}},
            {"changes": {"full_name": {"from": "[x]", "to": "J. Doe"}}},
        ),
        (["mail JANE.DOE@example.com now"], ["mail [e] now"]),
        ({"count": 3, "ok": True, "none": None}, {"count": 3, "ok": True, "none": None}),
    ],
)
def test_redaction_walks_nested_json_and_ignores_case(value: Any, expected: Any) -> None:
    needles = {"Jane Doe": "[x]", "jane.doe@example.com": "[e]"}

    assert redact_json(value, needles) == expected
