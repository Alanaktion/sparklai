"""Lookups for characters a request is allowed to touch.

Kept in one place so the character and chat routers agree on what counts as
accessible: owners get their own characters, and everyone gets public ones.
"""

from fastapi import HTTPException, status
from sqlmodel import select

from sparklchat.db import SessionDep
from sparklchat.models.character import Character


async def owned_character(db: SessionDep, character_id: int, user_id: int) -> Character:
    """The user's own character, for editing and deleting."""
    statement = select(Character).where(Character.id == character_id, Character.user_id == user_id)
    character = (await db.exec(statement)).first()
    if character is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    return character


async def readable_character(db: SessionDep, character_id: int, user_id: int) -> Character:
    """A character the user may read, chat with, or export.

    That means their own, or someone else's that has been published.
    """
    statement = select(Character).where(
        Character.id == character_id,
        (Character.user_id == user_id) | Character.is_public.is_(True),
    )
    character = (await db.exec(statement)).first()
    if character is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    return character
