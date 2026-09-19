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


def build_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine with this app's connection settings."""
    engine = create_async_engine(url, echo=echo, pool_pre_ping=True, future=True)
    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys (and their cascades) unless enabled.
        event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def get_engine() -> AsyncEngine:
    """Return the lazily-created, process-wide async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = build_engine(settings.database_url, echo=settings.debug)
    return _engine


def reset_engine() -> None:
    """Drop the cached engine so the next call rebuilds it (used by tests)."""
    global _engine
    _engine = None


def create_session(engine: AsyncEngine) -> AsyncSession:
    """Build an `AsyncSession` with the settings this app relies on.

    `expire_on_commit=False` matters: with the default, every object in the
    session is expired on commit, so merely reading an attribute afterwards (for
    example `current_user.id`) would issue lazy IO and raise `MissingGreenlet` in
    an async context. Tests use this same constructor so behaviour matches.
    """
    return AsyncSession(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an `AsyncSession` for the duration of a request."""
    async with create_session(get_engine()) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def create_db_and_tables(engine: AsyncEngine | None = None) -> None:
    """Create all tables from SQLModel metadata (tests/development only)."""
    # Importing the models package registers every table on SQLModel.metadata.
    import sparklchat.models  # noqa: F401

    target = engine or get_engine()
    async with target.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
