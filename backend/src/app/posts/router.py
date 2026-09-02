from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.dependencies import CurrentCreator, DbDep
from app.image_jobs.schemas import ImageGenerationJobResponse
from app.posts.repository import PostRepository
from app.posts.schemas import PostImageUploadResponse, PostResponse, PostsListResponse
from app.posts.service import DEFAULT_LIMIT, MAX_UPLOAD_BYTES, PostService

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
async def create_post(db: DbDep):
    """Generate a post for a random active user (any creator's) — matches the original endpoint,
    which doesn't scope authorship to the requesting creator either."""
    result = await _service(db).generate_random_post()
    return {
        "post": PostResponse.model_validate(result["post"]),
        "image_job": _image_job_response(result["image_job"]),
    }


@router.post("/{post_id}/image")
async def generate_or_upload_post_image(post_id: int, request: Request, db: DbDep):
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

    job = await service.generate_post_image(post_id)
    body = ImageGenerationJobResponse.model_validate(job)
    return JSONResponse(jsonable_encoder(body), status_code=202)
