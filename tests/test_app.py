"""Smoke tests for the app shell and API routing."""

from httpx import AsyncClient

from sparklchat import __version__


async def test_version_is_exposed() -> None:
    assert __version__ == "0.1.0"


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/auth/login" in response.json()["paths"]


async def test_api_only_app_serves_no_spa(client: AsyncClient) -> None:
    # With no frontend build present, non-API paths simply 404.
    assert (await client.get("/")).status_code == 404
