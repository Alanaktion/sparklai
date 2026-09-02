from fastapi import APIRouter, Response

from app.dependencies import DbDep
from app.exceptions import NotFoundError
from app.media.repository import MediaRepository
from app.media.schemas import MediaUpdate

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{media_id}")
async def get_media(media_id: int, db: DbDep) -> Response:
    """Port of `media/[id]/+server.ts` GET."""
    media = await MediaRepository(db).get_by_id(media_id)
    if not media:
        raise NotFoundError("Media", media_id)
    return Response(content=bytes(media.data), media_type=media.type, headers={"Cache-Control": "public"})


@router.patch("/{media_id}")
async def update_media(media_id: int, data: MediaUpdate, db: DbDep) -> Response:
    repo = MediaRepository(db)
    media = await repo.get_by_id(media_id)
    if not media:
        raise NotFoundError("Media", media_id)
    fields = data.model_dump(exclude_unset=True)
    if fields:
        await repo.update(media, fields)
    return Response()


@router.delete("/{media_id}", status_code=204)
async def delete_media(media_id: int, db: DbDep) -> None:
    repo = MediaRepository(db)
    media = await repo.get_by_id(media_id)
    if not media:
        raise NotFoundError("Media", media_id)
    await repo.delete(media)
