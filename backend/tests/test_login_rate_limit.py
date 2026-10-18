import pytest
from httpx import AsyncClient

from app.core.rate_limit import FailureLimiter, LoginAttemptGuard

LOGIN_URL = "/api/v1/auth/login"
GOOD_PASSWORD = "CorrectPass1!"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_limiter_allows_failures_below_the_maximum() -> None:
    limiter = FailureLimiter(max_failures=3, window_seconds=60, clock=FakeClock())
    limiter.record_failure("a")
    limiter.record_failure("a")

    assert limiter.retry_after("a") == 0


def test_limiter_blocks_at_the_maximum_and_reports_the_wait() -> None:
    clock = FakeClock()
    limiter = FailureLimiter(max_failures=3, window_seconds=60, clock=clock)
    for _ in range(3):
        limiter.record_failure("a")
        clock.advance(10)

    assert limiter.retry_after("a") == 30


def test_limiter_unblocks_once_the_window_has_passed() -> None:
    clock = FakeClock()
    limiter = FailureLimiter(max_failures=2, window_seconds=60, clock=clock)
    limiter.record_failure("a")
    limiter.record_failure("a")

    clock.advance(61)

    assert limiter.retry_after("a") == 0


def test_limiter_tracks_keys_independently() -> None:
    limiter = FailureLimiter(max_failures=1, window_seconds=60, clock=FakeClock())
    limiter.record_failure("a")

    assert limiter.retry_after("a") > 0
    assert limiter.retry_after("b") == 0


def test_limiter_reset_clears_a_key() -> None:
    limiter = FailureLimiter(max_failures=1, window_seconds=60, clock=FakeClock())
    limiter.record_failure("a")

    limiter.reset("a")

    assert limiter.retry_after("a") == 0


def test_limiter_bounds_memory_by_evicting_the_least_recent_keys() -> None:
    limiter = FailureLimiter(max_failures=1, window_seconds=60, clock=FakeClock(), max_keys=3)
    for key in ["a", "b", "c", "d"]:
        limiter.record_failure(key)

    assert limiter.tracked_keys() == 3
    assert limiter.retry_after("a") == 0
    assert limiter.retry_after("d") > 0


def test_guard_blocks_on_whichever_limit_is_stricter() -> None:
    guard = LoginAttemptGuard(
        max_failures_per_account=2, max_failures_per_ip=100, window_seconds=60, clock=FakeClock()
    )
    guard.record_failure("User@Example.com", "1.1.1.1")
    guard.record_failure("user@example.com", "2.2.2.2")

    assert guard.retry_after("USER@example.com", "3.3.3.3") > 0
    assert guard.retry_after("other@example.com", "3.3.3.3") == 0


def test_guard_blocks_an_address_that_sprays_many_accounts() -> None:
    guard = LoginAttemptGuard(
        max_failures_per_account=5, max_failures_per_ip=3, window_seconds=60, clock=FakeClock()
    )
    for index in range(3):
        guard.record_failure(f"user{index}@example.com", "9.9.9.9")

    assert guard.retry_after("fresh@example.com", "9.9.9.9") > 0
    assert guard.retry_after("fresh@example.com", "8.8.8.8") == 0


def test_guard_success_clears_the_account_but_not_the_address() -> None:
    guard = LoginAttemptGuard(
        max_failures_per_account=1, max_failures_per_ip=2, window_seconds=60, clock=FakeClock()
    )
    guard.record_failure("user@example.com", "9.9.9.9")
    guard.record_success("user@example.com")

    assert guard.retry_after("user@example.com", "1.1.1.1") == 0
    guard.record_failure("x@example.com", "9.9.9.9")
    assert guard.retry_after("y@example.com", "9.9.9.9") > 0


@pytest.fixture
async def registered_user(make_user):
    await make_user("user@example.com", "viewer", password=GOOD_PASSWORD)


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

    response = await _attempt(client, "ghost@example.com", "wrong")

    assert response.status_code == 429


async def test_a_successful_login_resets_the_failure_count(client: AsyncClient, registered_user):
    for _ in range(4):
        await _attempt(client, "user@example.com", "wrong")
    assert (await _attempt(client, "user@example.com", GOOD_PASSWORD)).status_code == 200

    for _ in range(4):
        assert (await _attempt(client, "user@example.com", "wrong")).status_code == 401


async def test_one_address_trying_many_accounts_is_eventually_blocked(client: AsyncClient, roles):
    for index in range(20):
        assert (await _attempt(client, f"ghost{index}@example.com", "wrong")).status_code == 401

    response = await _attempt(client, "someone-new@example.com", "wrong")

    assert response.status_code == 429


async def test_other_accounts_are_unaffected_by_one_lockout(client: AsyncClient, registered_user, make_user):
    await make_user("other@example.com", "viewer", password=GOOD_PASSWORD)
    for _ in range(5):
        await _attempt(client, "user@example.com", "wrong")

    response = await _attempt(client, "other@example.com", GOOD_PASSWORD)

    assert response.status_code == 200
