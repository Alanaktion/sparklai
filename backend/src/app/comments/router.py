from fastapi import APIRouter

from app.comments.repository import CommentRepository
from app.comments.schemas import CommentCreate, CommentResponse, RespondRequest, TranslateResponse
from app.comments.service import CommentService
from app.dependencies import ChatModelPref, DbDep

# Mounted under the `/posts` prefix (not its own `/comments` one) for the nested paths:
# `posts/[id]/comments/**` plus the sibling `posts/comments` random-generation route.
router = APIRouter(prefix="/posts", tags=["comments"])


def _service(db: DbDep) -> CommentService:
    return CommentService(CommentRepository(db))


@router.post("/comments", response_model=CommentResponse, status_code=201)
async def generate_random_comment(db: DbDep, chat_model: ChatModelPref):
    """Comment on a random recent post, by a random active user (any creator's, same as the
    equivalent random-post generation)."""
    service = _service(db)
    author = await service.get_random_active_user_or_raise()
    post = await service.get_random_recent_post_or_raise()
    comment = await service.generate_comment_for_post(post, author, chat_model)
    return CommentResponse.model_validate(comment)


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(post_id: int, data: CommentCreate, db: DbDep):
    """A plain, non-AI-generated user comment."""
    comment = await _service(db).create_comment(post_id, data.message)
    return CommentResponse.model_validate(comment)


@router.post("/{post_id}/comments/respond", response_model=CommentResponse)
async def respond_to_post(
    post_id: int, data: RespondRequest, db: DbDep, chat_model: ChatModelPref
):
    """An AI-generated reply, either by a specific user or a random active one."""
    service = _service(db)
    post = await service.get_post_or_raise(post_id)
    commenter = (
        await service.get_user_or_raise(data.user_id)
        if data.user_id
        else await service.get_random_active_user_or_raise()
    )
    comment = await service.generate_comment_for_post(post, commenter, chat_model)
    return CommentResponse.model_validate(comment)


@router.delete("/{post_id}/comments/{comment_id}", status_code=204)
async def delete_comment(post_id: int, comment_id: int, db: DbDep):
    await _service(db).delete_comment(comment_id)


@router.post("/{post_id}/comments/{comment_id}/translate", response_model=TranslateResponse)
async def translate_comment(
    post_id: int, comment_id: int, db: DbDep, chat_model: ChatModelPref
):
    body_en = await _service(db).translate_comment(post_id, comment_id, chat_model)
    return TranslateResponse(body_en=body_en)
