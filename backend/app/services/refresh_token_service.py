import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import TokenError, create_refresh_token, decode_token
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.audit_service import record_audit_event

TOKEN_ID_BYTES = 24
SESSION_ENDED = "Session expired. Please sign in again."


class RefreshTokenError(Exception):
    """The presented refresh token cannot be exchanged; the message is safe to show the client."""


@dataclass(frozen=True)
class RotationResult:
    user: User
    refresh_token: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def issue_refresh_token(db: AsyncSession, user_id: int, family_id: str | None = None) -> str:
    """Create and store a refresh token, starting a new family unless `family_id` continues one."""
    settings = get_settings()
    jti = secrets.token_urlsafe(TOKEN_ID_BYTES)
    family = family_id or str(uuid.uuid4())
    db.add(
        RefreshToken(
            jti=jti,
            family_id=family,
            user_id=user_id,
            expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    return create_refresh_token(str(user_id), jti=jti, family_id=family)


async def purge_expired_tokens(db: AsyncSession) -> None:
    """Expired tokens are already rejected by their signature; their rows only take space."""
    await db.execute(delete(RefreshToken).where(RefreshToken.expires_at < _now()))


async def _revoke_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def _claims(token: str) -> tuple[str, str]:
    try:
        payload = decode_token(token, expected_type="refresh")
    except TokenError as exc:
        raise RefreshTokenError(str(exc)) from exc
    jti, family = payload.get("jti"), payload.get("fam")
    if not jti or not family:
        # Issued before rotation existed; there is no stored row to check it against.
        raise RefreshTokenError("Invalid token")
    return jti, family


async def rotate_refresh_token(db: AsyncSession, token: str) -> RotationResult:
    """Exchange a refresh token for a successor, detecting replay of a token that was already used.

    Presenting a used token within the grace window is accepted again: React StrictMode, or two
    tabs refreshing at once, legitimately send the same token twice. Later than that, the token
    is treated as stolen and its whole family is revoked.
    """
    jti, _ = _claims(token)
    row = (
        await db.execute(select(RefreshToken).where(RefreshToken.jti == jti).with_for_update())
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        raise RefreshTokenError(SESSION_ENDED)

    now = _now()
    grace = timedelta(seconds=get_settings().refresh_reuse_grace_seconds)
    if row.used_at is not None and now - row.used_at >= grace:
        await _revoke_family(db, row.family_id)
        await record_audit_event(
            db,
            user_id=row.user_id,
            action="refresh_token_reuse",
            entity_type="user",
            entity_id=row.user_id,
            extra_data={"family_id": row.family_id},
        )
        # Commit before rejecting: the revocation and the audit record must outlive the 401.
        await db.commit()
        raise RefreshTokenError(SESSION_ENDED)

    user = (
        await db.execute(select(User).options(selectinload(User.role)).where(User.id == row.user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise RefreshTokenError("User is no longer active")

    if row.used_at is None:
        row.used_at = now
    successor = await issue_refresh_token(db, user.id, family_id=row.family_id)
    await db.commit()
    return RotationResult(user=user, refresh_token=successor)


async def revoke_session(db: AsyncSession, token: str | None) -> None:
    """End the session a refresh token belongs to. Silent for missing, malformed or unknown tokens."""
    if not token:
        return
    try:
        jti, family = _claims(token)
    except RefreshTokenError:
        return
    owned = (await db.execute(select(RefreshToken.id).where(RefreshToken.jti == jti))).first()
    if owned is None:
        return
    await _revoke_family(db, family)
    await db.commit()
