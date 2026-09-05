from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, Relationship, User


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_user(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def list_for_creator(self, creator_id: int) -> Sequence[User]:
        stmt = select(User).where(User.creator_id == creator_id, User.is_active.is_(True))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_latest_for_user(self, user_id: int) -> Chat | None:
        stmt = (
            select(Chat).where(Chat.user_id == user_id).order_by(Chat.created_at.desc()).limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_user(self, user_id: int) -> Sequence[Chat]:
        stmt = select(Chat).where(Chat.user_id == user_id).order_by(Chat.id.asc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_relationships_with_related_user(self, user_id: int) -> Sequence[Relationship]:
        result = await self._session.execute(
            select(Relationship).where(Relationship.user_id == user_id)
        )
        return result.scalars().all()

    async def create(self, *, user_id: int, role: str, body: str) -> Chat:
        chat = Chat(user_id=user_id, role=role, body=body)
        self._session.add(chat)
        await self._session.commit()
        await self._session.refresh(chat)
        return chat

    async def get_by_id_and_user(self, chat_id: int, user_id: int) -> Chat | None:
        stmt = select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def update_body_en(self, chat: Chat, body_en: str) -> None:
        chat.body_en = body_en
        await self._session.commit()

    async def update_additional_prompt(self, user: User, additional_prompt: str) -> None:
        user.additional_prompt = additional_prompt
        await self._session.commit()

    async def delete(self, chat_id: int) -> None:
        """Deletes by id alone — does not verify the message belongs to any particular user."""
        chat = await self._session.get(Chat, chat_id)
        if chat:
            await self._session.delete(chat)
            await self._session.commit()
