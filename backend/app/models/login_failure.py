from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginFailure(Base):
    """One rejected sign-in attempt, counted per account and per client address by the login throttle.

    `key_hash` is an HMAC of the account email or client address, never the value itself, so
    attacker-typed text is not stored. Rows older than the lockout window are purged as new
    failures arrive.
    """

    __tablename__ = "login_failures"
    __table_args__ = (Index("ix_login_failures_scope_key_failed_at", "scope", "key_hash", "failed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
