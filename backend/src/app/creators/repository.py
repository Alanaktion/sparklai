from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Creator


class CreatorRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: int) -> Creator | None:
        return await self._session.get(Creator, id)

    async def list_all(self) -> Sequence[Creator]:
        result = await self._session.execute(select(Creator))
        return result.scalars().all()

    async def create(self, *, name: str, pronouns: str, password_hash: str) -> Creator:
        creator = Creator(name=name, pronouns=pronouns, password_hash=password_hash)
        self._session.add(creator)
        await self._session.commit()
        await self._session.refresh(creator)
        return creator

    async def update(self, creator: Creator, fields: dict) -> Creator:
        for key, value in fields.items():
            setattr(creator, key, value)
        await self._session.commit()
        await self._session.refresh(creator)
        return creator
