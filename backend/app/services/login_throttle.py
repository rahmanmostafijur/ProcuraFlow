import hashlib
import hmac
import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.login_failure import LoginFailure

ACCOUNT_SCOPE = "account"
IP_SCOPE = "ip"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LoginThrottle:
    """Throttles credential guessing by account and, as a weaker second layer, by client address.

    Failures live in Postgres, so the counts survive restarts and are shared by every instance.
    The account limit is the dependable one: a client address can be spoofed by anyone who reaches
    the API directly (see app/core/proxy.py), so the address limit only slows broad spraying across
    many accounts. Locking an account also lets someone keep a known email locked for the window;
    that is the usual trade-off, kept short by a modest window.

    A blocked request only reads, so an attacker cannot grow the table by hammering a locked
    account, and expired rows are purged whenever a new failure is recorded. The check and the
    recording are separate steps, so attempts racing each other can slip a few past the limit
    before their failures land; this is a rate control, not an exact counter. It deliberately takes
    no per-account lock, which would let an attacker park connections on a victim's lock.
    """

    def __init__(
        self,
        max_failures_per_account: int,
        max_failures_per_ip: int,
        window_seconds: int,
        secret: str,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if min(max_failures_per_account, max_failures_per_ip, window_seconds) < 1:
            raise ValueError("throttle limits and window must be at least 1")
        self._max_failures = {ACCOUNT_SCOPE: max_failures_per_account, IP_SCOPE: max_failures_per_ip}
        self._window = timedelta(seconds=window_seconds)
        self._secret = secret.encode()
        self._clock = clock

    def _key(self, scope: str, value: str) -> str:
        normalised = value.strip().lower() if scope == ACCOUNT_SCOPE else value
        return hmac.new(self._secret, f"{scope}:{normalised}".encode(), hashlib.sha256).hexdigest()

    async def _wait_seconds(self, db: AsyncSession, scope: str, value: str) -> int:
        limit = self._max_failures[scope]
        now = self._clock()
        recent = (
            await db.execute(
                select(LoginFailure.failed_at)
                .where(
                    LoginFailure.scope == scope,
                    LoginFailure.key_hash == self._key(scope, value),
                    LoginFailure.failed_at > now - self._window,
                )
                .order_by(LoginFailure.failed_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        if len(recent) < limit:
            return 0
        # Blocked until the failure that tipped it over the limit leaves the window.
        return max(1, math.ceil((recent[-1] + self._window - now).total_seconds()))

    async def retry_after(self, db: AsyncSession, email: str, ip: str | None) -> int:
        """Seconds until a sign-in for `email` from `ip` may be tried; 0 when it is not blocked."""
        waits = [await self._wait_seconds(db, ACCOUNT_SCOPE, email)]
        if ip is not None:
            waits.append(await self._wait_seconds(db, IP_SCOPE, ip))
        return max(waits)

    async def record_failure(self, db: AsyncSession, email: str, ip: str | None) -> None:
        """Count a rejected attempt. The caller commits, so the record outlives the 401 it raises."""
        now = self._clock()
        db.add(LoginFailure(scope=ACCOUNT_SCOPE, key_hash=self._key(ACCOUNT_SCOPE, email), failed_at=now))
        if ip is not None:
            db.add(LoginFailure(scope=IP_SCOPE, key_hash=self._key(IP_SCOPE, ip), failed_at=now))
        await db.flush()
        await db.execute(delete(LoginFailure).where(LoginFailure.failed_at <= now - self._window))

    async def record_success(self, db: AsyncSession, email: str) -> None:
        # Only the account resets: one good login must not erase an address's spraying history.
        await db.execute(
            delete(LoginFailure).where(
                LoginFailure.scope == ACCOUNT_SCOPE, LoginFailure.key_hash == self._key(ACCOUNT_SCOPE, email)
            )
        )


def get_login_throttle() -> LoginThrottle:
    settings = get_settings()
    return LoginThrottle(
        max_failures_per_account=settings.login_max_failures_per_account,
        max_failures_per_ip=settings.login_max_failures_per_ip,
        window_seconds=settings.login_lockout_seconds,
        secret=settings.jwt_secret_key,
    )
