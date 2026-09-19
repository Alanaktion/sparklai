"""Liveness and readiness endpoints."""

from fastapi import APIRouter
from sqlalchemy import text

from sparklchat.db import SessionDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: the process is up and serving requests."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(db: SessionDep) -> dict[str, str]:
    """Readiness probe: the database is reachable."""
    await db.exec(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
