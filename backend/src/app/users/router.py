from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.dependencies import ChatModelPref, CurrentCreator, DbDep, RequireCreator
from app.exceptions import ForbiddenError
from app.image_jobs.schemas import ImageGenerationJobResponse
from app.posts.repository import PostRepository
from app.posts.schemas import PostResponse
from app.posts.service import PostService
from app.users.repository import UserRepository
from app.users.schemas import (
    AvatarUploadResponse,
    DreamResponse,
    ImageUploadResponse,
    PostGenerateRequest,
    UserCreate,
    UserProfileResponse,
    UserResponse,
    UserUpdate,
)
from app.users.service import MAX_UPLOAD_BYTES, UserService

router = APIRouter(prefix="/users", tags=["users"])

# Mounted without the `/users` prefix in api/router.py so this lands at `/api/import-character`,
# the path the frontend calls.
import_router = APIRouter(tags=["users"])


def _service(db: DbDep) -> UserService:
    return UserService(UserRepository(db))


@router.get("", response_model=list[UserResponse])
async def list_users(creator: RequireCreator, db: DbDep):
    return await _service(db).list_for_creator(creator.id)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate, creator: RequireCreator, db: DbDep, chat_model: ChatModelPref
):
    return await _service(db).create_ai_user(creator, data.prompt, model=chat_model)


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(user_id: int, creator: CurrentCreator, db: DbDep):
    """The whole profile-page bundle in one call."""
    return await _service(db).get_profile(user_id, creator, PostRepository(db))


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, data: UserUpdate, creator: RequireCreator, db: DbDep):
    """Enforces that the requesting creator actually owns this AI user — a server-side check
    independent of any client-side page gating."""
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
async def generate_post_for_user(
    user_id: int, data: PostGenerateRequest, db: DbDep, chat_model: ChatModelPref
):
    user = await _service(db).get_by_id_or_raise(user_id)
    result = await PostService(PostRepository(db)).generate_post_for_user(
        user, data.prompt, chat_model
    )
    image_job = result["image_job"]
    return {
        "post": PostResponse.model_validate(result["post"]),
        "image_job": ImageGenerationJobResponse.model_validate(image_job) if image_job else None,
    }


@router.post("/{user_id}/image")
async def generate_or_upload_avatar(
    user_id: int, request: Request, db: DbDep, chat_model: ChatModelPref
):
    """Dual-purpose: a multipart upload with a `file` field sets the avatar directly; anything
    else (including no body at all) generates one or more AI profile pictures via a queued
    image-generation job. See `UserService.upload_avatar()` / `.generate_avatar()`."""
    content_type = request.headers.get("content-type", "")
    service = _service(db)

    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        # `Request.form()` (unlike a `File(...)`-typed endpoint parameter) parses multipart
        # uploads into Starlette's own `UploadFile`, not `fastapi.UploadFile` — checking against
        # the former still matches the latter, since fastapi's is a subclass of it.
        if isinstance(file, StarletteUploadFile):
            contents = await file.read()
            if len(contents) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File too large (max 10MB)")
            image = await service.upload_avatar(user_id, contents)
            body = AvatarUploadResponse(image=image)
            return JSONResponse(jsonable_encoder(body), status_code=201)

    prompt = ""
    aspect = "square"
    count = 1
    if "form" in content_type:
        form = await request.form()
        prompt = str(form.get("prompt") or "")
        aspect = str(form.get("aspect") or "square")
        try:
            count = min(5, max(1, int(str(form.get("count") or "1"))))
        except ValueError:
            count = 1

    jobs = await service.generate_avatar(
        user_id, prompt=prompt, aspect=aspect, count=count, model=chat_model
    )
    body = [ImageGenerationJobResponse.model_validate(job) for job in jobs]
    return JSONResponse(jsonable_encoder(body), status_code=202)


@router.post("/{user_id}/images", response_model=ImageUploadResponse, status_code=201)
async def upload_user_images(
    user_id: int, db: DbDep, files: list[UploadFile] = File(...)
) -> ImageUploadResponse:
    """Bulk gallery upload — does not touch the user's avatar (see the singular
    `/users/{id}/image` endpoint above for that)."""
    images = await _service(db).upload_images(user_id, files)
    return ImageUploadResponse(images=images)


@router.post("/{user_id}/dream", response_model=DreamResponse)
async def dream(user_id: int, creator: RequireCreator, db: DbDep, chat_model: ChatModelPref):
    """Reflects on the AI user's recent activity and rewrites their `memory` field.
    Ownership-gated like `PATCH`/`DELETE` above."""
    service = _service(db)
    user = await service.get_by_id_or_raise(user_id)
    if user.creator_id != creator.id:
        raise ForbiddenError("You do not own this AI user")
    memory = await service.dream(user_id, model=chat_model)
    return DreamResponse(memory=memory)


@import_router.post("/import-character", response_model=UserResponse, status_code=201)
async def import_character(raw: dict, creator: RequireCreator, db: DbDep):
    return await _service(db).import_character_card(creator, raw)
