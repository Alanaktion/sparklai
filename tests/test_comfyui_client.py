"""ComfyUI client: workflow resolution, submit/poll/download, and error paths.

Exercised without network access via an injected `httpx.AsyncClient` backed by
a `MockTransport`, matching the pattern in `test_provider_clients.py`.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from sparklchat.services.providers import ProviderConfig, ProviderError, build_client
from sparklchat.services.providers.comfyui import ComfyUIClient
from sparklchat.services.providers.comfyui_workflows import WORKFLOW_TEMPLATES

Handler = Callable[[httpx.Request], httpx.Response]


def config(**overrides: Any) -> ProviderConfig:
    values: dict[str, Any] = {
        "provider_type": "comfyui",
        "base_url": "http://comfy.example",
        "model": "",
    }
    values.update(overrides)
    return ProviderConfig(**values)


@asynccontextmanager
async def client_for(cfg: ProviderConfig, handler: Handler) -> AsyncIterator[ComfyUIClient]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = build_client(cfg, http_client=http)
        assert isinstance(client, ComfyUIClient)
        yield client


def test_build_client_resolves_comfyui_type() -> None:
    assert isinstance(build_client(config()), ComfyUIClient)


async def test_complete_is_a_connectivity_check() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/system_stats"
        return httpx.Response(200, json={"system": {"comfyui_version": "0.3.1"}})

    async with client_for(config(), handler) as client:
        reply = await client.complete([])

    assert reply == "ComfyUI reachable (version 0.3.1)"


async def test_generate_submits_polls_and_downloads(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("sparklchat.services.providers.comfyui.asyncio.sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "job-1"})
        if request.url.path == "/history/job-1":
            # Not completed on the first poll, completed on the second.
            if calls.count("/history/job-1") == 1:
                return httpx.Response(200, json={"job-1": {"status": {"completed": False}}})
            return httpx.Response(
                200,
                json={
                    "job-1": {
                        "status": {"completed": True, "status_str": "success"},
                        "outputs": {
                            "51": {
                                "images": [
                                    {"filename": "out.png", "subfolder": "", "type": "output"}
                                ]
                            }
                        },
                    }
                },
            )
        if request.url.path == "/view":
            assert request.url.params["filename"] == "out.png"
            return httpx.Response(200, content=b"PNGDATA", headers={"content-type": "image/png"})
        raise AssertionError(f"unexpected request to {request.url}")

    cfg = config(extra_params={"workflow": "sdxl", "width": 512, "height": 512})
    async with client_for(cfg, handler) as client:
        events = [event async for event in client.generate("a cat", seed=42)]

    statuses = [event["status"] for event in events]
    assert statuses == ["queued", "running", "done"]

    done = events[-1]
    assert done["width"] == 512
    assert done["height"] == 512
    assert done["seed"] == 42
    assert len(done["images"]) == 1
    image = done["images"][0]
    assert image.filename == "out.png"
    assert image.content_type == "image/png"
    assert image.data == b"PNGDATA"


async def test_generate_fills_in_the_workflow_placeholders() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            import json

            captured["workflow"] = json.loads(request.content)["prompt"]
            return httpx.Response(200, json={"prompt_id": "job-1"})
        if request.url.path == "/history/job-1":
            return httpx.Response(
                200,
                json={
                    "job-1": {
                        "status": {"completed": True},
                        "outputs": {
                            "11": {
                                "images": [{"filename": "a.png", "subfolder": "", "type": "output"}]
                            }
                        },
                    }
                },
            )
        return httpx.Response(200, content=b"x", headers={"content-type": "image/png"})

    cfg = config(model="my-checkpoint.safetensors", extra_params={"workflow": "sdxl"})
    async with client_for(cfg, handler) as client:
        [event async for event in client.generate("a dog", negative_prompt="blurry")]

    workflow = captured["workflow"]
    assert workflow["6"]["inputs"]["text"] == "a dog"
    assert workflow["7"]["inputs"]["text"] == "blurry"
    assert workflow["4"]["inputs"]["ckpt_name"] == "my-checkpoint.safetensors"
    assert workflow["5"]["inputs"]["width"] == 1024  # DEFAULT_WIDTH, not overridden
    # No placeholder survives substitution.
    assert "__" not in str(workflow)


async def test_generate_rejects_unknown_workflow() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not make a request")

    cfg = config(extra_params={"workflow": "does-not-exist"})
    async with client_for(cfg, handler) as client:
        with pytest.raises(ProviderError, match="unknown ComfyUI workflow"):
            [event async for event in client.generate("x")]


async def test_generate_custom_workflow_requires_workflow_json() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not make a request")

    cfg = config(extra_params={"workflow": "custom"})
    async with client_for(cfg, handler) as client:
        with pytest.raises(ProviderError, match="workflow_json"):
            [event async for event in client.generate("x")]


async def test_generate_custom_workflow_uses_the_stored_template() -> None:
    template = {
        "1": {"inputs": {"text": "__POSITIVE_PROMPT__"}, "class_type": "CLIPTextEncode"},
        "2": {"inputs": {"images": ["1", 0]}, "class_type": "SaveImage"},
    }
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            import json

            captured["workflow"] = json.loads(request.content)["prompt"]
            return httpx.Response(200, json={"prompt_id": "job-1"})
        if request.url.path == "/history/job-1":
            return httpx.Response(
                200,
                json={
                    "job-1": {
                        "status": {"completed": True},
                        "outputs": {
                            "2": {
                                "images": [{"filename": "a.png", "subfolder": "", "type": "output"}]
                            }
                        },
                    }
                },
            )
        return httpx.Response(200, content=b"x", headers={"content-type": "image/png"})

    cfg = config(extra_params={"workflow": "custom", "workflow_json": template})
    async with client_for(cfg, handler) as client:
        [event async for event in client.generate("hi")]

    assert captured["workflow"]["1"]["inputs"]["text"] == "hi"


async def test_generate_reports_a_failed_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "job-1"})
        return httpx.Response(
            200,
            json={"job-1": {"status": {"completed": True, "status_str": "error"}}},
        )

    cfg = config(extra_params={"workflow": "sdxl"})
    async with client_for(cfg, handler) as client:
        with pytest.raises(ProviderError, match="job-1"):
            [event async for event in client.generate("x")]


async def test_generate_rejects_a_submission_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad prompt"})

    cfg = config(extra_params={"workflow": "sdxl"})
    async with client_for(cfg, handler) as client:
        with pytest.raises(ProviderError, match="HTTP 400"):
            [event async for event in client.generate("x")]


async def test_sends_api_key_as_x_api_key_header() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["x-api-key"] = request.headers.get("x-api-key", "")
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"system": {}})

    cfg = config(api_key="secret-key")
    async with client_for(cfg, handler) as client:
        await client.complete([])

    assert captured["x-api-key"] == "secret-key"


def test_bundled_workflow_names_match_the_templates() -> None:
    from sparklchat.services.providers.comfyui_workflows import WORKFLOW_NAMES

    assert set(WORKFLOW_NAMES) == set(WORKFLOW_TEMPLATES)
