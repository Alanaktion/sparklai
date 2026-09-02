"""Port of `src/lib/server/sd/index.ts`'s Automatic1111/ComfyUI clients.

Unlike the original, there's no mutable module-level "current style"/"current model" default —
each request must say what style it wants (`ImageGenerationRequest.image_style`), falling back to
a fixed `"photo"` default rather than a shared, cookie-settable global (the same bug class fixed
for the chat client in `app/services/chat.py`). Per-request style/model *overrides* driven by a
cookie (BACKEND_MIGRATION.md's "Model/style preferences" item) can layer on top of this later by
resolving the cookie to an explicit `image_style`/model argument before calling in, exactly like
`chat.resolve_model()` already does for chat.

The one piece of intentional, non-shared mutable state here is `_last_applied_model`: a
process-local cache of the last Automatic1111 checkpoint we told the backend to load, purely to
skip a redundant (and expensive — it's a multi-GB checkpoint swap) `options` call when consecutive
jobs use the same style. It does not affect *which* style/model any given job uses (that always
comes from the job's own data), only whether we bother re-issuing the switch.

Not ported from the original: the `SD_DEBUG_LOG` request/response file-logging hook — it's a
dev-only debugging aid, not user-facing behavior.
"""

import asyncio
import base64
import json
import logging
import random
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.sd.types import (
    ImageGenerationRequest,
    QueuedGenerationTask,
    SDBackend,
    SDImage,
    SDModel,
    SDStyle,
    StableDiffusionParams,
)

logger = logging.getLogger(__name__)

_STEPS = 20
_CFG_SCALE = 7
_WORKFLOW_DIR = Path(__file__).parent / "workflows"

backend: SDBackend = "comfyui" if settings.sd_backend == "comfyui" else "automatic1111"

styles: dict[SDStyle, dict[str, str]] = {
    "photo": {
        "model": settings.sd_photo_model,
        "prompt": settings.sd_photo_prompt,
        "negative_prompt": settings.sd_photo_negative_prompt,
    },
    "drawing": {
        "model": settings.sd_drawing_model,
        "prompt": settings.sd_drawing_prompt,
        "negative_prompt": settings.sd_drawing_negative_prompt,
    },
    "stylized": {
        "model": settings.sd_stylized_model,
        "prompt": settings.sd_stylized_prompt,
        "negative_prompt": settings.sd_stylized_negative_prompt,
    },
    "sdxl": {
        "model": settings.sd_sdxl_model,
        "prompt": settings.sd_sdxl_prompt,
        "negative_prompt": settings.sd_sdxl_negative_prompt,
    },
}

_DEFAULT_STYLE: SDStyle = "photo"
_last_applied_model: str | None = None
_workflow_cache: dict[SDStyle, dict[str, Any]] = {}
_client = httpx.AsyncClient(timeout=60.0)


def _sd_url(path: str) -> str:
    base = settings.sd_url if settings.sd_url.endswith("/") else f"{settings.sd_url}/"
    return base + path.lstrip("/")


def _now_seed() -> int:
    return random.randint(0, 2147483647)


def _build_params(request: ImageGenerationRequest) -> StableDiffusionParams:
    image_style = request.image_style or _DEFAULT_STYLE
    include_default_prompt = request.include_default_prompt
    style_config = styles[image_style]

    if include_default_prompt:
        positive_prompt = "\n".join(filter(None, [request.prompt, style_config["prompt"]]))
    else:
        positive_prompt = request.prompt

    if request.negative_prompt:
        negative_prompt = (
            "\n".join(filter(None, [request.negative_prompt, style_config["negative_prompt"]]))
            if include_default_prompt
            else request.negative_prompt
        )
    else:
        negative_prompt = style_config["negative_prompt"] if include_default_prompt else ""

    return StableDiffusionParams(
        prompt=positive_prompt,
        negative_prompt=negative_prompt,
        width=request.width,
        height=request.height,
        cfg_scale=_CFG_SCALE,
        seed=_now_seed(),
    )


def _read_workflow_template(image_style: SDStyle) -> dict[str, Any]:
    cached = _workflow_cache.get(image_style)
    if cached is not None:
        return cached
    raw = (_WORKFLOW_DIR / f"{image_style}.json").read_text()
    parsed = json.loads(raw)
    _workflow_cache[image_style] = parsed
    return parsed


