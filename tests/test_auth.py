"""Registration, login, and current-user behaviour."""

from httpx import AsyncClient


async def test_register_returns_public_user(client: AsyncClient, password: str) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "Ash@Example.com", "password": password},
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["email"] == "ash@example.com"
    assert body["is_active"] is True
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_rejects_duplicate_email(
    client: AsyncClient, registered_user: dict, password: str
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": registered_user["email"], "password": password},
    )
    assert response.status_code == 409


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "ash@example.com", "password": "short"},
    )
    assert response.status_code == 422


async def test_register_rejects_invalid_email(client: AsyncClient, password: str) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": password},
    )
    assert response.status_code == 422


async def test_login_returns_bearer_token(
    client: AsyncClient, registered_user: dict, password: str
) -> None:
    response = await client.post(
        "/api/auth/login",
        data={"username": registered_user["email"], "password": password},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_rejects_wrong_password(client: AsyncClient, registered_user: dict) -> None:
    response = await client.post(
        "/api/auth/login",
        data={"username": registered_user["email"], "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_login_rejects_unknown_email(client: AsyncClient, password: str) -> None:
    response = await client.post(
        "/api/auth/login",
        data={"username": "nobody@example.com", "password": password},
    )
    assert response.status_code == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/me")
    assert response.status_code == 401


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get("/api/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


async def test_me_returns_current_user(
    client: AsyncClient, registered_user: dict, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/me", headers=auth_headers)
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == registered_user["id"]
    assert body["email"] == registered_user["email"]


async def test_logout(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post("/api/auth/logout", headers=auth_headers)
    assert response.status_code == 204
