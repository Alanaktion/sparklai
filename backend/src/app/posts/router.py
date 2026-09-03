from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.comments.schemas import TranslateResponse
from app.dependencies import ChatModelPref, CurrentCreator, DbDep
from app.image_jobs.schemas import ImageGenerationJobResponse
from app.posts.repository import PostRepository
from app.posts.schemas import (
    PostBundleResponse,
    PostImageUploadResponse,
    PostMediaUploadResponse,
    PostResponse,
    PostsListResponse,
    PostUpdate,
)
from app.posts.service import DEFAULT_LIMIT, MAX_MEDIA_UPLOAD_BYTES, MAX_UPLOAD_BYTES, PostService

router = APIRouter(prefix="/posts", tags=["posts"])


def _service(db: DbDep) -> PostService:
    return PostService(PostRepository(db))


def _image_job_response(image_job) -> ImageGenerationJobResponse | None:
    return ImageGenerationJobResponse.model_validate(image_job) if image_job else None


@router.get("", response_model=PostsListResponse)
async def list_posts(
    creator: CurrentCreator,
    db: DbDep,
    limit: int = Query(DEFAULT_LIMIT, ge=1),
    cursor: int | None = Query(None, gt=0),
    q: str = Query(""),
):
    posts, has_more = await _service(db).list_for_creator(
        creator.id if creator else None, limit=limit, cursor=cursor, query=q.strip()
    )
    return PostsListResponse(posts=posts, hasMore=has_more)


@router.post("", status_code=201)
async def create_post(db: DbDep, chat_model: ChatModelPref):
    """Generate a post for a random active user (any creator's) — matches the original endpoint,
    which doesn't scope authorship to the requesting creator either."""
    result = await _service(db).generate_random_post(model=chat_model)
    return {
        "post": PostResponse.model_validate(result["post"]),
        "image_job": _image_job_response(result["image_job"]),
    }


@router.post("/{post_id}/image")
async def generate_or_upload_post_image(
    post_id: int, request: Request, db: DbDep, chat_model: ChatModelPref
):
    """Port of the dual-purpose `posts/[id]/image/+server.ts`: a multipart upload with a `file`
    field sets the post's image directly; anything else queues an AI-generated one. See
    `PostService.upload_post_image()` / `.generate_post_image()`."""
    content_type = request.headers.get("content-type", "")
    service = _service(db)

    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        # See the equivalent check in `users/router.py` for why this is Starlette's `UploadFile`
        # and not `fastapi.UploadFile`.
        if isinstance(file, StarletteUploadFile):
            contents = await file.read()
            if len(contents) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File too large (max 10MB)")
            image = await service.upload_post_image(post_id, contents)
            body = PostImageUploadResponse(image=image)
            return JSONResponse(jsonable_encoder(body), status_code=201)

    job = await service.generate_post_image(post_id, model=chat_model)
    body = ImageGenerationJobResponse.model_validate(job)
    return JSONResponse(jsonable_encoder(body), status_code=202)


@router.get("/{post_id}", response_model=PostBundleResponse)
async def get_post(post_id: int, creator: CurrentCreator, db: DbDep):
    """Port of `posts/[id]/+page.server.ts`'s load — the whole individual post page in one call."""
    return await _service(db).get_bundle(post_id, creator)


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(post_id: int, data: PostUpdate, db: DbDep):
    """Port of `posts/[id]/+server.ts`'s PATCH."""
    fields = data.model_dump(exclude_unset=True)
    return await _service(db).update_post(post_id, fields)


@router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: int, db: DbDep):
    """Port of `posts/[id]/+server.ts`'s DELETE."""
    await _service(db).delete_post(post_id)


@router.post("/{post_id}/translate", response_model=TranslateResponse)
async def translate_post(post_id: int, db: DbDep, chat_model: ChatModelPref):
    """Port of `posts/[id]/translate/+server.ts`."""
    body_en = await _service(db).translate_post(post_id, chat_model)
    return TranslateResponse(body_en=body_en)


@router.post("/{post_id}/media")
async def upload_post_media(post_id: int, request: Request, db: DbDep):
    """Port of `posts/[id]/media/+server.ts` — audio/video upload, attached to the post."""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=400, detail="Expected multipart/form-data")

    form = await request.form()
    file = form.get("file")
    if not isinstance(file, StarletteUploadFile):
        raise HTTPException(status_code=400, detail="No file uploaded")

    contents = await file.read()
    if len(contents) > MAX_MEDIA_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 100MB)")

    media = await _service(db).upload_post_media(post_id, file.content_type or "", contents)
    body = PostMediaUploadResponse(media=media)
    return JSONResponse(jsonable_encoder(body), status_code=201)
