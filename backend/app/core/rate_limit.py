import math
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from functools import lru_cache

from app.core.config import get_settings

DEFAULT_MAX_TRACKED_KEYS = 10_000


class FailureLimiter:
    """Sliding-window counter of failures per key (an account, an address).

    State lives in this process: it resets on restart and is not shared between workers or
    instances, which is fine for a single-instance deployment and wrong for a scaled-out one.
    Memory is bounded: once `max_keys` are tracked, the least recently failing key is dropped.
    """

    def __init__(
        self,
        max_failures: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = DEFAULT_MAX_TRACKED_KEYS,
    ) -> None:
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._failures: OrderedDict[str, deque[float]] = OrderedDict()

    def _prune(self, failures: deque[float], now: float) -> None:
        while failures and failures[0] <= now - self._window_seconds:
            failures.popleft()

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again; 0 when it is not blocked."""
        failures = self._failures.get(key)
        if not failures:
            return 0
        now = self._clock()
        self._prune(failures, now)
        if len(failures) < self._max_failures:
            return 0
        # Blocked until the failure that tipped it over the limit leaves the window.
        return max(1, math.ceil(failures[-self._max_failures] + self._window_seconds - now))

    def record_failure(self, key: str) -> None:
        now = self._clock()
        failures = self._failures.setdefault(key, deque())
        self._prune(failures, now)
        failures.append(now)
        self._failures.move_to_end(key)
        while len(self._failures) > self._max_keys:
            self._failures.popitem(last=False)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)

    def tracked_keys(self) -> int:
        return len(self._failures)


class LoginAttemptGuard:
    """Throttles credential guessing by account and, as a weaker second layer, by address.

    The account limit is the dependable one: the client address comes from X-Forwarded-For, which
    a caller can spoof, so the address limit only slows broad spraying across many accounts.
    Locking an account also lets someone lock a victim out for the window; that is the usual
    trade-off, kept short by a modest window.
    """

    def __init__(
        self,
        max_failures_per_account: int,
        max_failures_per_ip: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._accounts = FailureLimiter(max_failures_per_account, window_seconds, clock)
        self._addresses = FailureLimiter(max_failures_per_ip, window_seconds, clock)

    @staticmethod
    def _account_key(email: str) -> str:
        return email.strip().lower()

    def retry_after(self, email: str, ip: str) -> int:
        return max(self._accounts.retry_after(self._account_key(email)), self._addresses.retry_after(ip))

    def record_failure(self, email: str, ip: str) -> None:
        self._accounts.record_failure(self._account_key(email))
        self._addresses.record_failure(ip)

    def record_success(self, email: str) -> None:
        # Only the account resets: one good login must not erase an address's spraying history.
        self._accounts.reset(self._account_key(email))


@lru_cache
def get_login_guard() -> LoginAttemptGuard:
    settings = get_settings()
    return LoginAttemptGuard(
        max_failures_per_account=settings.login_max_failures_per_account,
        max_failures_per_ip=settings.login_max_failures_per_ip,
        window_seconds=settings.login_lockout_seconds,
    )
