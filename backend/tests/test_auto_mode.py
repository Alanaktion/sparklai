import asyncio
import contextlib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CreatorAutoModeSettings, UserAutoModeSettings
from app.services import chat
from app.services.auto_mode import engine, scoring

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Auto Mode Character",
        "description": "[Age: 28]",
        "personality": "",
        "scenario": "",
        "first_mes": "",
        "mes_example": "",
        "creator_notes": "",
        "system_prompt": "",
        "post_history_instructions": "",
        "alternate_greetings": [],
        "tags": [],
        "character_version": "",
        "avatar": "",
        "creator": "",
        "extensions": {},
    },
}


async def _login_new_creator(client: AsyncClient, name: str = "Auto Mode Tester") -> int:
    signup = await client.post("/api/creators", json={"name": name, "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def _login_existing_creator(client: AsyncClient, creator_id: int) -> None:
    """Switches the session back to an already-created creator, unlike `_login_new_creator`
    (which always signs up a brand new one)."""
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})


async def _create_ai_user(client: AsyncClient, name: str | None = None) -> int:
    card = CARD if not name else {**CARD, "data": {**CARD["data"], "name": name}}
    imported = await client.post("/api/import-character", json=card)
    return imported.json()["id"]


async def _fake_post_schema_completion(schema_name, *args, **kwargs):
    assert schema_name == "post"
    return {"post_text": "An auto-generated post."}


async def _fake_free_completion(*args, **kwargs) -> str:
    return "An auto-generated comment."


async def _enable_creator_directly(
    db_session: AsyncSession, creator_id: int, **fields
) -> CreatorAutoModeSettings:
    """Writes `CreatorAutoModeSettings` straight to the DB, bypassing `PATCH /api/auto-mode` —
    that endpoint's handler starts a *live* background loop as soon as `enabled=True`, which would
    race with these tests' own direct `engine.run_creator_tick()` calls and unmocked LLM state.
    `test_patch_creator_settings_partial_update` below covers the HTTP endpoint itself."""
    row = CreatorAutoModeSettings(creator_id=creator_id, enabled=True, **fields)
    db_session.add(row)
    await db_session.commit()
    return row


async def _enable_user_posting(db_session: AsyncSession, user_id: int, **fields) -> UserAutoModeSettings:
    row = UserAutoModeSettings(user_id=user_id, **fields)
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.fixture(autouse=True)
async def _cleanup_active_loops():
    """`engine._active_creator_loops` is process-global state (same pattern as
    `sd.jobs._active_jobs`) — cancel any loop tasks left over after each test so one test's
    `ensure_creator_loop_running`/`recover_auto_mode_loops` call can't leak into the next.

    Awaiting each cancelled task (not just calling `.cancel()`) matters here: pytest-asyncio tears
    down this test's event loop right after the test function returns, so a `.cancel()` that's
    merely *requested* but never actually processed leaves the task pending across the loop
    teardown — the next test's fresh event loop + freshly-recreated in-memory schema then has a
    zombie task from a previous test's dead session sitting in `_active_creator_loops`, which
    surfaces as confusing cross-test failures instead of a clean, contained cancellation."""
    yield
    tasks = list(engine._active_creator_loops.values())
    for creator_id in list(engine._active_creator_loops):
        engine.stop_creator_loop(creator_id)
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def test_get_auto_mode_settings_defaults(client: AsyncClient):
    await _login_new_creator(client)
    response = await client.get("/api/auto-mode")
    assert response.status_code == 200
    body = response.json()
    assert body["creator_settings"] == {
        "enabled": False,
        "tick_interval_seconds": 300,
        "max_posts_per_tick": 2,
        "max_comments_per_tick": 5,
    }
    assert body["users"] == []


async def test_get_auto_mode_settings_requires_auth(client: AsyncClient):
    response = await client.get("/api/auto-mode")
    assert response.status_code == 401


async def test_patch_creator_settings_partial_update(client: AsyncClient):
    """No AI users exist for this creator, so the live loop this spawns has nothing to act on —
    it's stopped again immediately after, and by the autouse cleanup fixture regardless."""
    await _login_new_creator(client)
    response = await client.patch("/api/auto-mode", json={"enabled": True})
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["tick_interval_seconds"] == 300  # untouched field keeps its default

    await client.patch("/api/auto-mode", json={"enabled": False})


