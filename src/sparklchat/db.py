"""Async database engine, session dependency, and schema helpers.

The database schema is owned by Alembic (`alembic upgrade head`). The
`create_db_and_tables` helper exists for tests and quick local experiments.
"""

from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.config import get_settings

_engine: AsyncEngine | None = None


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """SQLite ignores foreign keys unless they are enabled per connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine() -> AsyncEngine:
    """Return the lazily-created, process-wide async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            future=True,
        )
        if _engine.dialect.name == "sqlite":
            event.listen(_engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return _engine


def reset_engine() -> None:
    """Drop the cached engine so the next call rebuilds it (used by tests)."""
    global _engine
    _engine = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an `AsyncSession` for the duration of a request."""
    async with AsyncSession(get_engine()) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def create_db_and_tables(engine: AsyncEngine | None = None) -> None:
    """Create all tables from SQLModel metadata (tests/development only)."""
    # Importing the models package registers every table on SQLModel.metadata.
    import sparklchat.models  # noqa: F401

    target = engine or get_engine()
    async with target.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
