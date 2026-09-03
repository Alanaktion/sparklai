from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.db.models import Creator
from app.exceptions import UnauthorizedError
from app.security.session import read_session_token
from app.services.model_preferences import CHAT_MODEL_COOKIE, normalize_cookie_value

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_creator(
    db: DbDep,
    session_cookie: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> Creator | None:
    """Resolve the active creator from the signed session cookie, if any.

    This replaces `hooks.server.ts`, which did the same DB lookup on every request via
    `event.locals.creator` — the difference here is it's an explicit per-request dependency
    instead of implicit request-scoped state, and it doesn't touch anything process-wide.
    """
    if not session_cookie:
        return None
    creator_id = read_session_token(session_cookie)
    if creator_id is None:
        return None
    return await db.get(Creator, creator_id)


CurrentCreator = Annotated[Creator | None, Depends(get_current_creator)]


async def require_creator(creator: CurrentCreator) -> Creator:
    if creator is None:
        raise UnauthorizedError()
    return creator


RequireCreator = Annotated[Creator, Depends(require_creator)]


async def get_chat_model_preference(
    chat_model_cookie: Annotated[str | None, Cookie(alias=CHAT_MODEL_COOKIE)] = None,
) -> str | None:
    """The per-request replacement for `hooks.server.ts` calling `initChatModel()` on every
    request (see `app/services/model_preferences.py`'s docstring) — resolved here once and passed
    down explicitly as `model=` into every `chat.schema_completion()`/`chat.completion()` call,
    instead of every request racing to mutate a shared global."""
    return normalize_cookie_value(chat_model_cookie)


ChatModelPref = Annotated[str | None, Depends(get_chat_model_preference)]