async def test_patch_user_settings_for_own_user(client: AsyncClient):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    response = await client.patch(
        f"/api/auto-mode/users/{user_id}",
        json={"auto_post_enabled": True, "post_frequency_per_day": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["auto_post_enabled"] is True
    assert body["post_frequency_per_day"] == 5
    assert body["auto_comment_enabled"] is False  # default, untouched


async def test_patch_user_settings_rejects_other_creators_user(client: AsyncClient):
    await _login_new_creator(client, "Creator A")
    other_user_id = await _create_ai_user(client)

    await _login_new_creator(client, "Creator B")
    response = await client.patch(
        f"/api/auto-mode/users/{other_user_id}", json={"auto_post_enabled": True}
    )
    assert response.status_code == 404


async def test_run_creator_tick_creates_post_when_roll_succeeds(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    creator_id = await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    await _enable_creator_directly(db_session, creator_id, max_posts_per_tick=1)
    await _enable_user_posting(db_session, user_id, auto_post_enabled=True, post_frequency_per_day=10)

    monkeypatch.setattr(engine.random, "random", lambda: 0.0)  # every roll "fires"
    monkeypatch.setattr(chat, "schema_completion", _fake_post_schema_completion)

    result = await engine.run_creator_tick(creator_id)
    assert result == {"posts_created": 1, "comments_created": 0}

    feed = await client.get("/api/posts")
    assert feed.json()["posts"][0]["body"] == "An auto-generated post."


async def test_run_creator_tick_creates_comment_when_roll_succeeds(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    creator_id = await _login_new_creator(client)
    author_id = await _create_ai_user(client, "Author")
    commenter_id = await _create_ai_user(client, "Commenter")

    monkeypatch.setattr(chat, "schema_completion", _fake_post_schema_completion)
    post_response = await client.post(f"/api/users/{author_id}/posts", json={})
    post_id = post_response.json()["post"]["id"]

    await _enable_creator_directly(db_session, creator_id, max_comments_per_tick=1)
    await _enable_user_posting(
        db_session, commenter_id, auto_comment_enabled=True, comment_frequency_per_day=10
    )

    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    monkeypatch.setattr(chat, "completion", _fake_free_completion)

    result = await engine.run_creator_tick(creator_id)
    assert result == {"posts_created": 0, "comments_created": 1}

    bundle = await client.get(f"/api/posts/{post_id}")
    bodies = [c["body"] for c in bundle.json()["post"]["comments"]]
    assert "An auto-generated comment." in bodies


async def test_run_creator_tick_respects_max_posts_per_tick(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    creator_id = await _login_new_creator(client)
    user_a = await _create_ai_user(client, "User A")
    user_b = await _create_ai_user(client, "User B")

    await _enable_creator_directly(db_session, creator_id, max_posts_per_tick=1)
    for uid in (user_a, user_b):
        await _enable_user_posting(db_session, uid, auto_post_enabled=True, post_frequency_per_day=10)

    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    monkeypatch.setattr(chat, "schema_completion", _fake_post_schema_completion)

    result = await engine.run_creator_tick(creator_id)
    assert result["posts_created"] == 1


async def test_run_creator_tick_noop_when_disabled(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    creator_id = await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    await _enable_user_posting(db_session, user_id, auto_post_enabled=True, post_frequency_per_day=10)
    # Note: no CreatorAutoModeSettings row created — defaults to enabled=False on first read.

    monkeypatch.setattr(engine.random, "random", lambda: 0.0)

    result = await engine.run_creator_tick(creator_id)
    assert result == {"posts_created": 0, "comments_created": 0}


async def test_run_creator_tick_skips_posts_already_commented_on(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    creator_id = await _login_new_creator(client)
    author_id = await _create_ai_user(client, "Author")
    commenter_id = await _create_ai_user(client, "Commenter")

    monkeypatch.setattr(chat, "schema_completion", _fake_post_schema_completion)
    post_response = await client.post(f"/api/users/{author_id}/posts", json={})
    post_id = post_response.json()["post"]["id"]

    monkeypatch.setattr(chat, "completion", _fake_free_completion)
    await client.post(f"/api/posts/{post_id}/comments/respond", json={"user_id": commenter_id})

    await _enable_creator_directly(db_session, creator_id, max_comments_per_tick=5)
    await _enable_user_posting(
        db_session, commenter_id, auto_comment_enabled=True, comment_frequency_per_day=10
    )

    monkeypatch.setattr(engine.random, "random", lambda: 0.0)

    result = await engine.run_creator_tick(creator_id)
    assert result["comments_created"] == 0


async def test_recover_auto_mode_loops_starts_enabled_creators(
    client: AsyncClient, db_session: AsyncSession
):
    """Mirrors `test_recover_pending_jobs_picks_up_leftover_rows`: a settings row left
    `enabled=True` by a previous process (so nothing in this process's `_active_creator_loops` is
    tracking it) should get a loop re-attached by `recover_auto_mode_loops()`."""
    creator_id = await _login_new_creator(client)
    await _enable_creator_directly(db_session, creator_id, tick_interval_seconds=3600)

    assert creator_id not in engine._active_creator_loops
    await engine.recover_auto_mode_loops()
    assert creator_id in engine._active_creator_loops


async def test_activity_log_scoped_to_own_creator(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    creator_a = await _login_new_creator(client, "Creator A")
    user_a = await _create_ai_user(client, "User A")

    await _enable_creator_directly(db_session, creator_a, max_posts_per_tick=1)
    await _enable_user_posting(db_session, user_a, auto_post_enabled=True, post_frequency_per_day=10)

    monkeypatch.setattr(engine.random, "random", lambda: 0.0)
    monkeypatch.setattr(chat, "schema_completion", _fake_post_schema_completion)
    await engine.run_creator_tick(creator_a)

    await _login_new_creator(client, "Creator B")
    await _create_ai_user(client, "User B")

    response = await client.get("/api/auto-mode/activity")
    assert response.status_code == 200
    assert response.json()["items"] == []  # creator B sees none of creator A's activity

    await _login_existing_creator(client, creator_a)
    response = await client.get("/api/auto-mode/activity")
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "post"
    assert items[0]["user_name"] == "User A"


def test_recency_weight_decays_with_rank():
    assert scoring.recency_weight(0) == 1.0
    assert scoring.recency_weight(1) == pytest.approx(0.85)
    assert scoring.recency_weight(5) < scoring.recency_weight(1) < scoring.recency_weight(0)


def test_combine_relevance_into_probability_applies_recency():
    fresh = scoring.combine_relevance_into_probability(0.5, 1.0, recency=1.0)
    stale = scoring.combine_relevance_into_probability(0.5, 1.0, recency=0.1)
    assert stale == pytest.approx(0.05)
    assert stale < fresh


async def test_run_creator_tick_comments_prefer_more_recent_posts(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """With a comment budget of 1 and both posts' rolls forced to "fire", the newer post should
    win the budget — its recency-adjusted probability sorts higher than the older post's, even
    though both share the same commenter/author/frequency/relationship inputs."""
    creator_id = await _login_new_creator(client)
    author_id = await _create_ai_user(client, "Author")
    commenter_id = await _create_ai_user(client, "Commenter")

    monkeypatch.setattr(chat, "schema_completion", _fake_post_schema_completion)
    older = await client.post(f"/api/users/{author_id}/posts", json={})
    newer = await client.post(f"/api/users/{author_id}/posts", json={})
    older_post_id = older.json()["post"]["id"]
    newer_post_id = newer.json()["post"]["id"]

    await _enable_creator_directly(db_session, creator_id, max_comments_per_tick=1)
    await _enable_user_posting(
        db_session, commenter_id, auto_comment_enabled=True, comment_frequency_per_day=10
    )

    monkeypatch.setattr(engine.random, "random", lambda: 0.0)  # every roll "fires"
    monkeypatch.setattr(chat, "completion", _fake_free_completion)

    result = await engine.run_creator_tick(creator_id)
    assert result["comments_created"] == 1

    newer_bundle = await client.get(f"/api/posts/{newer_post_id}")
    older_bundle = await client.get(f"/api/posts/{older_post_id}")
    assert len(newer_bundle.json()["post"]["comments"]) == 1
    assert len(older_bundle.json()["post"]["comments"]) == 0
