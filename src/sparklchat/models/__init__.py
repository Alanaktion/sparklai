"""SQLModel table models and request/response schemas.

Importing this package registers every table on `SQLModel.metadata`, which
Alembic autogenerate and `create_db_and_tables` both rely on.
"""

from sparklchat.models.base import utcnow
from sparklchat.models.card import (
    CardFields,
    CharacterBook,
    CharacterBookEntry,
    CharacterCardData,
    TavernCardV1,
    TavernCardV2,
)
from sparklchat.models.character import (
    Character,
    CharacterDetail,
    CharacterSummary,
    CharacterUpdate,
)
from sparklchat.models.chat import (
    ChatSession,
    Message,
    MessagePair,
    MessagePublic,
    MessageUpdate,
    SessionCreate,
    SessionDetail,
    SessionSummary,
    SessionUpdate,
    SwipeRequest,
)
from sparklchat.models.provider import (
    Provider,
    ProviderCreate,
    ProviderPublic,
    ProviderTestResult,
    ProviderUpdate,
)
from sparklchat.models.user import Token, User, UserCreate, UserPublic
from sparklchat.models.user_settings import (
    UserSettings,
    UserSettingsPublic,
    UserSettingsUpdate,
)

__all__ = [
    "CardFields",
    "Character",
    "CharacterBook",
    "CharacterBookEntry",
    "CharacterCardData",
    "CharacterDetail",
    "CharacterSummary",
    "CharacterUpdate",
    "ChatSession",
    "Message",
    "MessagePair",
    "MessagePublic",
    "MessageUpdate",
    "Provider",
    "ProviderCreate",
    "ProviderPublic",
    "ProviderTestResult",
    "ProviderUpdate",
    "SessionCreate",
    "SessionDetail",
    "SessionSummary",
    "SessionUpdate",
    "SwipeRequest",
    "TavernCardV1",
    "TavernCardV2",
    "Token",
    "User",
    "UserCreate",
    "UserPublic",
    "UserSettings",
    "UserSettingsPublic",
    "UserSettingsUpdate",
    "utcnow",
]
