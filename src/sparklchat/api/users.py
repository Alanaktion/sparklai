"""Endpoints about the authenticated user."""

from fastapi import APIRouter

from sparklchat.api.deps import CurrentUserDep
from sparklchat.models.user import UserPublic

router = APIRouter(tags=["users"])


@router.get("/me")
async def read_me(current_user: CurrentUserDep) -> UserPublic:
    return current_user
