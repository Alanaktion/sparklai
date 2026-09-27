"""ComfyUI image-generation client.

Unlike the chat providers, ComfyUI has no request/response completion
protocol: a generation submits a node graph ("workflow"), then polls a history
endpoint until the job finishes, then downloads the resulting files. This is
an async port of the `hermes-comfyui-plugin` reference plugin's
`comfyui.py`/`run.py` (blocking `urllib`), adapted to `httpx` and to reading
its configuration from a stored `Provider` row's `extra_params` instead of
environment variables:

- `extra_params.workflow` — one of `comfyui_workflows.WORKFLOW_NAMES`, or
  `"custom"` (default `"image"`).
- `extra_params.workflow_json` — required when `workflow` is `"custom"`: a raw
  ComfyUI node graph using the same `__UPPER_SNAKE__` placeholder convention
  as the bundled templates.
- `extra_params.width` / `height` / `negative_prompt` / `duration` /
  `filename_prefix` — generation defaults, overridable per request.
- `Provider.model` — default checkpoint/UNet filename override, like the
  plugin's `model` argument / `models.ini`.
- `Provider.api_key` — sent as `x-api-key`, ComfyUI's own convention (not the
  chat clients' `Authorization: Bearer`).

`complete()` has no chat-completion meaning here; it is repurposed as a cheap
connectivity check so `/providers/{id}/test` and the one-off `/complete`
debug endpoint work for ComfyUI providers without special-casing them.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from sparklchat.services.providers.base import BaseClient, ChatMessage, ProviderError
from sparklchat.services.providers.comfyui_workflows import (
    DEFAULT_MODELS,
    WORKFLOW_NAMES,
    WORKFLOW_TEMPLATES,
)

DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024
DEFAULT_DURATION = 97
DEFAULT_FILENAME_PREFIX = "sparklchat"
DEFAULT_POLL_INTERVAL_SECS = 2.0
DEFAULT_POLL_TIMEOUT_SECS = 300.0

_PLACEHOLDER_RE = re.compile(r"__[A-Z_]{3,}__")


@dataclass(frozen=True, slots=True)
class OutputFile:
    filename: str
    subfolder: str
    kind: str


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    filename: str
    content_type: str
    data: bytes


def _apply_replacements(obj: Any, replacements: dict[str, Any]) -> Any:
    """Recursively splice in placeholder values, preserving non-string types."""
    if isinstance(obj, dict):
        return {key: _apply_replacements(value, replacements) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_apply_replacements(value, replacements) for value in obj]
    if isinstance(obj, str):
        return replacements.get(obj, obj)
    return obj


def _remaining_placeholders(workflow: dict) -> list[str]:
    raw = json.dumps(workflow)
    return sorted(set(_PLACEHOLDER_RE.findall(raw)))


def _collect_output_files(history_entry: dict) -> list[OutputFile]:
    """Collect every image/video/gif/audio reference from a history entry."""
    files: list[OutputFile] = []
    outputs = history_entry.get("outputs")
    if not isinstance(outputs, dict):
        return files
    for node in outputs.values():
        if not isinstance(node, dict):
            continue
        for key in ("images", "videos", "gifs", "audio"):
            items = node.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                files.append(
                    OutputFile(
                        filename=str(item.get("filename", "")),
                        subfolder=str(item.get("subfolder", "")),
                        kind=str(item.get("type", "")),
                    )
                )
    return files


class ComfyUIClient(BaseClient):
    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key
        return headers

    def _workflow_name(self) -> str:
        name = str(self.config.extra_params.get("workflow") or "image")
        if name != "custom" and name not in WORKFLOW_NAMES:
            raise ProviderError(
                f"unknown ComfyUI workflow {name!r}; available: {', '.join(WORKFLOW_NAMES)}, custom"
            )
        return name

    def _workflow_template(self, name: str) -> dict:
        if name == "custom":
            template = self.config.extra_params.get("workflow_json")
            if not isinstance(template, dict) or not template:
                raise ProviderError(
                    "this provider's workflow is 'custom' but extra_params.workflow_json "
                    "is missing or empty"
                )
            return template
        return WORKFLOW_TEMPLATES[name]

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        """Connectivity check: ComfyUI has no chat completion, so this just
        confirms the server answers, for `/test` and the one-off `/complete`
        debug endpoint."""
        del messages  # ComfyUI has nothing to reply to; only reachability matters.
        async with self._client() as http:
            response = await http.get(self._url("/system_stats"), headers=self._headers())
            await self._raise_for_status(response)
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = {}
        version = ((data or {}).get("system") or {}).get("comfyui_version")
        return f"ComfyUI reachable{f' (version {version})' if version else ''}"

    def _view_url(self, file: OutputFile) -> str:
        parts = [f"filename={quote(file.filename)}"]
        if file.subfolder:
            parts.append(f"subfolder={quote(file.subfolder)}")
        if file.kind:
            parts.append(f"type={quote(file.kind)}")
        return self._url(f"/view?{'&'.join(parts)}")

    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        width: int | None = None,
        height: int | None = None,
        seed: int | None = None,
        model: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Submit the provider's workflow and poll it to completion.

        Yields `{"status": "queued", "prompt_id": ..., "warning": ...}`, then
        `{"status": "running", "elapsed": n}` roughly every poll interval, then
        `{"status": "done", "images": [GeneratedImage, ...], "seed": ...,
        "width": ..., "height": ..., "prompt_id": ...}`. Raises `ProviderError`
        on any failure (bad workflow config, rejected submission, a job that
        errors or times out, or a completed job with no output files).
        """
        extra = self.config.extra_params
        workflow_name = self._workflow_name()
        template = self._workflow_template(workflow_name)

        resolved_seed = seed if seed is not None else random.randint(0, 0xFFFF_FFFF)
        resolved_width = width or int(extra.get("width") or DEFAULT_WIDTH)
        resolved_height = height or int(extra.get("height") or DEFAULT_HEIGHT)
        resolved_model = model or self.config.model or DEFAULT_MODELS.get(workflow_name)

        replacements: dict[str, Any] = {
            "__POSITIVE_PROMPT__": prompt,
            "__PROMPT__": prompt,
            "__NEGATIVE_PROMPT__": negative_prompt,
            "__WIDTH__": resolved_width,
            "__HEIGHT__": resolved_height,
            "__SEED__": resolved_seed,
            "__FILENAME_PREFIX__": str(extra.get("filename_prefix") or DEFAULT_FILENAME_PREFIX),
            "__DURATION__": int(extra.get("duration") or DEFAULT_DURATION),
        }
        if resolved_model:
            replacements["__MODEL__"] = resolved_model

        workflow = _apply_replacements(template, replacements)
        leftovers = _remaining_placeholders(workflow)
        warning = (
            f"unresolved placeholders in workflow: {', '.join(leftovers)}" if leftovers else None
        )

        client_id = f"sparklchat-{random.randint(0, 0xFFFF_FFFF):08x}"
        poll_interval = float(extra.get("poll_interval") or DEFAULT_POLL_INTERVAL_SECS)
        poll_timeout = float(extra.get("poll_timeout") or DEFAULT_POLL_TIMEOUT_SECS)

        async with self._client() as http:
            response = await http.post(
                self._url("/prompt"),
                json={"client_id": client_id, "prompt": workflow},
                headers=self._headers(),
            )
            await self._raise_for_status(response)
            try:
                submitted = response.json()
            except json.JSONDecodeError as exc:
                raise ProviderError(f"ComfyUI returned an invalid /prompt response: {exc}") from exc
            prompt_id = submitted.get("prompt_id") if isinstance(submitted, dict) else None
            if not prompt_id:
                raise ProviderError(f"ComfyUI's /prompt response had no prompt_id: {submitted}")

            yield {"status": "queued", "prompt_id": prompt_id, "warning": warning}

            history_url = self._url(f"/history/{prompt_id}")
            elapsed = 0.0
            entry: dict | None = None
            while entry is None:
                response = await http.get(history_url, headers=self._headers())
                await self._raise_for_status(response)
                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    raise ProviderError(
                        f"ComfyUI returned an invalid /history response: {exc}"
                    ) from exc
                candidate = data.get(prompt_id) if isinstance(data, dict) else None
                if candidate is not None and bool((candidate.get("status") or {}).get("completed")):
                    entry = candidate
                    break
                if elapsed >= poll_timeout:
                    raise ProviderError(
                        f"timed out after {poll_timeout:.0f}s waiting for ComfyUI job {prompt_id}"
                    )
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                yield {"status": "running", "elapsed": elapsed}

            if (entry.get("status") or {}).get("status_str") == "error":
                raise ProviderError(f"ComfyUI job {prompt_id} failed: {entry.get('status')}")

            files = _collect_output_files(entry)
            if not files:
                raise ProviderError(
                    f"ComfyUI job {prompt_id} completed but produced no output files"
                )

            images: list[GeneratedImage] = []
            for file in files:
                response = await http.get(self._view_url(file), headers=self._headers())
                await self._raise_for_status(response)
                content_type = response.headers.get("content-type", "application/octet-stream")
                images.append(
                    GeneratedImage(
                        filename=file.filename,
                        content_type=content_type.split(";")[0].strip(),
                        data=await response.aread(),
                    )
                )

            yield {
                "status": "done",
                "images": images,
                "seed": resolved_seed,
                "width": resolved_width,
                "height": resolved_height,
                "prompt_id": prompt_id,
            }
