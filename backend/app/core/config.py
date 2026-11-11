from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

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
# Fragments that mark a secret as copied from an example file rather than generated.
WEAK_SECRET_MARKERS = ("changeme", "change-me", "change-this", "change_this", "insecure", "placeholder")
MIN_DISTINCT_SECRET_CHARACTERS = 10
# Database passwords that ship in example files, compose files and tutorials.
WEAK_DATABASE_PASSWORDS = frozenset(
    {"procuraflow", "postgres", "password", "admin", "root", "changeme", "change-me", "secret", "123456", "test"}
)
MIN_DATABASE_PASSWORD_LENGTH = 8
Environment = Literal["development", "test", "staging", "production"]
StorageBackendName = Literal["local", "s3"]
SECRET_HINT = 'generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'  # noqa: S105 - help text


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    environment: Environment = "production"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow"
    test_database_url: str = "postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow_test"
    # Optional direct (non-pooler) URL used only by migrations. Falls back to DATABASE_URL.
    migration_database_url: str | None = None

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
    # Placeholder only: the seed refuses it outside development/test (app/seeds/seed.py).
    default_admin_password: str = "change-this-admin-password"  # noqa: S105

    # Uploaded files (logo, attachments) when STORAGE_BACKEND is local. Relative paths are resolved from the
    # backend directory; containers mount a volume here.
    storage_local_path: str = "var/uploads"
    # "s3" stores files in any S3-compatible bucket (AWS S3, MinIO, Cloudflare R2, Backblaze B2) and needs the
    # S3_* settings below; they are checked at startup so a half-configured deployment fails immediately.
    storage_backend: StorageBackendName = "local"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # Outgoing email. Without SMTP_HOST (always the case in development and test) messages are logged, not sent.
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    email_from: str = "ProcuraFlow <no-reply@procuraflow.local>"
    # Base URL of the web app, used for links in emails (password reset, invitations).
    app_base_url: str = "http://localhost:5173"
    email_max_attempts: int = Field(default=5, ge=1)

    # Demo suppliers and products: seeded by default only in local environments. A deployment that
    # wants them (a public demo) must say so; a real one never gets them by accident.
    seed_demo_data: bool | None = None

    # Public demo: one-click role sign-in, destructive admin actions blocked, email logged only (see app/demo and
    # app/core/demo_guard.py). Off by default. In production it also needs ALLOW_DEMO_IN_PRODUCTION=true, because a
    # demo exposes sign-in without a password; see _require_safe_demo_mode.
    demo_mode: bool = False
    allow_demo_in_production: bool = False
    # Password of the seeded demo accounts. Unset: derived from JWT_SECRET_KEY (app/demo/accounts.py), so every
    # deployment has its own and none is written in the source. Demo accounts only sign in while DEMO_MODE is true.
    demo_password: str | None = Field(default=None, min_length=12)

    @field_validator("database_url", "test_database_url", "migration_database_url")
    @classmethod
    def _normalize_database_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_database_url(value)

    @property
    def is_local(self) -> bool:
        return self.environment in LOCAL_ENVIRONMENTS

    @property
    def migrations_database_url(self) -> str:
        return self.migration_database_url or self.database_url

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
    def _require_s3_settings_when_selected(self) -> "Settings":
        if self.storage_backend != "s3":
            return self
        required = {
            "S3_ENDPOINT_URL": self.s3_endpoint_url,
            "S3_BUCKET": self.s3_bucket,
            "S3_REGION": self.s3_region,
            "S3_ACCESS_KEY_ID": self.s3_access_key_id,
            "S3_SECRET_ACCESS_KEY": self.s3_secret_access_key,
        }
        missing = [name for name, value in required.items() if not value or not value.strip()]
        if missing:
            raise ValueError(f"STORAGE_BACKEND=s3 needs these settings: {', '.join(missing)}")
        if not (self.s3_endpoint_url or "").startswith(("https://", "http://")):
            raise ValueError("S3_ENDPOINT_URL must start with https:// (or http:// for a local MinIO)")
        return self

    @model_validator(mode="after")
    def _require_strong_secret_outside_local(self) -> "Settings":
        """Production rule 1: outside development and test, JWT_SECRET_KEY must be a generated secret.

        Refused: a known placeholder, anything containing a placeholder marker (for example "change-me"), fewer
        than MIN_JWT_SECRET_LENGTH characters, or fewer than MIN_DISTINCT_SECRET_CHARACTERS different characters.
        """
        if self.is_local:
            return self
        secret = self.jwt_secret_key
        if secret in PLACEHOLDER_JWT_SECRETS or any(marker in secret.lower() for marker in WEAK_SECRET_MARKERS):
            raise ValueError(
                f"JWT_SECRET_KEY is a known placeholder and cannot be used in {self.environment}; "
                f"set JWT_SECRET_KEY to a random value ({SECRET_HINT})"
            )
        if len(secret) < MIN_JWT_SECRET_LENGTH or len(set(secret)) < MIN_DISTINCT_SECRET_CHARACTERS:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters and not repetitive in "
                f"{self.environment}; set JWT_SECRET_KEY to a random value ({SECRET_HINT})"
            )
        return self

    @model_validator(mode="after")
    def _require_strong_database_password_outside_local(self) -> "Settings":
        """Production rule 2: outside development and test, the database password must not be a default.

        Refused: no password, one of WEAK_DATABASE_PASSWORDS (case-insensitive) or one shorter than
        MIN_DATABASE_PASSWORD_LENGTH characters. The message never repeats the password.
        """
        if self.is_local:
            return self
        for name, url in (("DATABASE_URL", self.database_url), ("MIGRATION_DATABASE_URL", self.migration_database_url)):
            if not url:  # an unset or empty MIGRATION_DATABASE_URL falls back to DATABASE_URL
                continue
            password = make_url(url).password
            if (
                not password
                or password.lower() in WEAK_DATABASE_PASSWORDS
                or len(password) < MIN_DATABASE_PASSWORD_LENGTH
            ):
                raise ValueError(
                    f"{name} has no password, a default one or a very short one, which cannot be used in "
                    f"{self.environment}; set a strong password for the database user"
                )
        return self

    @model_validator(mode="after")
    def _require_safe_demo_mode(self) -> "Settings":
        """Production rule 3: DEMO_MODE=true together with ENVIRONMENT=production is refused.

        A demo lets anyone sign in as any role without a password, so it must never switch on by a stray variable
        in a real deployment. A deliberate public demo hosted as production sets ALLOW_DEMO_IN_PRODUCTION=true as
        well. Development, test and staging need nothing extra.
        """
        if self.demo_mode and self.environment == "production" and not self.allow_demo_in_production:
            raise ValueError(
                "DEMO_MODE=true is refused when ENVIRONMENT=production: it lets visitors sign in without a "
                "password. Set ALLOW_DEMO_IN_PRODUCTION=true as well only for a public demo deployment"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
