import asyncio
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
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


def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _refresh_with(token: str):
    """Refresh as a separate browser (its own cookie jar) holding exactly `token`."""
    async with _new_client() as other:
        return await _present(other, token)


async def _live_count(db_session: AsyncSession) -> int:
    """Tokens that could still be exchanged: neither used nor revoked. A healthy session has exactly one."""
    return sum(1 for row in await _rows(db_session) if row.used_at is None and row.revoked_at is None)


@pytest.fixture
def long_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keeps every request of a test inside the grace window, so outcomes never depend on timing."""
    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", 300)


async def test_a_grace_window_replay_gets_an_access_token_but_no_refresh_token(
    client: AsyncClient, db_session: AsyncSession, user, long_grace
):
    first = await _login(client)
    rotated = await _present(client, first)

    replay = await _refresh_with(first)

    assert rotated.status_code == 200 and "set-cookie" in rotated.headers
    assert replay.status_code == 200
    assert "access_token" in replay.json()
    assert "set-cookie" not in replay.headers
    assert len(await _rows(db_session)) == 2
    assert await _live_count(db_session) == 1


async def test_a_grace_window_replay_cannot_fork_the_chain(
    client: AsyncClient, db_session: AsyncSession, user, long_grace
):
    first = await _login(client)
    legit = _cookie_value(await _present(client, first))
    await _refresh_with(first)  # the replay

    for _ in range(3):
        legit = _cookie_value(await _refresh_with(legit))
        assert await _live_count(db_session) == 1


async def test_concurrent_refreshes_with_one_token_rotate_it_exactly_once(
    client: AsyncClient, db_session: AsyncSession, user, long_grace
):
    token = await _login(client)

    responses = await asyncio.gather(*[_refresh_with(token) for _ in range(5)])

    assert [response.status_code for response in responses] == [200] * 5
    assert sum("set-cookie" in response.headers for response in responses) == 1
    assert len(await _rows(db_session)) == 2
    assert await _live_count(db_session) == 1


async def test_a_browser_refreshing_twice_at_once_keeps_the_canonical_cookie(
    client: AsyncClient, db_session: AsyncSession, user, long_grace
):
    """Two tabs, or React StrictMode, send the same cookie together; the jar must end up on the successor."""
    await _login(client)

    first, second = await asyncio.gather(client.post(REFRESH_URL), client.post(REFRESH_URL))

    assert first.status_code == second.status_code == 200
    assert ("set-cookie" in first.headers) != ("set-cookie" in second.headers)
    # A Set-Cookie on the next refresh proves the jar held the unused successor, not the rotated-away token.
    follow_up = await client.post(REFRESH_URL)
    assert follow_up.status_code == 200 and "set-cookie" in follow_up.headers
    assert len(await _rows(db_session)) == 3
    assert await _live_count(db_session) == 1


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
    async with _new_client() as other:
        second_device = await _login(other)

        assert (await client.post(LOGOUT_URL)).status_code == 204

        assert (await _present(other, second_device)).status_code == 200


async def test_logging_out_with_an_older_token_still_ends_the_whole_session(client: AsyncClient, user, long_grace):
    first = await _login(client)
    successor = _cookie_value(await _present(client, first))

    async with _new_client() as browser:
        browser.cookies.set(REFRESH_COOKIE_NAME, first, path=REFRESH_COOKIE_PATH)
        assert (await browser.post(LOGOUT_URL)).status_code == 204

    assert (await _refresh_with(successor)).status_code == 401


async def test_reuse_in_one_login_leaves_the_users_other_devices_signed_in(
    client: AsyncClient, user, no_grace
):
    device_a = await _login(client)
    async with _new_client() as other:
        device_b = await _login(other)

    successor_a = _cookie_value(await _refresh_with(device_a))
    replay = await _refresh_with(device_a)

    assert replay.status_code == 401
    assert (await _refresh_with(successor_a)).status_code == 401
    assert (await _refresh_with(device_b)).status_code == 200


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


async def _age_session(db_session: AsyncSession, days: float) -> None:
    """Pretend the login happened `days` ago, as a real session would have by the time it is refreshed."""
    await db_session.execute(
        update(RefreshToken).values(family_started_at=datetime.now(timezone.utc) - timedelta(days=days))
    )
    await db_session.commit()


async def _session_starts(db_session: AsyncSession) -> list[datetime]:
    db_session.expire_all()
    result = await db_session.execute(select(RefreshToken.family_started_at).order_by(RefreshToken.id))
    return list(result.scalars().all())


async def test_login_stamps_when_the_session_started(client: AsyncClient, db_session: AsyncSession, user):
    before = datetime.now(timezone.utc)
    await _login(client)

    (started,) = await _session_starts(db_session)

    assert before - timedelta(seconds=5) <= started <= datetime.now(timezone.utc) + timedelta(seconds=5)


async def test_rotation_keeps_the_original_session_start(client: AsyncClient, db_session: AsyncSession, user):
    first = await _login(client)
    await _age_session(db_session, days=3)
    (original,) = await _session_starts(db_session)

    await _present(client, first)

    assert await _session_starts(db_session) == [original, original]


async def test_a_session_past_the_absolute_limit_is_rejected_and_revoked(
    client: AsyncClient, db_session: AsyncSession, user
):
    token = await _login(client)
    await _age_session(db_session, days=get_settings().session_absolute_days + 1)

    response = await _present(client, token)

    assert response.status_code == 401
    assert all(row.revoked_at is not None for row in await _rows(db_session))


async def test_a_session_within_the_absolute_limit_keeps_refreshing(client: AsyncClient, db_session: AsyncSession, user):
    token = await _login(client)
    await _age_session(db_session, days=get_settings().session_absolute_days - 1)

    assert (await _present(client, token)).status_code == 200


async def test_the_absolute_limit_is_configurable(
    client: AsyncClient, db_session: AsyncSession, user, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(get_settings(), "session_absolute_days", 1)
    token = await _login(client)
    await _age_session(db_session, days=2)

    assert (await _present(client, token)).status_code == 401


async def test_the_absolute_limit_also_ends_a_session_whose_token_is_replayed_in_the_grace_window(
    client: AsyncClient, db_session: AsyncSession, user, long_grace
):
    token = await _login(client)
    await _present(client, token)  # rotates; `token` is now used but still inside the grace window
    await _age_session(db_session, days=get_settings().session_absolute_days + 1)

    assert (await _refresh_with(token)).status_code == 401
