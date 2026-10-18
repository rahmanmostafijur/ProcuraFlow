import pytest
from httpx import AsyncClient

from app.core.auth_cookie import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH, refresh_cookie_options
from app.core.config import Settings

CREDENTIALS = {"email": "user@example.com", "password": "CorrectPass1!"}


async def _login(client: AsyncClient, make_user):
    await make_user(CREDENTIALS["email"], "viewer", password=CREDENTIALS["password"])
    return await client.post("/api/v1/auth/login", json=CREDENTIALS)


async def test_login_succeeds_with_correct_credentials(client: AsyncClient, make_user):
    response = await _login(client, make_user)

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_sets_the_refresh_token_as_an_httponly_cookie_not_in_the_body(
    client: AsyncClient, make_user
):
    response = await _login(client, make_user)

    assert "refresh_token" not in response.json()
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{REFRESH_COOKIE_NAME}=")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert f"Path={REFRESH_COOKIE_PATH}" in set_cookie


async def test_login_rejects_wrong_password(client: AsyncClient, make_user):
    await make_user(CREDENTIALS["email"], "viewer", password=CREDENTIALS["password"])

    response = await client.post(
        "/api/v1/auth/login", json={"email": CREDENTIALS["email"], "password": "WrongPassword!"}
    )

    assert response.status_code == 401
    assert "set-cookie" not in response.headers


async def test_login_rejects_unknown_email(client: AsyncClient, roles):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert response.status_code == 401


async def test_me_requires_authentication(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, auth_headers):
    headers = await auth_headers("admin")

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


async def test_refresh_uses_the_cookie_to_issue_a_new_access_token(client: AsyncClient, make_user):
    await _login(client, make_user)

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_refresh_without_a_cookie_is_rejected(client: AsyncClient):
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


async def test_refresh_ignores_a_token_sent_in_the_body(client: AsyncClient, make_user):
    login_response = await _login(client, make_user)
    client.cookies.clear()
    stolen = login_response.headers["set-cookie"].split(";")[0].split("=", 1)[1]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": stolen})

    assert response.status_code == 401


async def test_refresh_rejects_access_token_used_as_refresh_cookie(client: AsyncClient, make_user):
    login_response = await _login(client, make_user)
    client.cookies.clear()
    access_token = login_response.json()["access_token"]
    client.cookies.set(REFRESH_COOKIE_NAME, access_token, path=REFRESH_COOKIE_PATH)

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


async def test_refresh_rejects_a_garbage_cookie(client: AsyncClient):
    client.cookies.set(REFRESH_COOKIE_NAME, "not-a-jwt", path=REFRESH_COOKIE_PATH)

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


async def test_logout_clears_the_cookie_so_refresh_fails_afterwards(client: AsyncClient, make_user):
    await _login(client, make_user)

    logout_response = await client.post("/api/v1/auth/logout")
    refresh_response = await client.post("/api/v1/auth/refresh")

    assert logout_response.status_code == 204
    assert "Max-Age=0" in logout_response.headers["set-cookie"]
    assert refresh_response.status_code == 401


async def test_logout_is_idempotent_without_a_session(client: AsyncClient):
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204


def test_refresh_cookie_is_secure_outside_local_environments(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 48)
    monkeypatch.setenv("ENVIRONMENT", "production")
    production = Settings(_env_file=None)
    monkeypatch.setenv("ENVIRONMENT", "development")
    development = Settings(_env_file=None)

    assert refresh_cookie_options(production)["secure"] is True
    assert refresh_cookie_options(development)["secure"] is False


def test_refresh_cookie_lifetime_follows_the_configured_token_lifetime(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("REFRESH_TOKEN_EXPIRE_DAYS", "3")

    assert refresh_cookie_options(Settings(_env_file=None))["max_age"] == 3 * 24 * 60 * 60
