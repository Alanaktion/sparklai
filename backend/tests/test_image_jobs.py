import asyncio
import io

import pytest
from httpx import AsyncClient
from PIL import Image as PILImage

from app.services import chat
from app.services.sd import client as sd_client
from app.services.sd.types import QueuedGenerationTask, SDImage

CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "Image Job Person",
        "description": "[Age: 26]",
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


def _fake_png_bytes() -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (4, 4), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


async def _fake_start_generation(request) -> QueuedGenerationTask:
    return _fake_generation_task()


def _fake_generation_task() -> QueuedGenerationTask:
    async def wait_for_result() -> SDImage:
        return SDImage(
            params={
                "prompt": "p",
                "negative_prompt": "",
                "width": 512,
                "height": 512,
                "cfg_scale": 7,
                "seed": 1,
            },
            data=_fake_png_bytes(),
        )

    return QueuedGenerationTask(
        provider="automatic1111", provider_job_id=None, wait_for_result=wait_for_result
    )


async def _login_new_creator(client: AsyncClient, name: str = "Image Job Tester") -> int:
    signup = await client.post("/api/creators", json={"name": name, "pin": "9999"})
    creator_id = signup.json()["id"]
    await client.post(f"/api/creators/{creator_id}", json={"pin": "9999"})
    return creator_id


async def _create_ai_user(client: AsyncClient) -> int:
    imported = await client.post("/api/import-character", json=CARD)
    return imported.json()["id"]


async def _wait_for_job(client: AsyncClient, job_id: int, timeout: float = 2.0) -> dict:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        response = await client.get(f"/api/image-jobs/{job_id}")
        body = response.json()
        if body["status"] in ("completed", "failed"):
            return body
        await asyncio.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish in time")


async def test_get_image_job_404(client: AsyncClient):
    response = await client.get("/api/image-jobs/999999")
    assert response.status_code == 404


async def test_list_image_jobs_empty_when_logged_out(client: AsyncClient):
    response = await client.get("/api/image-jobs")
    assert response.status_code == 200
    assert response.json() == []


async def test_job_runs_to_completion_and_sets_user_avatar(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    monkeypatch.setattr(sd_client, "start_generation", _fake_start_generation)

    async def fake_completion(*args, **kwargs):
        return "brown hair, tall, park bench, golden hour"

    monkeypatch.setattr(chat, "completion", fake_completion)

    # A blank prompt (the default from AvatarPicker.svelte's upload-only UI) triggers the
    # LLM-written-prompt branch and sets the result as the user's avatar once it completes.
    response = await client.post(f"/api/users/{user_id}/image")
    assert response.status_code == 202
    job_id = response.json()[0]["id"]

    finished = await _wait_for_job(client, job_id)
    assert finished["status"] == "completed"
    assert finished["image"] is not None
    assert finished["set_as_user_image"] is True

    profile = await client.get(f"/api/users/{user_id}")
    assert profile.json()["user"]["image_id"] == finished["image_id"]


async def test_job_marked_failed_on_generation_error(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    async def failing_start_generation(request):
        raise RuntimeError("backend unreachable")

    monkeypatch.setattr(sd_client, "start_generation", failing_start_generation)

    response = await client.post(
        f"/api/users/{user_id}/image",
        data={"prompt": "a nice photo", "aspect": "square", "count": "1"},
    )
    job_id = response.json()[0]["id"]

    finished = await _wait_for_job(client, job_id)
    assert finished["status"] == "failed"
    assert finished["error"] == "backend unreachable"


async def test_list_active_jobs_for_creator(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    await _login_new_creator(client)
    user_id = await _create_ai_user(client)

    async def never_finishes(request):
        await asyncio.sleep(10)
        raise AssertionError("should not reach here")

    monkeypatch.setattr(sd_client, "start_generation", never_finishes)

    await client.post(
        f"/api/users/{user_id}/image", data={"prompt": "x", "aspect": "square", "count": "1"}
    )
    await asyncio.sleep(0)  # let the task start and flip to queued/processing

    response = await client.get("/api/image-jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] in ("queued", "processing")


async def test_recover_pending_jobs_picks_up_leftover_rows(
    client: AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
):
    """Simulates a process restart: a `queued` row left over from a previous process (so nothing
    in this process's `_active_jobs` is tracking it) should get picked back up and run to
    completion by `recover_pending_jobs()`."""
    from app.db.models import ImageGenerationJob, User
    from app.services.sd import jobs as sd_jobs

    await _login_new_creator(client)
    user_id = await _create_ai_user(client)
    monkeypatch.setattr(sd_client, "start_generation", _fake_start_generation)

    user = await db_session.get(User, user_id)
    job = ImageGenerationJob(
        user_id=user.id,
        provider="automatic1111",
        status="queued",
        target="user_image",
        image_style="photo",
        prompt="leftover job",
        width=512,
        height=512,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    assert job.id not in sd_jobs._active_jobs
    await sd_jobs.recover_pending_jobs()

    finished = await _wait_for_job(client, job.id)
    assert finished["status"] == "completed"
