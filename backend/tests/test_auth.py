from httpx import AsyncClient


async def test_login_succeeds_with_correct_credentials(client: AsyncClient, make_user):
    await make_user("user@example.com", "viewer", password="CorrectPass1!")

    response = await client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "CorrectPass1!"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_rejects_wrong_password(client: AsyncClient, make_user):
    await make_user("user@example.com", "viewer", password="CorrectPass1!")

    response = await client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "WrongPassword!"}
    )

    assert response.status_code == 401


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


async def test_refresh_token_issues_new_access_token(client: AsyncClient, make_user):
    await make_user("user@example.com", "viewer", password="CorrectPass1!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "CorrectPass1!"}
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_refresh_rejects_access_token_used_as_refresh_token(client: AsyncClient, make_user):
    await make_user("user@example.com", "viewer", password="CorrectPass1!")
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "CorrectPass1!"}
    )
    access_token = login_response.json()["access_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})

    assert response.status_code == 401
