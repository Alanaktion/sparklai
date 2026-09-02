from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Image


class ImageRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, image_id: int) -> Image | None:
        return await self._session.get(Image, image_id)

    async def update(self, image: Image, fields: dict) -> Image:
        for key, value in fields.items():
            setattr(image, key, value)
        await self._session.commit()
        await self._session.refresh(image)
        return image

    async def delete(self, image: Image) -> None:
        await self._session.delete(image)
        await self._session.commit()
