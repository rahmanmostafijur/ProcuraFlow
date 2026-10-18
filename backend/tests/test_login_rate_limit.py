import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.login_failure import LoginFailure
from app.services.login_throttle import LoginThrottle

LOGIN_URL = "/api/v1/auth/login"
GOOD_PASSWORD = "CorrectPass1!"
SECRET = "unit-test-secret"


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def make_throttle(clock: FakeClock, *, per_account: int = 3, per_ip: int = 100, window: int = 60) -> LoginThrottle:
    return LoginThrottle(
        max_failures_per_account=per_account,
        max_failures_per_ip=per_ip,
        window_seconds=window,
        secret=SECRET,
        clock=clock,
    )


async def fail(throttle: LoginThrottle, db: AsyncSession, email: str, ip: str | None = "1.1.1.1") -> None:
    await throttle.record_failure(db, email, ip)
    await db.commit()


async def stored_keys(db: AsyncSession) -> list[tuple[str, str]]:
    db.expire_all()
    return [tuple(row) for row in (await db.execute(select(LoginFailure.scope, LoginFailure.key_hash))).all()]


async def test_failures_below_the_maximum_do_not_block(db_session: AsyncSession):
    throttle = make_throttle(FakeClock())
    await fail(throttle, db_session, "a@example.com")
    await fail(throttle, db_session, "a@example.com")

    assert await throttle.retry_after(db_session, "a@example.com", "1.1.1.1") == 0


async def test_reaching_the_maximum_blocks_and_reports_the_wait(db_session: AsyncSession):
    clock = FakeClock()
    throttle = make_throttle(clock)
    for _ in range(3):
        await fail(throttle, db_session, "a@example.com")
        clock.advance(10)

    assert await throttle.retry_after(db_session, "a@example.com", "9.9.9.9") == 30


async def test_the_block_lifts_once_the_window_has_passed(db_session: AsyncSession):
    clock = FakeClock()
    throttle = make_throttle(clock, per_account=2)
    await fail(throttle, db_session, "a@example.com")
    await fail(throttle, db_session, "a@example.com")

    clock.advance(61)

    assert await throttle.retry_after(db_session, "a@example.com", "1.1.1.1") == 0


async def test_accounts_are_throttled_independently_and_emails_are_normalised(db_session: AsyncSession):
    throttle = make_throttle(FakeClock(), per_account=1)
    await fail(throttle, db_session, "  User@Example.com ", ip=None)

    assert await throttle.retry_after(db_session, "user@example.com", None) > 0
    assert await throttle.retry_after(db_session, "other@example.com", None) == 0


async def test_an_address_that_sprays_many_accounts_is_blocked_for_new_accounts_too(db_session: AsyncSession):
    throttle = make_throttle(FakeClock(), per_account=5, per_ip=3)
    for index in range(3):
        await fail(throttle, db_session, f"user{index}@example.com", ip="9.9.9.9")

    assert await throttle.retry_after(db_session, "fresh@example.com", "9.9.9.9") > 0
    assert await throttle.retry_after(db_session, "fresh@example.com", "8.8.8.8") == 0


async def test_success_clears_the_account_but_not_the_address(db_session: AsyncSession):
    throttle = make_throttle(FakeClock(), per_account=1, per_ip=2)
    await fail(throttle, db_session, "user@example.com", ip="9.9.9.9")

    await throttle.record_success(db_session, "user@example.com")
    await db_session.commit()

    assert await throttle.retry_after(db_session, "user@example.com", "1.1.1.1") == 0
    await fail(throttle, db_session, "x@example.com", ip="9.9.9.9")
    assert await throttle.retry_after(db_session, "y@example.com", "9.9.9.9") > 0


async def test_an_unknown_client_address_is_never_counted_or_blocked(db_session: AsyncSession):
    throttle = make_throttle(FakeClock(), per_account=5, per_ip=1)
    await fail(throttle, db_session, "a@example.com", ip=None)
    await fail(throttle, db_session, "b@example.com", ip=None)

    assert {scope for scope, _ in await stored_keys(db_session)} == {"account"}
    assert await throttle.retry_after(db_session, "c@example.com", None) == 0


async def test_stored_keys_are_hashed_so_typed_emails_never_reach_the_table(db_session: AsyncSession):
    throttle = make_throttle(FakeClock())
    await fail(throttle, db_session, "victim@example.com", ip="203.0.113.7")

    keys = await stored_keys(db_session)

    assert len(keys) == 2
    for _, key_hash in keys:
        assert len(key_hash) == 64
        assert "victim" not in key_hash and "203.0.113.7" not in key_hash


