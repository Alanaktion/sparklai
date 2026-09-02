from fastapi import APIRouter, Query

from app.dependencies import CurrentCreator, DbDep
from app.posts.repository import PostRepository
from app.posts.schemas import PostResponse, PostsListResponse
from app.posts.service import DEFAULT_LIMIT, PostService

router = APIRouter(prefix="/posts", tags=["posts"])


def _service(db: DbDep) -> PostService:
    return PostService(PostRepository(db))


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
    return {"post": PostResponse.model_validate(result["post"]), "image_job": result["image_job"]}
