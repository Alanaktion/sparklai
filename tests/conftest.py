"""Shared pytest fixtures.

Each test gets its own throwaway SQLite file and an app whose DB dependency is
overridden to use it, so tests never touch the development database.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.config import Settings
from sparklchat.db import create_db_and_tables, get_session
from sparklchat.main import create_app

PASSWORD = "correct horse battery staple"


def _override_session(app: FastAPI, engine: AsyncEngine) -> None:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session


def _asgi_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def password() -> str:
    return PASSWORD


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    # Point at a missing build directory so API tests are unaffected by a real
    # `frontend/build` that happens to exist in the working tree.
    return create_app(Settings(frontend_dist_dir=tmp_path / "no-frontend-build"))


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await create_db_and_tables(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def client(app: FastAPI, engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    _override_session(app, engine)
    async with _asgi_client(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def spa_dist(tmp_path: Path) -> Path:
    """A stand-in for the output of `npm run build` in `frontend/`."""
    dist = tmp_path / "frontend-build"
    (dist / "_app" / "immutable").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Sparkl Chat SPA</title>")
    (dist / "_app" / "immutable" / "app.js").write_text("console.log('sparklchat');")
    (dist / "robots.txt").write_text("User-agent: *\n")
    return dist


@pytest.fixture
async def spa_client(engine: AsyncEngine, spa_dist: Path) -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(frontend_dist_dir=spa_dist))
    _override_session(app, engine)
    async with _asgi_client(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def registered_user(client: AsyncClient, password: str) -> dict:
    response = await client.post(
        "/api/auth/register",
        json={"email": "ash@example.com", "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def auth_headers(client: AsyncClient, registered_user: dict, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/auth/login",
        data={"username": registered_user["email"], "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
