"""In-memory image-generation job queue, adapted for FastAPI/asyncio.

Fire-and-forget `asyncio.create_task` per job, tracked in a process-local dict so a job already
running doesn't get double-started. Two things worth knowing:

- Each background job runs with its *own* `AsyncSession` from `database.async_session_factory`,
  created fresh inside the task — a SQLAlchemy `AsyncSession` isn't safe to share across
  concurrently running coroutines. Accessed as `database.async_session_factory()` (module
  attribute), not imported by name, so tests can monkeypatch it to point background tasks at a
  test database too — see `tests/conftest.py`.
- `recover_pending_jobs()` (called from `main.py`'s startup) re-attaches any `queued`/`processing`
  rows left over from a previous process — e.g. after a crash or redeploy mid-generation.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import database
from app.db.models import Image, ImageGenerationJob, Post, User
from app.services import image_utils
from app.services.sd import client as sd_client
from app.services.sd.types import ImageGenerationJobTarget, ImageGenerationRequest, SDStyle

logger = logging.getLogger(__name__)

_active_jobs: dict[int, asyncio.Task] = {}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_dimension(value: int | None, fallback: int = 512) -> int:
    if not value or value <= 0:
        return fallback
    return int(value)


async def enqueue_image_job(
    session: AsyncSession,
    *,
    user_id: int,
    target: ImageGenerationJobTarget,
    prompt: str,
    negative_prompt: str | None = None,
    post_id: int | None = None,
    width: int | None = None,
    height: int | None = None,
    include_default_prompt: bool = True,
    image_style: SDStyle = "photo",
    set_as_user_image: bool = False,
) -> ImageGenerationJob:
    timestamp = _now()
    job = ImageGenerationJob(
        user_id=user_id,
        post_id=post_id,
        provider=sd_client.backend,
        status="queued",
        target=target,
        image_style=image_style,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=_normalize_dimension(width),
        height=_normalize_dimension(height),
        include_default_prompt=include_default_prompt,
        set_as_user_image=set_as_user_image,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    ensure_job_running(job.id)
    return job


def ensure_job_running(job_id: int) -> None:
    if job_id in _active_jobs:
        return
    task = asyncio.create_task(_run_image_job(job_id))
    _active_jobs[job_id] = task
    task.add_done_callback(lambda _: _active_jobs.pop(job_id, None))


async def recover_pending_jobs() -> None:
    """Called once from `main.py`'s startup lifespan."""
    async with database.async_session_factory() as session:
        result = await session.execute(
            select(ImageGenerationJob.id).where(
                ImageGenerationJob.status.in_(["queued", "processing"])
            )
        )
        for job_id in result.scalars().all():
            ensure_job_running(job_id)


async def _run_image_job(job_id: int) -> None:
    async with database.async_session_factory() as session:
        job = await session.get(ImageGenerationJob, job_id)
        if not job or job.status in ("completed", "failed"):
            return

        try:
            request = ImageGenerationRequest(
                prompt=job.prompt,
                negative_prompt=job.negative_prompt,
                width=job.width,
                height=job.height,
                include_default_prompt=job.include_default_prompt,
                image_style=job.image_style,
            )
            task = await sd_client.start_generation(request)

            job.status = "processing"
            job.provider_job_id = task.provider_job_id
            job.provider_metadata = task.provider_metadata
            job.started_at = job.started_at or _now()
            job.updated_at = _now()
            job.error = None
            await session.commit()

            result = await task.wait_for_result()
            webp_data = await asyncio.to_thread(image_utils.to_webp, result.data)

            image = Image(user_id=job.user_id, params=dict(result.params), data=webp_data)
            session.add(image)
            await session.flush()

            if job.set_as_user_image:
                user = await session.get(User, job.user_id)
                if user:
                    user.image_id = image.id

            if job.post_id is not None:
                post = await session.get(Post, job.post_id)
                if post:
                    post.image_id = image.id

            job.status = "completed"
            job.image_id = image.id
            job.provider_metadata = {
                **(task.provider_metadata or {}),
                **(result.provider_metadata or {}),
            }
            job.completed_at = _now()
            job.updated_at = _now()
            job.error = None
            await session.commit()
        except Exception as exc:
            logger.exception("Image generation job %s failed", job_id)
            await session.rollback()
            failed_job = await session.get(ImageGenerationJob, job_id)
            if failed_job:
                failed_job.status = "failed"
                failed_job.error = str(exc) or "Image generation failed"
                failed_job.completed_at = _now()
                failed_job.updated_at = _now()
                await session.commit()
