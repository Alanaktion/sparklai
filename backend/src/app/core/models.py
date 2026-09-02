"""Shared SQLAlchemy base.

Adapted from the vendored `fastapi-core-models` skill: we skip its UUID/soft-delete mixins
because the existing schema (see `app.db.models`) uses integer autoincrement primary keys and
hard deletes, and we're preserving that schema exactly rather than migrating the data.
"""

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy models. Table names are set explicitly per model."""
