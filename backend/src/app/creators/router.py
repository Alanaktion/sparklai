from fastapi import APIRouter, Response

from app.config import settings
from app.creators.repository import CreatorRepository
from app.creators.schemas import CreatorCreate, CreatorLogin, CreatorResponse, CreatorUpdate
from app.creators.service import CreatorService
from app.dependencies import CurrentCreator, DbDep, RequireCreator
from app.security.session import create_session_token

router = APIRouter(prefix="/creators", tags=["creators"])


def _service(db: DbDep) -> CreatorService:
    return CreatorService(CreatorRepository(db))


@router.get("", response_model=list[CreatorResponse])
async def list_creators(db: DbDep):
    return await _service(db).list_all()


@router.get("/me", response_model=CreatorResponse | None)
async def get_current(creator: CurrentCreator):
    return creator


@router.post("", response_model=CreatorResponse, status_code=201)
async def signup(data: CreatorCreate, db: DbDep):
    return await _service(db).signup(data)


@router.post("/{creator_id}", response_model=CreatorResponse)
async def login(creator_id: int, data: CreatorLogin, response: Response, db: DbDep):
    """Path matches the original `api/creators/[id]/+server.ts` POST route exactly, since
    `CreatorSwitcher.svelte` already calls it client-side and doesn't need to change."""
    creator = await _service(db).authenticate(creator_id, data.pin)
    token = create_session_token(creator.id)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return creator


@router.delete("/session")
async def logout(response: Response):
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"success": True}


@router.patch("/me", response_model=CreatorResponse)
async def update_profile(data: CreatorUpdate, creator: RequireCreator, db: DbDep):
    return await _service(db).update_profile(creator, data)
