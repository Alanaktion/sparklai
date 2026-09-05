"""Applies Alembic migrations on startup (see the vendored `fastapi-alembic-setup` skill for the
reasoning).

A pre-existing database created before Alembic tracking was introduced already has every table
the baseline migration (`0001_baseline`) would create, but no `alembic_version` table. Running
`upgrade head` against it would try to `CREATE TABLE` things that already exist and fail. So: if
that exact shape is detected (app tables present, no `alembic_version` table), we stamp it to head
instead of upgrading — a one-time cutover that doesn't touch a single row. Anything else (a fresh/
empty database, or one already stamped/migrated before) just runs `upgrade head` normally, which
is also how every future schema change gets applied.
"""

import logging
import sqlite3
from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.config import settings

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[3]  # backend/


def _alembic_config() -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _sqlite_path() -> str | None:
    url = make_url(settings.database_url)
    if not url.database or url.database == ":memory:":
        return None
    # Alembic's env.py resolves relative to backend/ (its own cwd assumption); match that here.
    path = Path(url.database)
    return str(path if path.is_absolute() else _BACKEND_DIR / path)


def _existing_tables(path: str) -> set[str]:
    if not Path(path).exists():
        return set()
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def apply_migrations() -> None:
    """Synchronous by design — Alembic's own migration runner manages its async engine
    internally (see `alembic/env.py`), so this must be called via `asyncio.to_thread` from the
    FastAPI lifespan rather than awaited directly."""
    cfg = _alembic_config()
    sqlite_path = _sqlite_path()

    if sqlite_path:
        tables = _existing_tables(sqlite_path)
        if "creators" in tables and "alembic_version" not in tables:
            logger.info("Pre-Alembic database detected at %s — stamping baseline", sqlite_path)
            command.stamp(cfg, "head")
            return

    logger.info("Applying migrations (upgrade head)")
    command.upgrade(cfg, "head")
