"""Verifies the SPA fallback (app/spa.py): unmatched client-side routes should still get the app
shell, real files should be served as themselves, and /api/* must never be swallowed by it."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def spa_client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "index.html").write_text("<html>spa shell</html>")
    (tmp_path / "favicon.ico").write_bytes(b"\x00")

    monkeypatch.setattr("app.config.settings.static_dir", str(tmp_path))
    return create_app()


@pytest.fixture
async def client(spa_client) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=spa_client), base_url="http://test") as ac:
        yield ac


async def test_real_static_file_is_served_as_itself(client: AsyncClient):
    response = await client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.content == b"\x00"


async def test_unmatched_client_route_falls_back_to_index(client: AsyncClient):
    response = await client.get("/users/123")
    assert response.status_code == 200
    assert "spa shell" in response.text


async def test_deeply_nested_unmatched_route_falls_back_to_index(client: AsyncClient):
    response = await client.get("/users/123/chat/456")
    assert response.status_code == 200
    assert "spa shell" in response.text


async def test_unmatched_api_route_is_a_real_404_not_the_spa_shell(client: AsyncClient):
    response = await client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert "spa shell" not in response.text
