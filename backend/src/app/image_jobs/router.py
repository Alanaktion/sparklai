from fastapi import APIRouter

from app.dependencies import CurrentCreator, DbDep
from app.exceptions import NotFoundError
from app.image_jobs.repository import ImageJobRepository
from app.image_jobs.schemas import ImageGenerationJobResponse
from app.services.sd.jobs import ensure_job_running

router = APIRouter(prefix="/image-jobs", tags=["image-jobs"])


@router.get("", response_model=list[ImageGenerationJobResponse])
async def list_active_image_jobs(creator: CurrentCreator, db: DbDep):
    """Port of `image-jobs/+server.ts` — the creator's still-in-flight jobs, re-kicking any that
    somehow aren't running (e.g. after a backend restart that missed the startup recovery pass)."""
    if not creator:
        return []
    jobs = await ImageJobRepository(db).list_active_for_creator(creator.id)
    for job in jobs:
        ensure_job_running(job.id)
    return jobs


@router.get("/{job_id}", response_model=ImageGenerationJobResponse)
async def get_image_job(job_id: int, db: DbDep):
    job = await ImageJobRepository(db).get_by_id(job_id)
    if not job:
        raise NotFoundError("Image generation job", job_id)
    if job.status in ("queued", "processing"):
        ensure_job_running(job.id)
    return job
