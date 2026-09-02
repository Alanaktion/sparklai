from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

from fastapi import APIRouter, Response

from app.dependencies import DbDep
from app.exceptions import NotFoundError
from app.images.repository import ImageRepository
from app.images.schemas import ImageUpdate

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/{image_id}")
async def get_image(image_id: int, db: DbDep) -> Response:
    """Port of `images/[id]/+server.ts` GET — serves the raw blob straight from SQLite."""
    image = await ImageRepository(db).get_by_id(image_id)
    if not image:
        raise NotFoundError("Image", image_id)
    expires = format_datetime(datetime.now(UTC) + timedelta(days=7), usegmt=True)
    return Response(
        content=bytes(image.data),
        media_type=image.type,
        headers={"Cache-Control": "public", "Expires": expires},
    )


@router.patch("/{image_id}")
async def update_image(image_id: int, data: ImageUpdate, db: DbDep) -> Response:
    repo = ImageRepository(db)
    image = await repo.get_by_id(image_id)
    if not image:
        raise NotFoundError("Image", image_id)
    fields = data.model_dump(exclude_unset=True)
    if fields:
        await repo.update(image, fields)
    return Response()


@router.delete("/{image_id}", status_code=204)
async def delete_image(image_id: int, db: DbDep) -> None:
    repo = ImageRepository(db)
    image = await repo.get_by_id(image_id)
    if not image:
        raise NotFoundError("Image", image_id)
    await repo.delete(image)
