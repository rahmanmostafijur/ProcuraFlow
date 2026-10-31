import re
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email import EmailOutbox, UserToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from tests.fixture_types import AuthHeaders, MakeUser

REQUEST = "/api/v1/auth/password-reset/request"
CONFIRM = "/api/v1/auth/password-reset/confirm"
ACCEPT = "/api/v1/auth/invitations/accept"
NEW_PASSWORD = "BrandNewPass456!"


async def _token_from_outbox(db: AsyncSession, to_address: str) -> str:
    rows = (
        (await db.execute(select(EmailOutbox).where(EmailOutbox.to_address == to_address).order_by(EmailOutbox.id)))
        .scalars()
        .all()
    )
    match = re.search(r"token=([\w-]+)", rows[-1].body)
    assert match, rows[-1].body
    return match.group(1)


async def _login_status(client: AsyncClient, email: str, password: str) -> int:
    return (await client.post("/api/v1/auth/login", json={"email": email, "password": password})).status_code


async def test_reset_request_answers_the_same_for_unknown_and_known_emails(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    await make_user("known@example.com", "admin")
    known = await client.post(REQUEST, json={"email": "known@example.com"})
    unknown = await client.post(REQUEST, json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    sent = (await db_session.execute(select(EmailOutbox.to_address))).scalars().all()
    assert sent == ["known@example.com"]


async def test_reset_changes_the_password_and_revokes_sessions(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    await make_user("ada@example.com", "admin")
    assert await _login_status(client, "ada@example.com", "TestPass123!") == 200
    await client.post(REQUEST, json={"email": "ada@example.com"})
    token = await _token_from_outbox(db_session, "ada@example.com")

    response = await client.post(CONFIRM, json={"token": token, "password": NEW_PASSWORD})

    assert response.status_code == 204
    assert await _login_status(client, "ada@example.com", "TestPass123!") == 401
    assert await _login_status(client, "ada@example.com", NEW_PASSWORD) == 200
    revoked = (await db_session.execute(select(RefreshToken.revoked_at))).scalars().all()
    assert revoked
    assert any(value is not None for value in revoked)


async def test_a_reset_token_works_only_once(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    await make_user("ada@example.com", "admin")
    await client.post(REQUEST, json={"email": "ada@example.com"})
    token = await _token_from_outbox(db_session, "ada@example.com")
    assert (await client.post(CONFIRM, json={"token": token, "password": NEW_PASSWORD})).status_code == 204
    again = await client.post(CONFIRM, json={"token": token, "password": "AnotherPass789!"})
    assert again.status_code == 400
    assert await _login_status(client, "ada@example.com", NEW_PASSWORD) == 200


async def test_an_expired_reset_token_is_refused(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    await make_user("ada@example.com", "admin")
    await client.post(REQUEST, json={"email": "ada@example.com"})
    token = await _token_from_outbox(db_session, "ada@example.com")
    await db_session.execute(update(UserToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    await db_session.commit()
    response = await client.post(CONFIRM, json={"token": token, "password": NEW_PASSWORD})
    assert response.status_code == 400


async def test_a_new_request_voids_the_earlier_token(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    await make_user("ada@example.com", "admin")
    await client.post(REQUEST, json={"email": "ada@example.com"})
    first = await _token_from_outbox(db_session, "ada@example.com")
    await client.post(REQUEST, json={"email": "ada@example.com"})
    assert (await client.post(CONFIRM, json={"token": first, "password": NEW_PASSWORD})).status_code == 400


async def test_reset_requests_are_throttled_per_account(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    await make_user("ada@example.com", "admin")
    for _ in range(6):
        assert (await client.post(REQUEST, json={"email": "ada@example.com"})).status_code == 202
    sent = (await db_session.execute(select(EmailOutbox))).scalars().all()
    assert len(sent) == 3


async def test_a_token_for_one_purpose_does_not_work_for_the_other(
    client: AsyncClient, auth_headers: AuthHeaders, make_user: MakeUser, db_session: AsyncSession
) -> None:
    await make_user("ada@example.com", "admin")
    await client.post(REQUEST, json={"email": "ada@example.com"})
    token = await _token_from_outbox(db_session, "ada@example.com")
    assert (await client.post(ACCEPT, json={"token": token, "password": NEW_PASSWORD})).status_code == 400


async def test_an_admin_invites_a_user_who_then_chooses_a_password(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    admin = await auth_headers("admin")
    role_id = (await db_session.execute(select(User.role_id).limit(1))).scalar_one()

    created = await client.post(
        "/api/v1/users/invite",
        headers=admin,
        json={"email": "new@example.com", "full_name": "New Person", "role_id": role_id},
    )
    assert created.status_code == 201
    token = await _token_from_outbox(db_session, "new@example.com")
    assert await _login_status(client, "new@example.com", "guess") == 401

    assert (await client.post(ACCEPT, json={"token": token, "password": NEW_PASSWORD})).status_code == 204
    assert await _login_status(client, "new@example.com", NEW_PASSWORD) == 200


async def test_inviting_needs_user_manage_permission(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    viewer = await auth_headers("viewer")
    response = await client.post(
        "/api/v1/users/invite", headers=viewer, json={"email": "x@example.com", "full_name": "X", "role_id": 1}
    )
    assert response.status_code == 403


async def test_inviting_an_existing_email_is_refused(
    client: AsyncClient, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    admin = await auth_headers("admin")
    role_id = (await db_session.execute(select(User.role_id).limit(1))).scalar_one()
    response = await client.post(
        "/api/v1/users/invite",
        headers=admin,
        json={"email": "admin@example.com", "full_name": "Dup", "role_id": role_id},
    )
    assert response.status_code == 409


async def test_change_password_requires_the_current_one(client: AsyncClient, auth_headers: AuthHeaders) -> None:
    headers = await auth_headers("admin")
    wrong = await client.post(
        "/api/v1/auth/change-password", headers=headers, json={"current_password": "nope", "new_password": NEW_PASSWORD}
    )
    assert wrong.status_code == 400
    ok = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "TestPass123!", "new_password": NEW_PASSWORD},
    )
    assert ok.status_code == 204
    assert await _login_status(client, "admin@example.com", NEW_PASSWORD) == 200


async def test_change_password_needs_sign_in(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/change-password", json={"current_password": "a", "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 401
