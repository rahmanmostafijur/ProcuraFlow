import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.email import UserToken
from app.models.user import User
from app.services.email_service import queue_email
from app.services.refresh_token_service import revoke_all_sessions

PURPOSE_RESET = "reset"
PURPOSE_INVITE = "invite"
RESET_TTL = timedelta(minutes=30)
INVITE_TTL = timedelta(days=7)
# Reset requests per account within the window; further requests are ignored without telling the requester.
MAX_RESET_REQUESTS = 3
RESET_REQUEST_WINDOW = timedelta(hours=1)

_EXPIRES_IN = {PURPOSE_RESET: "30 minutes", PURPOSE_INVITE: "7 days"}
_TEMPLATE = {PURPOSE_RESET: "password_reset", PURPOSE_INVITE: "invitation"}


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


async def _issue(db: AsyncSession, user: User, purpose: str, ttl: timedelta) -> str:
    """Create a token, voiding the user's earlier unused ones of that purpose. Returns the raw value to email."""
    await db.execute(
        update(UserToken)
        .where(UserToken.user_id == user.id, UserToken.purpose == purpose, UserToken.used_at.is_(None))
        .values(used_at=_now())
    )
    raw = secrets.token_urlsafe(32)
    db.add(UserToken(user_id=user.id, purpose=purpose, token_hash=_hash(raw), expires_at=_now() + ttl))
    return raw


async def _send_link(db: AsyncSession, user: User, purpose: str, raw: str, extra: dict[str, str]) -> None:
    path = "reset-password" if purpose == PURPOSE_RESET else "accept-invitation"
    link = f"{get_settings().app_base_url.rstrip('/')}/{path}?token={raw}"
    context = {"full_name": user.full_name, "link": link, "expires_in": _EXPIRES_IN[purpose]} | extra
    await queue_email(db, user.email, _TEMPLATE[purpose], context)


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """Queue a reset email if the account exists and is active. The caller answers identically either way."""
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.is_active:
        return
    recent = await db.scalar(
        select(func.count())
        .select_from(UserToken)
        .where(
            UserToken.user_id == user.id,
            UserToken.purpose == PURPOSE_RESET,
            UserToken.created_at > _now() - RESET_REQUEST_WINDOW,
        )
    )
    if (recent or 0) >= MAX_RESET_REQUESTS:
        return
    raw = await _issue(db, user, PURPOSE_RESET, RESET_TTL)
    await _send_link(db, user, PURPOSE_RESET, raw, {})


async def invite_user(db: AsyncSession, user: User, company_name: str) -> None:
    raw = await _issue(db, user, PURPOSE_INVITE, INVITE_TTL)
    await _send_link(db, user, PURPOSE_INVITE, raw, {"company_name": company_name})


async def consume_token(db: AsyncSession, raw: str, purpose: str, new_password: str) -> User | None:
    """Spend a valid token and set the password. None when the token is unknown, used, expired or inactive.

    The single UPDATE ... WHERE used_at IS NULL is the atomic step: of two racing requests, one gets the row.
    """
    claimed = await db.execute(
        update(UserToken)
        .where(
            UserToken.token_hash == _hash(raw),
            UserToken.purpose == purpose,
            UserToken.used_at.is_(None),
            UserToken.expires_at > _now(),
        )
        .values(used_at=_now())
        .returning(UserToken.user_id)
    )
    user_id = claimed.scalar_one_or_none()
    if user_id is None:
        return None
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    user.hashed_password = hash_password(new_password)
    await revoke_all_sessions(db, user.id)
    return user
