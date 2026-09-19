"""Aggregate router mounted under `/api`."""

from fastapi import APIRouter

from sparklchat.api import auth, characters, health, providers, settings, users

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(settings.router)
api_router.include_router(characters.router)
api_router.include_router(providers.router)
