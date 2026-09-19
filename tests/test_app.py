"""Smoke tests for the scaffolded app shell."""

from httpx import AsyncClient

from sparklchat import __version__


async def test_version_is_exposed() -> None:
    assert __version__ == "0.1.0"


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_index_renders(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "Sparkl Chat" in response.text
