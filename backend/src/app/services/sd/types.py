"""Shared types for the Stable Diffusion clients and job queue."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypedDict

SD_STYLE_NAMES: tuple[str, ...] = ("photo", "drawing", "stylized", "sdxl")
SDStyle = Literal["photo", "drawing", "stylized", "sdxl"]
SDBackend = Literal["automatic1111", "comfyui"]
ImageGenerationJobStatus = Literal["queued", "processing", "completed", "failed"]
ImageGenerationJobTarget = Literal["user_image", "post_image", "post_generation"]


class StableDiffusionParams(TypedDict):
    prompt: str
    negative_prompt: str
    width: int
    height: int
    cfg_scale: float
    seed: int


class SDModel(TypedDict, total=False):
    title: str
    model_name: str
    hash: str


@dataclass
class ImageGenerationRequest:
    prompt: str
    negative_prompt: str | None = None
    width: int = 512
    height: int = 512
    include_default_prompt: bool = True
    image_style: SDStyle | None = None


@dataclass
class SDImage:
    params: StableDiffusionParams
    data: bytes
    provider_metadata: dict | None = None


@dataclass
class QueuedGenerationTask:
    provider: SDBackend
    provider_job_id: str | None
    wait_for_result: Callable[[], Awaitable[SDImage]]
    provider_metadata: dict | None = None
