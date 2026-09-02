from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.models import Base
from app.database import get_db
from app.db import models  # noqa: F401  (registers tables on Base.metadata)
from app.main import app

# In-memory sqlite, single shared connection for the whole test session (StaticPool) so every
# session sees the same schema/data. `app.main`'s lifespan (which migrates the *real*
# `DATABASE_URL`) never runs here: httpx's ASGITransport doesn't send ASGI lifespan events, so
# tests only ever touch this engine via the `get_db` override below.
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
test_session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # `app.services.sd.jobs`'s background tasks open their own session directly from
    # `app.database.async_session_factory` (a request-scoped `get_db` override alone can't reach
    # them — they outlive the request). Patching the module attribute here, rather than the name
    # `jobs.py` imported, works because `jobs.py` does `from app import database` and calls
    # `database.async_session_factory()` each time, so it always sees whatever this attribute
    # currently is instead of a value captured once at import time.
    import app.database as database_module

    monkeypatch.setattr(database_module, "async_session_factory", test_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
