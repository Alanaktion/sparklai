from fastapi import APIRouter

from app.chats.router import conversations_router
from app.chats.router import router as chats_router
from app.comments.router import router as comments_router
from app.creators.router import router as creators_router
from app.image_jobs.router import router as image_jobs_router
from app.images.router import router as images_router
from app.media.router import router as media_router
from app.posts.router import router as posts_router
from app.users.router import import_router as import_character_router
from app.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(creators_router)
api_router.include_router(users_router)
api_router.include_router(posts_router)
api_router.include_router(comments_router)
api_router.include_router(chats_router)
api_router.include_router(conversations_router)
api_router.include_router(images_router)
api_router.include_router(image_jobs_router)
api_router.include_router(media_router)
api_router.include_router(import_character_router)


@api_router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
