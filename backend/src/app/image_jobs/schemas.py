from app.core.schemas import BaseSchema


class ImageJobImageResponse(BaseSchema):
    id: int
    params: dict | None = None
    blur: bool


class ImageGenerationJobResponse(BaseSchema):
    id: int
    user_id: int
    post_id: int | None = None
    provider: str
    status: str
    target: str
    image_style: str
    prompt: str
    negative_prompt: str | None = None
    width: int
    height: int
    include_default_prompt: bool
    set_as_user_image: bool
    provider_job_id: str | None = None
    provider_metadata: dict | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    image_id: int | None = None
    image: ImageJobImageResponse | None = None
