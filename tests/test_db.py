"""Checks that the async SQLModel layer creates schema and round-trips rows."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.models import User


async def test_create_schema_and_user(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        session.add(User(email="ash@example.com", hashed_password="not-a-real-hash"))
        await session.commit()

    async with AsyncSession(engine) as session:
        users = (await session.exec(select(User))).all()

    assert [user.email for user in users] == ["ash@example.com"]


async def test_ready_reports_database(client: AsyncClient) -> None:
    response = await client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
