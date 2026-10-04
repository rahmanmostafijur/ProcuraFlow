import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG_SECRET = "k3Vq9xLr0TzP7mWb2NcY8sHd5FgJ1aUe6RoXiQ4vEyZt"
PLACEHOLDER_SECRETS = [
    "insecure-dev-secret-change-me",
    "dev-secret-change-in-production",
    "change-this-to-a-random-secret-in-production",
]


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ENVIRONMENT", "JWT_SECRET_KEY", "DEBUG"):
        monkeypatch.delenv(name, raising=False)


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_environment_defaults_to_production():
    settings = make_settings(jwt_secret_key=STRONG_SECRET)

    assert settings.environment == "production"
    assert settings.debug is False


def test_production_rejects_missing_secret():
    with pytest.raises(ValidationError, match="jwt_secret_key"):
        make_settings(environment="production")


def test_production_rejects_short_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY must be at least 32 characters"):
        make_settings(environment="production", jwt_secret_key="too-short-secret")


@pytest.mark.parametrize("placeholder", PLACEHOLDER_SECRETS)
def test_production_rejects_placeholder_secrets(placeholder: str):
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY is a known placeholder"):
        make_settings(environment="production", jwt_secret_key=placeholder)


@pytest.mark.parametrize("placeholder", PLACEHOLDER_SECRETS)
def test_staging_rejects_placeholder_secrets(placeholder: str):
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY is a known placeholder"):
        make_settings(environment="staging", jwt_secret_key=placeholder)


def test_production_accepts_strong_secret():
    settings = make_settings(environment="production", jwt_secret_key=STRONG_SECRET)

    assert settings.jwt_secret_key == STRONG_SECRET


@pytest.mark.parametrize("environment", ["development", "test"])
def test_local_environments_accept_short_dev_secret(environment: str):
    settings = make_settings(environment=environment, jwt_secret_key="dev-secret")

    assert settings.environment == environment


def test_development_still_requires_a_secret():
    with pytest.raises(ValidationError, match="jwt_secret_key"):
        make_settings(environment="development")


def test_unknown_environment_rejected():
    with pytest.raises(ValidationError, match="environment"):
        make_settings(environment="prod", jwt_secret_key=STRONG_SECRET)


def test_environment_read_from_env_var(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("JWT_SECRET_KEY", STRONG_SECRET)

    assert make_settings().environment == "staging"
