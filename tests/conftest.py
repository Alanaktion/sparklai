"""Shared pytest fixtures.

Each test gets its own throwaway SQLite file and an app whose DB dependency is
overridden to use it, so tests never touch the development database.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from sparklchat.config import Settings, get_settings
from sparklchat.db import build_engine, create_db_and_tables, create_session, get_session
from sparklchat.main import create_app

PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch) -> None:
    """Keep uploads out of the real tree and token counting offline/deterministic."""
    monkeypatch.setenv("AVATAR_DIR", str(tmp_path / "avatars"))
    monkeypatch.setenv("PACKAGE_DIR", str(tmp_path / "packages"))
    # tiktoken downloads its BPE data on first use; tests stay offline.
    monkeypatch.setenv("TOKENIZER", "heuristic")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _override_session(app: FastAPI, engine: AsyncEngine) -> None:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with create_session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session


def _asgi_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def password() -> str:
    return PASSWORD


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    # Point at a missing build directory so API tests are unaffected by a real
    # `frontend/build` that happens to exist in the working tree.
    return create_app(Settings(frontend_dist_dir=tmp_path / "no-frontend-build"))


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await create_db_and_tables(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def client(app: FastAPI, engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    _override_session(app, engine)
    async with _asgi_client(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def spa_dist(tmp_path: Path) -> Path:
    """A stand-in for the output of `npm run build` in `frontend/`."""
    dist = tmp_path / "frontend-build"
    (dist / "_app" / "immutable").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Sparkl Chat SPA</title>")
    (dist / "_app" / "immutable" / "app.js").write_text("console.log('sparklchat');")
    (dist / "robots.txt").write_text("User-agent: *\n")
    return dist


@pytest.fixture
async def spa_client(engine: AsyncEngine, spa_dist: Path) -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(frontend_dist_dir=spa_dist))
    _override_session(app, engine)
    async with _asgi_client(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def registered_user(client: AsyncClient, password: str) -> dict:
    response = await client.post(
        "/api/auth/register",
        json={"email": "ash@example.com", "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def auth_headers(client: AsyncClient, registered_user: dict, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/auth/login",
        data={"username": registered_user["email"], "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def v1_card() -> dict:
    """A V1 card, including a key the spec does not define."""
    return {
        "name": "Haruhi",
        "description": "A cheerful but blunt student.",
        "personality": "Energetic and demanding.",
        "scenario": "The club room after school.",
        "first_mes": "Hi!",
        "mes_example": "<START>\n{{user}}: hi\n{{char}}: hello",
        "custom_v1_key": {"keep": "me"},
    }


@pytest.fixture
def v2_card() -> dict:
    """A V2 card exercising extensions at card, book, and entry level."""
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "Haruhi",
            "description": "A cheerful but blunt student.",
            "personality": "Energetic and demanding.",
            "scenario": "The club room after school.",
            "first_mes": "Hi!",
            "mes_example": "",
            "creator_notes": "Made for tests.",
            "system_prompt": "You are {{char}}.",
            "post_history_instructions": "",
            "alternate_greetings": ["Oh, it's you."],
            "character_book": {
                "name": "Club",
                "scan_depth": 4,
                "token_budget": 512,
                "recursive_scanning": False,
                "extensions": {"book_ext": {"keep": True}},
                "entries": [
                    {
                        "keys": ["brigade"],
                        "secondary_keys": ["club"],
                        "content": "The SOS Brigade.",
                        "enabled": True,
                        "insertion_order": 10,
                        "case_sensitive": False,
                        "selective": True,
                        "constant": False,
                        "position": "before_char",
                        "priority": 5,
                        "id": 1,
                        "comment": "club lore",
                        "name": "Brigade",
                        "extensions": {"entry_ext": [1, 2, 3]},
                    }
                ],
            },
            "tags": ["Anime", "school"],
            "creator": "tests",
            "character_version": "1.1",
            "extensions": {"card_ext": {"nested": "value"}},
        },
    }


@pytest.fixture
def v3_card() -> dict:
    """A V3 card exercising the fields V2 does not have."""
    return {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": "Haruhi",
            "nickname": "Haru",
            "description": "A cheerful but blunt student.",
            "personality": "Energetic and demanding.",
            "scenario": "The club room after school.",
            "first_mes": "Hi!",
            "mes_example": "",
            "creator_notes": "Made for tests.",
            "creator_notes_multilingual": {"en": "English notes.", "ja": "Japanese notes."},
            "system_prompt": "You are {{char}}.",
            "post_history_instructions": "",
            "alternate_greetings": ["Oh, it's you."],
            "group_only_greetings": ["Everyone, listen up!"],
            "source": ["example-id", "https://example.com/haruhi.png"],
            "assets": [
                {
                    "type": "icon",
                    "uri": "embeded://assets/icon/images/main.png",
                    "name": "main",
                    "ext": "png",
                },
                {
                    "type": "user_icon",
                    "uri": "ccdefault:",
                    "name": "Ash",
                    "ext": "png",
                },
            ],
            "creation_date": 1700000000,
            "modification_date": 1700000100,
            "character_book": {
                "name": "Club",
                "extensions": {},
                "entries": [
                    {
                        "keys": [r"/brigade|club/i"],
                        "content": "The SOS Brigade.",
                        "enabled": True,
                        "insertion_order": 10,
                        "use_regex": True,
                        "id": "brigade-lore",
                        "extensions": {"entry_ext": [1, 2, 3]},
                    }
                ],
            },
            "tags": ["Anime", "school"],
            "creator": "tests",
            "character_version": "1.1",
            "extensions": {"card_ext": {"keep": True}},
        },
    }


@pytest.fixture
def login_as(client: AsyncClient, password: str):
    """Register and log in another user, returning their auth headers."""

    async def _login(email: str) -> dict[str, str]:
        await client.post("/api/auth/register", json={"email": email, "password": password})
        response = await client.post(
            "/api/auth/login", data={"username": email, "password": password}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login
