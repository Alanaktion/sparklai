"""SQLModel table models.

Importing this package registers every table on `SQLModel.metadata`, which
Alembic autogenerate and `create_db_and_tables` both rely on.
"""

from sparklchat.models.base import utcnow
from sparklchat.models.user import Token, User, UserCreate, UserPublic
from sparklchat.models.user_settings import (
    UserSettings,
    UserSettingsPublic,
    UserSettingsUpdate,
)

__all__ = [
    "Token",
    "User",
    "UserCreate",
    "UserPublic",
    "UserSettings",
    "UserSettingsPublic",
    "UserSettingsUpdate",
    "utcnow",
]
