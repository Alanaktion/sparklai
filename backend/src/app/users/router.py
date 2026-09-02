from fastapi import APIRouter, File, UploadFile

from app.dependencies import CurrentCreator, DbDep, RequireCreator
from app.exceptions import ForbiddenError
from app.posts.repository import PostRepository
from app.posts.schemas import PostResponse
from app.posts.service import PostService
from app.users.repository import UserRepository
from app.users.schemas import (
    ImageUploadResponse,
    PostGenerateRequest,
    UserCreate,
    UserProfileResponse,
    UserResponse,
    UserUpdate,
)
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])

# Mounted without the `/users` prefix in api/router.py to keep the original `/api/import-character`
# path the frontend already calls.
import_router = APIRouter(tags=["users"])


def _service(db: DbDep) -> UserService:
    return UserService(UserRepository(db))


@router.get("", response_model=list[UserResponse])
async def list_users(creator: RequireCreator, db: DbDep):
    return await _service(db).list_for_creator(creator.id)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(data: UserCreate, creator: RequireCreator, db: DbDep):
    return await _service(db).create_ai_user(creator, data.prompt)


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(user_id: int, creator: CurrentCreator, db: DbDep):
    """Port of `users/[id]/+layout.server.ts` — the whole profile-page bundle in one call."""
    return await _service(db).get_profile(user_id, creator, PostRepository(db))


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, data: UserUpdate, creator: RequireCreator, db: DbDep):
    """The original had no ownership check at all (any request could edit any AI user) even
    though the edit *page* itself gated on `isOwner` client-side — enforcing it here too, since a
    server-side gate that only exists in the page and not the API it calls isn't really a gate."""
    service = _service(db)
    user = await service.get_by_id_or_raise(user_id)
    if user.creator_id != creator.id:
        raise ForbiddenError("You do not own this AI user")
    return await service.update_user(user_id, data.model_dump(exclude_unset=True))


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, creator: RequireCreator, db: DbDep):
    service = _service(db)
    user = await service.get_by_id_or_raise(user_id)
    if user.creator_id != creator.id:
        raise ForbiddenError("You do not own this AI user")
    await service.delete_user(user_id)


@router.post("/{user_id}/posts")
async def generate_post_for_user(user_id: int, data: PostGenerateRequest, db: DbDep):
    """Port of `users/[id]/posts/+server.ts`."""
    user = await _service(db).get_by_id_or_raise(user_id)
    result = await PostService(PostRepository(db)).generate_post_for_user(user, data.prompt)
    return {"post": PostResponse.model_validate(result["post"]), "image_job": result["image_job"]}


@router.post("/{user_id}/images", response_model=ImageUploadResponse, status_code=201)
async def upload_user_images(
    user_id: int, db: DbDep, files: list[UploadFile] = File(...)
) -> ImageUploadResponse:
    """Bulk gallery upload (port of `users/[id]/images/+server.ts`). The singular
    `/users/{id}/image` quick-avatar-upload-or-generate endpoint is intentionally not ported yet
    — see BACKEND_MIGRATION.md."""
    images = await _service(db).upload_images(user_id, files)
    return ImageUploadResponse(images=images)


@import_router.post("/import-character", response_model=UserResponse, status_code=201)
async def import_character(raw: dict, creator: RequireCreator, db: DbDep):
    return await _service(db).import_character_card(creator, raw)
