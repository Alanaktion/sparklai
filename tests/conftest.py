"""Shared pytest fixtures.

Each test gets its own throwaway SQLite file and an app whose DB dependency is
overridden to use it, so tests never touch the development database.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.db import create_db_and_tables, get_session
from sparklchat.main import create_app

PASSWORD = "correct horse battery staple"


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def password() -> str:
    return PASSWORD


@pytest.fixture
async def engine(tmp_path) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await create_db_and_tables(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def client(app: FastAPI, engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
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
