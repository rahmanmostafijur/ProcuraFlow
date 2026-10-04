from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_ENVIRONMENTS = frozenset({"development", "test"})
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

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    default_admin_email: str = "admin@procuraflow.com"
    default_admin_password: str = "change-this-admin-password"

    @property
    def is_local(self) -> bool:
        return self.environment in LOCAL_ENVIRONMENTS

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

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
