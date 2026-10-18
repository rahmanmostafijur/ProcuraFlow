import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookie import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH
from app.main import app
from app.models.audit import AuditLog

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
OLD_PASSWORD = "OriginalPass1!"
NEW_PASSWORD = "BrandNewSecret99!"


def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _sign_in_on_a_new_device(email: str, password: str = OLD_PASSWORD) -> str:
    async with _new_client() as device:
        response = await device.post(LOGIN_URL, json={"email": email, "password": password})
        assert response.status_code == 200
        return response.headers["set-cookie"].split(";")[0].split("=", 1)[1]


async def _refresh_status(token: str) -> int:
    async with _new_client() as device:
        device.cookies.set(REFRESH_COOKIE_NAME, token, path=REFRESH_COOKIE_PATH)
        return (await device.post(REFRESH_URL)).status_code


@pytest.fixture
async def target(make_user):
    return await make_user("target@example.com", "viewer", password=OLD_PASSWORD)


@pytest.fixture
async def admin_headers(auth_headers):
    return await auth_headers("admin")


async def _admin_patch(client: AsyncClient, admin_headers, user_id: int, body: dict):
    response = await client.patch(f"/api/v1/users/{user_id}", json=body, headers=admin_headers)
    assert response.status_code == 200
    return response


async def test_changing_a_password_revokes_every_session_of_that_user(
    client: AsyncClient, admin_headers, target
):
    laptop = await _sign_in_on_a_new_device(target.email)
    phone = await _sign_in_on_a_new_device(target.email)

    await _admin_patch(client, admin_headers, target.id, {"password": NEW_PASSWORD})

    assert await _refresh_status(laptop) == 401
    assert await _refresh_status(phone) == 401


async def test_the_new_password_works_and_the_old_one_does_not(client: AsyncClient, admin_headers, target):
    await _admin_patch(client, admin_headers, target.id, {"password": NEW_PASSWORD})

    async with _new_client() as device:
        old = await device.post(LOGIN_URL, json={"email": target.email, "password": OLD_PASSWORD})
        new = await device.post(LOGIN_URL, json={"email": target.email, "password": NEW_PASSWORD})

    assert old.status_code == 401
    assert new.status_code == 200


async def test_other_users_keep_their_sessions(client: AsyncClient, admin_headers, make_user, target):
    bystander = await make_user("bystander@example.com", "viewer", password=OLD_PASSWORD)
    bystander_session = await _sign_in_on_a_new_device(bystander.email)

    await _admin_patch(client, admin_headers, target.id, {"password": NEW_PASSWORD})

    assert await _refresh_status(bystander_session) == 200


async def test_updates_that_touch_neither_password_nor_status_keep_sessions(
    client: AsyncClient, admin_headers, target
):
    session = await _sign_in_on_a_new_device(target.email)

    await _admin_patch(client, admin_headers, target.id, {"full_name": "Renamed Person"})

    assert await _refresh_status(session) == 200


async def test_deactivating_a_user_revokes_sessions_for_good_even_after_reactivation(
    client: AsyncClient, admin_headers, target
):
    session = await _sign_in_on_a_new_device(target.email)

    await _admin_patch(client, admin_headers, target.id, {"is_active": False})
    assert await _refresh_status(session) == 401

    await _admin_patch(client, admin_headers, target.id, {"is_active": True})
    assert await _refresh_status(session) == 401
    assert await _sign_in_on_a_new_device(target.email)  # a fresh sign-in is still possible


async def test_revocation_is_audited_separately_and_leaves_the_update_event_intact(
    client: AsyncClient, admin_headers, target, db_session: AsyncSession
):
    target_id = target.id
    await _sign_in_on_a_new_device(target.email)

    await _admin_patch(client, admin_headers, target_id, {"password": NEW_PASSWORD})

    db_session.expire_all()
    events = (
        await db_session.execute(
            select(AuditLog.action, AuditLog.extra_data).where(AuditLog.entity_id == target_id, AuditLog.entity_type == "user")
        )
    ).all()
    by_action = {event.action: event.extra_data for event in events}
    assert by_action["user_updated"] == {"changes": {"password": "changed"}}
    assert by_action["user_sessions_revoked"] == {"reasons": ["password_changed"]}


async def test_no_revocation_event_when_nothing_credential_related_changed(
    client: AsyncClient, admin_headers, target, db_session: AsyncSession
):
    target_id = target.id

    await _admin_patch(client, admin_headers, target_id, {"full_name": "Renamed Person"})

    db_session.expire_all()
    actions = (await db_session.execute(select(AuditLog.action).where(AuditLog.entity_id == target_id))).scalars().all()
    assert "user_sessions_revoked" not in actions
