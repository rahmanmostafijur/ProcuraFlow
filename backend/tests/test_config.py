from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG_SECRET = "k3Vq9xLr0TzP7mWb2NcY8sHd5FgJ1aUe6RoXiQ4vEyZt"
STRONG_DATABASE_URL = "postgresql+asyncpg://procuraflow:Zq8vL2mN7xR4tW9k@db.internal:5432/procuraflow"
PLACEHOLDER_SECRETS = [
    "insecure-dev-secret-change-me",
    "dev-secret-change-in-production",
    "change-this-to-a-random-secret-in-production",
]


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ENVIRONMENT", "JWT_SECRET_KEY", "DEBUG", "DATABASE_URL", "DEMO_MODE", "ALLOW_DEMO_IN_PRODUCTION"):
        monkeypatch.delenv(name, raising=False)


def make_settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **{"database_url": STRONG_DATABASE_URL, **overrides})


def test_environment_defaults_to_production() -> None:
    settings = make_settings(jwt_secret_key=STRONG_SECRET)

    assert settings.environment == "production"
    assert settings.debug is False


def test_production_rejects_missing_secret() -> None:
    with pytest.raises(ValidationError, match="jwt_secret_key"):
        make_settings(environment="production")


def test_production_rejects_short_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be at least 32 characters"):
        make_settings(environment="production", jwt_secret_key="too-short-secret")


@pytest.mark.parametrize("placeholder", PLACEHOLDER_SECRETS)
def test_production_rejects_placeholder_secrets(placeholder: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY is a known placeholder"):
        make_settings(environment="production", jwt_secret_key=placeholder)


@pytest.mark.parametrize("placeholder", PLACEHOLDER_SECRETS)
def test_staging_rejects_placeholder_secrets(placeholder: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY is a known placeholder"):
        make_settings(environment="staging", jwt_secret_key=placeholder)


def test_production_accepts_strong_secret() -> None:
    settings = make_settings(environment="production", jwt_secret_key=STRONG_SECRET)

    assert settings.jwt_secret_key == STRONG_SECRET


@pytest.mark.parametrize("environment", ["development", "test"])
def test_local_environments_accept_short_dev_secret(environment: str) -> None:
    settings = make_settings(environment=environment, jwt_secret_key="dev-secret")

    assert settings.environment == environment


def test_development_still_requires_a_secret() -> None:
    with pytest.raises(ValidationError, match="jwt_secret_key"):
        make_settings(environment="development")


def test_unknown_environment_rejected() -> None:
    with pytest.raises(ValidationError, match="environment"):
        make_settings(environment="prod", jwt_secret_key=STRONG_SECRET)


def test_environment_read_from_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("JWT_SECRET_KEY", STRONG_SECRET)

    assert make_settings().environment == "staging"


@pytest.mark.parametrize("secret", ["x" * 48, "change-me-" + "k3Vq9xLr0TzP7mWb2NcY8sHd5FgJ1aUe6", "ab" * 24])
def test_production_rejects_repetitive_or_example_secrets(secret: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        make_settings(environment="production", jwt_secret_key=secret)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://procuraflow:procuraflow@db.internal:5432/procuraflow",
        "postgresql+asyncpg://postgres:Postgres@db.internal:5432/procuraflow",
        "postgresql+asyncpg://procuraflow:short@db.internal:5432/procuraflow",
        "postgresql+asyncpg://procuraflow@db.internal:5432/procuraflow",
    ],
)
@pytest.mark.parametrize("environment", ["production", "staging"])
def test_non_local_environments_reject_a_weak_database_password(environment: str, database_url: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL has no password, a default one or a very short one"):
        make_settings(environment=environment, jwt_secret_key=STRONG_SECRET, database_url=database_url)


def test_the_database_password_is_never_repeated_in_the_error() -> None:
    url = "postgresql+asyncpg://procuraflow:procuraflow@db.internal:5432/procuraflow"
    with pytest.raises(ValidationError) as caught:
        make_settings(environment="production", jwt_secret_key=STRONG_SECRET, database_url=url)

    assert "procuraflow:procuraflow" not in str(caught.value)


def test_the_migration_url_is_held_to_the_same_rule() -> None:
    weak = "postgresql+asyncpg://procuraflow:procuraflow@db.internal:5432/procuraflow"
    with pytest.raises(ValidationError, match="MIGRATION_DATABASE_URL"):
        make_settings(environment="production", jwt_secret_key=STRONG_SECRET, migration_database_url=weak)


@pytest.mark.parametrize("environment", ["development", "test"])
def test_local_environments_keep_the_default_database_password(environment: str) -> None:
    default = "postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:5432/procuraflow"
    settings = make_settings(environment=environment, jwt_secret_key="dev-secret", database_url=default)

    assert settings.database_url == default


def test_demo_mode_is_off_by_default() -> None:
    assert make_settings(environment="development", jwt_secret_key="dev-secret").demo_mode is False


def test_demo_mode_is_refused_in_production_unless_explicitly_allowed() -> None:
    with pytest.raises(ValidationError, match="DEMO_MODE=true is refused when ENVIRONMENT=production"):
        make_settings(environment="production", jwt_secret_key=STRONG_SECRET, demo_mode=True)


def test_demo_mode_in_production_needs_the_explicit_allowance() -> None:
    settings = make_settings(
        environment="production", jwt_secret_key=STRONG_SECRET, demo_mode=True, allow_demo_in_production=True
    )

    assert settings.demo_mode is True


@pytest.mark.parametrize("environment", ["development", "test", "staging"])
def test_demo_mode_needs_no_allowance_outside_production(environment: str) -> None:
    settings = make_settings(environment=environment, jwt_secret_key=STRONG_SECRET, demo_mode=True)

    assert settings.demo_mode is True


def test_the_allowance_alone_does_not_switch_the_demo_on() -> None:
    settings = make_settings(environment="production", jwt_secret_key=STRONG_SECRET, allow_demo_in_production=True)

    assert settings.demo_mode is False


def test_demo_mode_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", STRONG_SECRET)
    monkeypatch.setenv("DATABASE_URL", STRONG_DATABASE_URL)
    monkeypatch.setenv("DEMO_MODE", "true")

    with pytest.raises(ValidationError, match="DEMO_MODE=true is refused"):
        Settings(_env_file=None)


def test_an_empty_migration_url_means_use_the_database_url() -> None:
    settings = make_settings(environment="production", jwt_secret_key=STRONG_SECRET, migration_database_url="")

    assert settings.migrations_database_url == STRONG_DATABASE_URL
