"""ComfyUI request/response flow for `app/services/sd/client.py`'s `_start_comfy_generation()` —
port of the old SvelteKit-side `src/tests/sd.comfy.test.ts` (deleted in BACKEND_MIGRATION.md's
cleanup pass along with the `$lib/server/sd` module it tested). Nothing under
`test_image_generation_endpoints.py`/`test_image_jobs.py` exercises this deep — they mock
`sd_client.start_generation` itself — so this is the one place the prompt-submission/history-
polling/image-fetch mechanics actually get covered.

Real `httpx.Response` objects stand in for the SD server's replies (constructed directly, not sent
over the network) so `response.is_error`/`.json()`/`.content` all behave exactly like a real
response would, without needing an HTTP mocking library.
"""

import asyncio

import httpx
import pytest

from app.services.sd import client as sd_client
from app.services.sd.types import ImageGenerationRequest


class _FakeHttpClient:
    """Replaces `sd_client._client`: `post`/`get` pop canned `httpx.Response`s off a queue in
    order — an unexpected extra call raises `IndexError`, which is the point. A callable queued
    instead of a `Response` is called fresh every time and never popped, for the timeout test's
    endless "still running" replies (queue it last; nothing should follow it)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def _respond(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self._responses[0]
        if callable(item):
            return item()
        return self._responses.pop(0)

    async def post(self, url, **kwargs):
        return await self._respond("POST", url, **kwargs)

    async def get(self, url, **kwargs):
        return await self._respond("GET", url, **kwargs)


@pytest.fixture(autouse=True)
def _comfy_backend(monkeypatch: pytest.MonkeyPatch):
    """Every test in this file exercises the ComfyUI branch regardless of the real
    `SD_BACKEND` setting `settings` was loaded with."""
    monkeypatch.setattr(sd_client, "backend", "comfyui")
    monkeypatch.setattr(sd_client, "_workflow_cache", {})


def _install(monkeypatch: pytest.MonkeyPatch, *responses) -> _FakeHttpClient:
    fake = _FakeHttpClient(responses)
    monkeypatch.setattr(sd_client, "_client", fake)
    return fake


def _request(**overrides) -> ImageGenerationRequest:
    fields = {"prompt": "test prompt", "width": 640, "height": 768, "image_style": "photo"}
    fields.update(overrides)
    return ImageGenerationRequest(**fields)


async def test_submits_prompt_polls_history_and_fetches_output_image(
    monkeypatch: pytest.MonkeyPatch,
):
    fake = _install(
        monkeypatch,
        httpx.Response(200, json={"prompt_id": "prompt-123"}),
        httpx.Response(
            200,
            json={
                "prompt-123": {
                    "outputs": {
                        "51": {
                            "images": [
                                {"filename": "image_0001.png", "subfolder": "sparklai", "type": "output"}
                            ]
                        }
                    },
                    "status": {"status_str": "success", "completed": True},
                }
            },
        ),
        httpx.Response(200, content=bytes([1, 2, 3, 4])),
    )

    task = await sd_client.start_generation(_request(negative_prompt="test negative"))
    image = await task.wait_for_result()

    assert len(image.data) == 4
    assert image.provider_metadata["promptId"] == "prompt-123"
    assert image.provider_metadata["outputNodeId"] == "51"

    assert len(fake.calls) == 3
    method, url, kwargs = fake.calls[0]
    assert method == "POST"
    assert url.endswith("/prompt")
    assert "prompt" in kwargs["json"]
    assert kwargs["json"]["prompt"]
    assert isinstance(kwargs["json"]["client_id"], str)

    assert fake.calls[1][1].endswith("/history/prompt-123")

    _, view_url, view_kwargs = fake.calls[2]
    assert view_url.endswith("/view")
    assert view_kwargs["params"]["filename"] == "image_0001.png"
    assert view_kwargs["params"]["subfolder"] == "sparklai"
    assert view_kwargs["params"]["type"] == "output"


async def test_supports_direct_history_entry_format_non_keyed_body(
    monkeypatch: pytest.MonkeyPatch,
):
    fake = _install(
        monkeypatch,
        httpx.Response(200, json={"prompt_id": "prompt-direct"}),
        httpx.Response(
            200,
            json={
                "outputs": {
                    "other_node": {
                        "images": [{"filename": "direct.png", "subfolder": "", "type": "output"}]
                    }
                }
            },
        ),
        httpx.Response(200, content=bytes([9, 9, 9])),
    )

    task = await sd_client.start_generation(_request(prompt="direct entry prompt"))
    image = await task.wait_for_result()

    assert len(image.data) == 3
    assert len(fake.calls) == 3


async def test_raises_when_prompt_submission_fails(monkeypatch: pytest.MonkeyPatch):
    _install(monkeypatch, httpx.Response(400, json={"error": "bad request"}))

    with pytest.raises(RuntimeError, match="ComfyUI prompt submission failed with 400"):
        await sd_client.start_generation(_request())


async def test_raises_when_prompt_submission_has_no_prompt_id(monkeypatch: pytest.MonkeyPatch):
    _install(monkeypatch, httpx.Response(200, json={"number": 12}))

    with pytest.raises(RuntimeError, match="ComfyUI did not return a prompt_id"):
        await sd_client.start_generation(_request())


async def test_raises_when_history_reports_error_status(monkeypatch: pytest.MonkeyPatch):
    _install(
        monkeypatch,
        httpx.Response(200, json={"prompt_id": "prompt-error"}),
        httpx.Response(200, json={"prompt-error": {"status": {"status_str": "error"}}}),
    )

    task = await sd_client.start_generation(_request())
    with pytest.raises(RuntimeError, match="ComfyUI workflow execution failed"):
        await task.wait_for_result()


async def test_raises_when_history_never_yields_an_image_before_timeout(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.config import settings

    monkeypatch.setattr(settings, "sd_comfy_timeout_ms", 50)
    monkeypatch.setattr(settings, "sd_comfy_poll_interval_ms", 1)

    still_running = httpx.Response(
        200,
        json={
            "prompt-timeout": {"status": {"status_str": "running", "completed": False}, "outputs": {}}
        },
    )
    fake = _install(
        monkeypatch,
        httpx.Response(200, json={"prompt_id": "prompt-timeout"}),
        lambda: still_running,
    )

    task = await sd_client.start_generation(_request(prompt="timeout prompt"))
    with pytest.raises(RuntimeError, match="ComfyUI workflow timed out after 50ms"):
        await task.wait_for_result()

    assert any(url.endswith("/history/prompt-timeout") for _, url, _ in fake.calls)


async def test_wait_for_result_polls_at_the_configured_interval(monkeypatch: pytest.MonkeyPatch):
    """Not part of the original vitest suite — added since porting the timeout test above made it
    easy to also confirm `sd_comfy_poll_interval_ms` actually throttles the loop rather than
    spinning it hot."""
    from app.config import settings

    monkeypatch.setattr(settings, "sd_comfy_timeout_ms", 1000)
    monkeypatch.setattr(settings, "sd_comfy_poll_interval_ms", 1000)

    sleep_calls = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    running = httpx.Response(
        200, json={"prompt-slow": {"status": {"status_str": "running"}, "outputs": {}}}
    )
    done = httpx.Response(
        200,
        json={
            "prompt-slow": {
                "outputs": {"51": {"images": [{"filename": "f.png", "subfolder": "", "type": "output"}]}}
            }
        },
    )
    _install(
        monkeypatch,
        httpx.Response(200, json={"prompt_id": "prompt-slow"}),
        running,
        done,
        httpx.Response(200, content=b"ok"),
    )

    task = await sd_client.start_generation(_request(prompt="slow prompt"))
    image = await task.wait_for_result()

    assert image.data == b"ok"
    assert sleep_calls == [1.0]
