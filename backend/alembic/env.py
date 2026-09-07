import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.core.models import Base

# Import every entity's models so they're registered on Base.metadata for autogenerate.
from app.db import models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    # disable_existing_loggers defaults to True, which — since alembic.ini's [loggers] only lists
    # root/sqlalchemy/alembic — silently disables every other logger already registered in this
    # process (app.main, app.db.migrate, uvicorn, uvicorn.error, uvicorn.access, ...) the moment
    # migrations run. Migrations run from FastAPI's startup lifespan on every boot (see
    # app/main.py), so in practice this was permanently muting uvicorn's access logs *and* its
    # unhandled-exception tracebacks (logged via the uvicorn.error logger) for the rest of the
    # process's life — the exact reason a 500 would show nothing at all in `docker logs`.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # render_as_batch: SQLite can't ALTER most column properties in place, so Alembic emits
    # "copy the table into a new one" batch operations instead — required for any future
    # migration that isn't a plain CREATE/DROP TABLE.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
