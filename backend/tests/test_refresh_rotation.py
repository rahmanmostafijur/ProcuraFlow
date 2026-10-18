from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookie import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH
from app.core.config import get_settings
from app.core.security import _create_token, decode_token
from app.main import app
from app.models.audit import AuditLog
from app.models.refresh_token import RefreshToken

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
PASSWORD = "CorrectPass1!"
EMAIL = "user@example.com"


def _cookie_value(response) -> str:
    return response.headers["set-cookie"].split(";")[0].split("=", 1)[1]


async def _login(client: AsyncClient) -> str:
    response = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    return _cookie_value(response)


async def _present(client: AsyncClient, token: str):
    """Send `token` as the refresh cookie, as a browser holding exactly that token would."""
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE_NAME, token, path=REFRESH_COOKIE_PATH)
    return await client.post(REFRESH_URL)


async def _rows(db_session: AsyncSession):
    db_session.expire_all()
    result = await db_session.execute(
        select(
            RefreshToken.jti, RefreshToken.family_id, RefreshToken.used_at, RefreshToken.revoked_at
        ).order_by(RefreshToken.id)
    )
    return result.all()


@pytest.fixture
async def user(make_user):
    return await make_user(EMAIL, "viewer", password=PASSWORD)


@pytest.fixture
def no_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", 0)


async def test_login_records_an_unused_token_row_matching_the_issued_token(
    client: AsyncClient, db_session: AsyncSession, user
):
    token = await _login(client)

    (row,) = await _rows(db_session)
    claims = decode_token(token, expected_type="refresh")
    assert claims["jti"] == row.jti
    assert claims["fam"] == row.family_id
    assert row.used_at is None and row.revoked_at is None


async def test_refresh_rotates_the_token_within_the_same_family(
    client: AsyncClient, db_session: AsyncSession, user
):
    first = await _login(client)

    response = await _present(client, first)

    assert response.status_code == 200
    second = _cookie_value(response)
    assert second != first
    old_row, new_row = await _rows(db_session)
    assert old_row.family_id == new_row.family_id
    assert old_row.used_at is not None
    assert new_row.used_at is None
    assert decode_token(second, expected_type="refresh")["jti"] == new_row.jti


async def test_a_replay_within_the_grace_window_is_not_treated_as_theft(client: AsyncClient, user):
    first = await _login(client)

    assert (await _present(client, first)).status_code == 200
    assert (await _present(client, first)).status_code == 200


async def test_a_replay_after_the_grace_window_revokes_the_whole_family(
    client: AsyncClient, db_session: AsyncSession, user, no_grace
):
    first = await _login(client)
    second = _cookie_value(await _present(client, first))

    replay = await _present(client, first)
    successor = await _present(client, second)

    assert replay.status_code == 401
    assert successor.status_code == 401
    assert all(row.revoked_at is not None for row in await _rows(db_session))


async def test_reuse_is_audited_even_though_the_request_is_rejected(
    client: AsyncClient, db_session: AsyncSession, user, no_grace
):
    user_id = user.id  # read before the helpers expire the session's objects
    first = await _login(client)
    await _present(client, first)

    await _present(client, first)

    db_session.expire_all()
    actions = (await db_session.execute(select(AuditLog.action).where(AuditLog.user_id == user_id))).scalars().all()
    assert "refresh_token_reuse" in actions


async def test_logout_revokes_the_session_so_the_old_token_stops_working(
    client: AsyncClient, db_session: AsyncSession, user
):
    token = await _login(client)

    assert (await client.post(LOGOUT_URL)).status_code == 204

    assert (await _present(client, token)).status_code == 401
    assert all(row.revoked_at is not None for row in await _rows(db_session))


async def test_logging_out_one_device_leaves_other_sessions_alone(client: AsyncClient, user):
    await _login(client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        second_device = await _login(other)

        assert (await client.post(LOGOUT_URL)).status_code == 204

        assert (await _present(other, second_device)).status_code == 200


async def test_a_token_without_an_id_is_rejected(client: AsyncClient, user):
    legacy = _create_token(str(user.id), timedelta(days=1), "refresh")

    assert (await _present(client, legacy)).status_code == 401


async def test_a_validly_signed_token_with_no_stored_row_is_rejected(client: AsyncClient, user):
    forged = _create_token(
        str(user.id), timedelta(days=1), "refresh", extra_claims={"jti": "never-issued", "fam": "none"}
    )

    assert (await _present(client, forged)).status_code == 401


async def test_a_token_signed_with_another_key_is_rejected(client: AsyncClient, user):
    forged = jwt.encode(
        {
            "sub": str(user.id),
            "type": "refresh",
            "jti": "x",
            "fam": "y",
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
        },
        "a-completely-different-signing-key-0123456789",
        algorithm="HS256",
    )

    assert (await _present(client, forged)).status_code == 401


async def test_a_deactivated_user_cannot_refresh(client: AsyncClient, db_session: AsyncSession, user):
    token = await _login(client)
    user.is_active = False
    await db_session.commit()

    assert (await _present(client, token)).status_code == 401


async def test_expired_token_rows_are_purged_at_login(client: AsyncClient, db_session: AsyncSession, user):
    db_session.add(
        RefreshToken(
            jti="long-expired",
            family_id="old-family",
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
    )
    await db_session.commit()

    await _login(client)

    jtis = [row.jti for row in await _rows(db_session)]
    assert "long-expired" not in jtis
    assert len(jtis) == 1
