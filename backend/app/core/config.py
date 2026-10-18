from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.database_url import normalize_database_url, uses_connection_pooler

LOCAL_ENVIRONMENTS = frozenset({"development", "test"})
LOCAL_CORS_ORIGINS = "http://localhost:5173,http://localhost:3000"
MIN_JWT_SECRET_LENGTH = 32
PLACEHOLDER_JWT_SECRETS = frozenset(
    {
        "insecure-dev-secret-change-me",
        "dev-secret-change-in-production",
        "change-this-to-a-random-secret-in-production",
    }
)
SECRET_HINT = 'generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    environment: Literal["development", "test", "staging", "production"] = "production"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow"
    test_database_url: str = "postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow_test"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    # Hard ceiling on a session however actively it is refreshed: a real sign-in is needed at least this often.
    session_absolute_days: int = Field(default=30, ge=1)
    # A refresh token seen again this soon after use is a double submit (two tabs, StrictMode), not theft.
    refresh_reuse_grace_seconds: int = 10

    # Failed sign-ins tolerated per account / per client address within the lockout window.
    login_max_failures_per_account: int = Field(default=5, ge=1)
    login_max_failures_per_ip: int = Field(default=20, ge=1)
    login_lockout_seconds: int = Field(default=900, ge=1)

    # How many reverse proxies in front of the app to trust for the client address (see app/core/proxy.py).
    # 0 ignores X-Forwarded-* entirely, which is right for local development and direct exposure.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)

    # Unset means "local dev origins" locally and "no cross-origin access" elsewhere: a deployed
    # frontend reaches the API through a same-origin proxy and needs no CORS at all.
    cors_origins: str | None = None

    default_admin_email: str = "admin@procuraflow.com"
    default_admin_password: str = "change-this-admin-password"

    # Demo suppliers and products: seeded by default only in local environments. A deployment that
    # wants them (a public demo) must say so; a real one never gets them by accident.
    seed_demo_data: bool | None = None

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def is_local(self) -> bool:
        return self.environment in LOCAL_ENVIRONMENTS

    @property
    def should_seed_demo_data(self) -> bool:
        return self.is_local if self.seed_demo_data is None else self.seed_demo_data

    @property
    def uses_connection_pooler(self) -> bool:
        return uses_connection_pooler(self.database_url)

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins
        if raw is None:
            raw = LOCAL_CORS_ORIGINS if self.is_local else ""
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _require_strong_secret_outside_local(self) -> "Settings":
        if self.is_local:
            return self
        if self.jwt_secret_key in PLACEHOLDER_JWT_SECRETS:
            raise ValueError(
                f"JWT_SECRET_KEY is a known placeholder and cannot be used in {self.environment}; "
                f"set JWT_SECRET_KEY to a random value ({SECRET_HINT})"
            )
        if len(self.jwt_secret_key) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters in {self.environment}; "
                f"set JWT_SECRET_KEY to a random value ({SECRET_HINT})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
