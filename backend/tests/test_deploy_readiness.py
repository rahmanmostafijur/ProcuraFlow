import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.database_url import asyncpg_connect_args, normalize_database_url, uses_connection_pooler
from app.db.session import get_db
from app.main import app

STRONG_SECRET = "x" * 48


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgresql://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgres://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+asyncpg://u:p@host/db?ssl=require"),
        (
            "postgresql://u:p@host/db?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@host/db?ssl=require",
        ),
        (
            "postgresql://u:p@host/db?sslmode=require&application_name=pf",
            "postgresql+asyncpg://u:p@host/db?ssl=require&application_name=pf",
        ),
    ],
)
def test_normalize_database_url_targets_asyncpg(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected


def test_normalize_database_url_keeps_an_explicit_ssl_parameter() -> None:
    url = "postgresql+asyncpg://u:p@host/db?ssl=require"
    assert normalize_database_url(url) == url


@pytest.mark.parametrize(
    "url, expected",
    [
        ("postgresql+asyncpg://u:p@ep-cool-123-pooler.us-east-2.aws.neon.tech/db", True),
        ("postgresql+asyncpg://u:p@ep-cool-123.us-east-2.aws.neon.tech/db", False),
        ("postgresql+asyncpg://u:p@127.0.0.1:5432/db", False),
    ],
)
def test_uses_connection_pooler_detects_neon_pooled_hosts(url: str, expected: bool) -> None:
    assert uses_connection_pooler(url) is expected


def test_asyncpg_connect_args_disable_the_statement_cache_only_behind_a_pooler() -> None:
    pooled = "postgresql+asyncpg://u:p@ep-cool-123-pooler.us-east-2.aws.neon.tech/db"
    direct = "postgresql+asyncpg://u:p@ep-cool-123.us-east-2.aws.neon.tech/db"
    assert asyncpg_connect_args(pooled) == {"statement_cache_size": 0}
    assert asyncpg_connect_args(direct) == {}


def test_settings_normalise_a_provider_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db?sslmode=require")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+asyncpg://u:p@host/db?ssl=require"


def test_cors_defaults_to_local_origins_only_in_local_environments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert "http://localhost:5173" in Settings(_env_file=None).cors_origin_list


def test_cors_is_closed_by_default_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", STRONG_SECRET)
    assert Settings(_env_file=None).cors_origin_list == []


def test_explicit_cors_origins_are_honoured_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", STRONG_SECRET)
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com, https://admin.example.com")
    assert Settings(_env_file=None).cors_origin_list == ["https://app.example.com", "https://admin.example.com"]


async def test_health_reports_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_root_health_stays_available_for_platform_probes(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


async def test_ready_reports_ready_when_the_database_answers(client: AsyncClient) -> None:
    response = await client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_ready_reports_503_when_the_database_is_unreachable(client: AsyncClient) -> None:
    class BrokenSession:
        async def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, ConnectionRefusedError("db down"))

    async def broken_db():
        yield BrokenSession()

    previous = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = broken_db
    try:
        response = await client.get("/api/ready")
    finally:
        app.dependency_overrides[get_db] = previous

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