def _apply_template_values(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, list):
        return [_apply_template_values(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _apply_template_values(child, replacements) for key, child in value.items()}
    return value


def _extract_history_entry(body: Any, prompt_id: str) -> dict[str, Any]:
    if isinstance(body, dict) and prompt_id in body:
        return body[prompt_id] or {}
    return body or {}


def _extract_output_image(entry: dict[str, Any], output_node_id: str) -> dict[str, Any] | None:
    outputs = entry.get("outputs") or {}
    direct = outputs.get(output_node_id, {}).get("images") or []
    if direct:
        return direct[0]
    for output in outputs.values():
        images = output.get("images") or []
        if images:
            return images[0]
    return None


async def _ensure_model_loaded(model_name: str) -> None:
    """Automatic1111-only: switch the loaded checkpoint, skipping the call entirely if it's
    already the last one we applied (see module docstring)."""
    global _last_applied_model
    if not model_name or model_name == _last_applied_model:
        return
    await _client.post(_sd_url("options"), json={"sd_model_checkpoint": model_name})
    _last_applied_model = model_name


async def _start_automatic1111_generation(
    request: ImageGenerationRequest,
) -> QueuedGenerationTask:
    image_style = request.image_style or _DEFAULT_STYLE
    await _ensure_model_loaded(styles[image_style]["model"])
    params = _build_params(request)

    async def wait_for_result() -> SDImage:
        response = await _client.post(
            _sd_url("txt2img"),
            json={
                "prompt": params["prompt"],
                "negative_prompt": params["negative_prompt"],
                "num_inference_steps": _STEPS,
                "height": params["height"],
                "width": params["width"],
                "seed": params["seed"],
                "cfg_scale": params["cfg_scale"],
                "steps": _STEPS,
                "restore_faces": True,
            },
        )
        if response.is_error:
            raise RuntimeError(f"Automatic1111 txt2img failed with {response.status_code}")

        body = response.json()
        return SDImage(
            params=params,
            data=base64.b64decode(body["images"][0]),
            provider_metadata={"info": body["info"]} if body.get("info") else None,
        )

    return QueuedGenerationTask(provider=backend, provider_job_id=None, wait_for_result=wait_for_result)


async def _start_comfy_generation(request: ImageGenerationRequest) -> QueuedGenerationTask:
    image_style = request.image_style or _DEFAULT_STYLE
    params = _build_params(request)
    template = _read_workflow_template(image_style)
    filename_prefix = f"sparklai-{image_style}-{int(asyncio.get_event_loop().time() * 1000)}"
    replacements = {
        "__MODEL__": styles[image_style]["model"],
        "__POSITIVE_PROMPT__": params["prompt"],
        "__NEGATIVE_PROMPT__": params["negative_prompt"],
        "__WIDTH__": params["width"],
        "__HEIGHT__": params["height"],
        "__SEED__": params["seed"],
        "__STEPS__": _STEPS,
        "__CFG_SCALE__": params["cfg_scale"],
        "__FILENAME_PREFIX__": filename_prefix,
    }
    prompt_graph = _apply_template_values(template["prompt"], replacements)
    client_id = str(uuid.uuid4())

    response = await _client.post(
        _sd_url("prompt"), json={"prompt": prompt_graph, "client_id": client_id}
    )
    if response.is_error:
        raise RuntimeError(f"ComfyUI prompt submission failed with {response.status_code}")

    body = response.json()
    prompt_id = body.get("prompt_id")
    if not prompt_id:
        raise RuntimeError("ComfyUI did not return a prompt_id")

    output_node_id = template["output_node_id"]

    async def wait_for_result() -> SDImage:
        deadline = asyncio.get_event_loop().time() + settings.sd_comfy_timeout_ms / 1000

        while asyncio.get_event_loop().time() < deadline:
            history_response = await _client.get(_sd_url(f"history/{prompt_id}"))
            if history_response.is_error:
                raise RuntimeError(f"ComfyUI history lookup failed with {history_response.status_code}")

            entry = _extract_history_entry(history_response.json(), prompt_id)
            if (entry.get("status") or {}).get("status_str") == "error":
                raise RuntimeError("ComfyUI workflow execution failed")

            image = _extract_output_image(entry, output_node_id)
            if image:
                image_response = await _client.get(
                    _sd_url("view"),
                    params={
                        "filename": image["filename"],
                        "subfolder": image.get("subfolder", ""),
                        "type": image.get("type", "output"),
                    },
                )
                if image_response.is_error:
                    raise RuntimeError(f"ComfyUI image fetch failed with {image_response.status_code}")

                return SDImage(
                    params=params,
                    data=image_response.content,
                    provider_metadata={
                        "promptId": prompt_id,
                        "outputNodeId": output_node_id,
                        "image": image,
                        "status": entry.get("status"),
                        "meta": entry.get("meta"),
                    },
                )

            await asyncio.sleep(settings.sd_comfy_poll_interval_ms / 1000)

        raise RuntimeError(f"ComfyUI workflow timed out after {settings.sd_comfy_timeout_ms}ms")

    return QueuedGenerationTask(
        provider=backend,
        provider_job_id=prompt_id,
        provider_metadata={
            "clientId": client_id,
            "outputNodeId": output_node_id,
            "filenamePrefix": filename_prefix,
        },
        wait_for_result=wait_for_result,
    )


async def start_generation(request: ImageGenerationRequest) -> QueuedGenerationTask:
    if backend == "comfyui":
        return await _start_comfy_generation(request)
    return await _start_automatic1111_generation(request)


async def fetch_models() -> list[SDModel]:
    """Automatic1111 only — ComfyUI has no equivalent "list checkpoints" endpoint this app uses."""
    if backend != "automatic1111":
        return []
    try:
        response = await _client.get(_sd_url("sd-models"))
        if response.is_error:
            raise RuntimeError(f"Stable Diffusion model fetch failed with {response.status_code}")
        return response.json()
    except Exception:
        logger.exception("Failed to fetch Stable Diffusion models")
        return []


def supports_model_selection() -> bool:
    return backend == "automatic1111"
