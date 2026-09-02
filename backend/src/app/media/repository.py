from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Media


class MediaRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, media_id: int) -> Media | None:
        return await self._session.get(Media, media_id)

    async def update(self, media: Media, fields: dict) -> Media:
        for key, value in fields.items():
            setattr(media, key, value)
        await self._session.commit()
        await self._session.refresh(media)
        return media

    async def delete(self, media: Media) -> None:
        await self._session.delete(media)
        await self._session.commit()