async def test_expired_rows_are_purged_so_the_table_stays_bounded(db_session: AsyncSession):
    clock = FakeClock()
    throttle = make_throttle(clock, window=60)
    for index in range(5):
        await fail(throttle, db_session, f"user{index}@example.com")

    clock.advance(61)
    await fail(throttle, db_session, "latest@example.com")

    assert await db_session.scalar(select(func.count()).select_from(LoginFailure)) == 2


async def test_state_is_shared_between_application_instances_and_survives_restarts(session_factory):
    clock = FakeClock()
    async with session_factory() as first_instance_db:
        await fail(make_throttle(clock, per_account=2), first_instance_db, "a@example.com")
        await fail(make_throttle(clock, per_account=2), first_instance_db, "a@example.com")

    # A different process, with a brand-new throttle object and database session, sees the same state.
    async with session_factory() as second_instance_db:
        assert await make_throttle(clock, per_account=2).retry_after(second_instance_db, "a@example.com", "5.5.5.5") > 0


@pytest.fixture
async def registered_user(make_user):
    await make_user("user@example.com", "viewer", password=GOOD_PASSWORD)


def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _attempt(client: AsyncClient, email: str, password: str):
    return await client.post(LOGIN_URL, json={"email": email, "password": password})


async def test_account_is_locked_after_repeated_failures_even_for_the_right_password(
    client: AsyncClient, registered_user
):
    for _ in range(5):
        assert (await _attempt(client, "user@example.com", "wrong")).status_code == 401

    response = await _attempt(client, "user@example.com", GOOD_PASSWORD)

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    assert "too many" in response.json()["detail"].lower()
    assert "set-cookie" not in response.headers


async def test_unknown_emails_are_limited_the_same_way(client: AsyncClient, roles):
    for _ in range(5):
        assert (await _attempt(client, "ghost@example.com", "wrong")).status_code == 401

    assert (await _attempt(client, "ghost@example.com", "wrong")).status_code == 429


async def test_a_successful_login_resets_the_failure_count(client: AsyncClient, registered_user):
    for _ in range(4):
        await _attempt(client, "user@example.com", "wrong")
    assert (await _attempt(client, "user@example.com", GOOD_PASSWORD)).status_code == 200

    for _ in range(4):
        assert (await _attempt(client, "user@example.com", "wrong")).status_code == 401


async def test_one_address_trying_many_accounts_is_eventually_blocked(client: AsyncClient, roles):
    for index in range(20):
        assert (await _attempt(client, f"ghost{index}@example.com", "wrong")).status_code == 401

    assert (await _attempt(client, "someone-new@example.com", "wrong")).status_code == 429


async def test_other_accounts_are_unaffected_by_one_lockout(client: AsyncClient, registered_user, make_user):
    await make_user("other@example.com", "viewer", password=GOOD_PASSWORD)
    for _ in range(5):
        await _attempt(client, "user@example.com", "wrong")

    assert (await _attempt(client, "other@example.com", GOOD_PASSWORD)).status_code == 200


async def test_blocked_requests_write_nothing_so_an_attacker_cannot_grow_the_table(
    client: AsyncClient, registered_user, db_session: AsyncSession
):
    for _ in range(5):
        await _attempt(client, "user@example.com", "wrong")
    db_session.expire_all()
    rows_at_lockout = await db_session.scalar(select(func.count()).select_from(LoginFailure))

    for _ in range(10):
        assert (await _attempt(client, "user@example.com", "wrong")).status_code == 429

    db_session.expire_all()
    assert await db_session.scalar(select(func.count()).select_from(LoginFailure)) == rows_at_lockout


async def test_concurrent_wrong_attempts_lose_no_failure_records_and_end_up_locked(
    registered_user, db_session: AsyncSession
):
    """The limit is a rate control, not an exact counter: attempts racing the check can slip past it.
    What must hold is that every rejected credential is recorded and the account is locked afterwards."""

    async def one_attempt() -> int:
        async with _new_client() as browser:
            return (await _attempt(browser, "user@example.com", "wrong")).status_code

    statuses = await asyncio.gather(*[one_attempt() for _ in range(12)])

    assert set(statuses) <= {401, 429}
    assert statuses.count(401) >= 5
    db_session.expire_all()
    recorded = await db_session.scalar(
        select(func.count()).select_from(LoginFailure).where(LoginFailure.scope == "account")
    )
    assert recorded == statuses.count(401)
    async with _new_client() as browser:
        assert (await _attempt(browser, "user@example.com", GOOD_PASSWORD)).status_code == 429
