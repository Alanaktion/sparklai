"""ComfyUI provider CRUD and the `/sessions/{id}/images/stream` generation flow."""

from collections.abc import AsyncIterator
from typing import Any

from httpx import AsyncClient

from sparklchat.services.providers import ProviderError
from sparklchat.services.providers.comfyui import GeneratedImage


class StubImageClient:
    """Stands in for `ComfyUIClient` so tests don't need a real ComfyUI server."""

    def __init__(
        self,
        *,
        images: list[GeneratedImage] | None = None,
        width: int = 512,
        height: int = 512,
        error: str | None = None,
    ) -> None:
        self.prompts: list[str] = []
        self._images = (
            images
            if images is not None
            else [GeneratedImage(filename="out.png", content_type="image/png", data=b"PNGDATA")]
        )
        self._width = width
        self._height = height
        self._error = error

    async def generate(self, prompt: str, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        self.prompts.append(prompt)
        yield {"status": "queued", "prompt_id": "job-1", "warning": None}
        if self._error:
            raise ProviderError(self._error)
        yield {"status": "running", "elapsed": 2.0}
        yield {
            "status": "done",
            "images": self._images,
            "seed": 1,
            "width": self._width,
            "height": self._height,
            "prompt_id": "job-1",
        }


class StubTextClient:
    """Stands in for the session's text provider, for automatic-prompt tests."""

    def __init__(
        self, *, reply: str = "a cat astronaut, digital art, vivid colors", error: str | None = None
    ) -> None:
        self.calls: list[list] = []
        self._reply = reply
        self._error = error

    async def complete(self, messages):
        self.calls.append(list(messages))
        if self._error:
            raise ProviderError(self._error)
        return self._reply


def install_stub(monkeypatch, *, text: StubTextClient | None = None, **kwargs) -> StubImageClient:
    """Replace the chat router's client factory: a `comfyui` provider gets the
    image stub, anything else (the session's text provider, used to derive an
    automatic prompt) gets `text`."""
    image = StubImageClient(**kwargs)
    text_client = text or StubTextClient()
    monkeypatch.setattr(
        "sparklchat.api.chat.build_client",
        lambda config: image if config.provider_type == "comfyui" else text_client,
    )
    return image


async def make_text_provider(client: AsyncClient, headers: dict[str, str], **overrides) -> dict:
    body: dict[str, Any] = {
        "name": "Text provider",
        "provider_type": "openai",
        "base_url": "https://api.example/v1",
        "api_key": "sk-test",
        "model": "test-model",
    }
    body.update(overrides)
    response = await client.post("/api/providers", json=body, headers=headers)
    assert response.status_code == 201, response.text
    provider = response.json()
    await client.patch(
        "/api/settings", json={"default_provider_id": provider["id"]}, headers=headers
    )
    return provider


async def make_comfyui_provider(client: AsyncClient, headers: dict[str, str], **overrides) -> dict:
    body: dict[str, Any] = {
        "name": "Local ComfyUI",
        "provider_type": "comfyui",
        "base_url": "http://127.0.0.1:8188",
        "model": "",
        "extra_params": {"workflow": "sdxl", "width": 512, "height": 512},
    }
    body.update(overrides)
    response = await client.post("/api/providers", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def make_character(client: AsyncClient, headers: dict[str, str], card: dict) -> dict:
    response = await client.post("/api/characters", json=card, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def make_session(client: AsyncClient, headers: dict[str, str], character_id: int) -> dict:
    response = await client.post(
        f"/api/characters/{character_id}/sessions", json={}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_default_base_url_for_comfyui() -> None:
    from sparklchat.models.provider import default_base_url

    assert default_base_url("comfyui") == "http://127.0.0.1:8188"


async def test_create_comfyui_provider(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    provider = await make_comfyui_provider(client, auth_headers)
    assert provider["provider_type"] == "comfyui"
    assert provider["extra_params"]["workflow"] == "sdxl"


async def test_test_endpoint_uses_the_comfyui_connectivity_check(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    provider = await make_comfyui_provider(client, auth_headers)

    class Reachable:
        async def complete(self, messages):
            return "ComfyUI reachable (version 0.3.1)"

    monkeypatch.setattr("sparklchat.api.providers.build_client", lambda config: Reachable())
    response = await client.post(f"/api/providers/{provider['id']}/test", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "ComfyUI reachable" in body["reply"]


async def test_stream_image_generates_and_attaches_to_a_message(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    provider = await make_comfyui_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    stub = install_stub(monkeypatch)

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/images/stream",
        json={"provider_id": provider["id"], "prompt": "a cat astronaut"},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert stub.prompts == ["a cat astronaut"]
    assert "event: status" in payload
    assert "event: message" in payload
    assert "event: done" in payload
    assert "event: error" not in payload

    messages = (
        await client.get(f"/api/sessions/{session['id']}/messages", headers=auth_headers)
    ).json()
    image_message = next(message for message in messages if message["images"])
    assert image_message["content"] == "a cat astronaut"
    assert image_message["images"] == [{"index": 0, "width": 512, "height": 512}]

    image_response = await client.get(
        f"/api/sessions/{session['id']}/messages/{image_message['id']}/images/0",
        headers=auth_headers,
    )
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"
    assert image_response.content == b"PNGDATA"

    missing = await client.get(
        f"/api/sessions/{session['id']}/messages/{image_message['id']}/images/1",
        headers=auth_headers,
    )
    assert missing.status_code == 404


async def test_stream_image_reports_provider_errors(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    provider = await make_comfyui_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, error="ComfyUI is unreachable")

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/images/stream",
        json={"provider_id": provider["id"], "prompt": "x"},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: error" in payload
    assert "ComfyUI is unreachable" in payload
    assert "event: done" in payload

    messages = (
        await client.get(f"/api/sessions/{session['id']}/messages", headers=auth_headers)
    ).json()
    assert not any(message["images"] for message in messages)


async def test_stream_image_rejects_a_non_comfyui_provider(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    response = await client.post(
        "/api/providers",
        json={
            "name": "Text provider",
            "provider_type": "openai",
            "base_url": "https://api.example/v1",
            "model": "gpt-4",
        },
        headers=auth_headers,
    )
    provider = response.json()
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/images/stream",
        json={"provider_id": provider["id"], "prompt": "x"},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: error" in payload
    assert "not a ComfyUI provider" in payload


async def test_deleting_a_message_removes_its_generated_image_file(
    client: AsyncClient, engine, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    from sparklchat.services.generated_images import generated_image_file

    provider = await make_comfyui_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch)

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/images/stream",
        json={"provider_id": provider["id"], "prompt": "x"},
        headers=auth_headers,
    ):
        pass

    messages = (
        await client.get(f"/api/sessions/{session['id']}/messages", headers=auth_headers)
    ).json()
    image_message = next(message for message in messages if message["images"])

    # Reach past the API to find the file the message points at.
    from sparklchat.db import create_session
    from sparklchat.models.chat import Message

    async with create_session(engine) as db:
        row = await db.get(Message, image_message["id"])
        path = generated_image_file(row.meta["images"][0]["path"])
    assert path.is_file()

    delete_response = await client.delete(
        f"/api/sessions/{session['id']}/messages/{image_message['id']}", headers=auth_headers
    )
    assert delete_response.status_code == 204
    assert not path.is_file()


async def test_stream_image_writes_a_prompt_automatically_when_none_given(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_text_provider(client, auth_headers)
    provider = await make_comfyui_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    text = StubTextClient(reply="a cat astronaut, digital art, vivid colors")
    install_stub(monkeypatch, text=text)

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/images/stream",
        json={"provider_id": provider["id"]},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: status" in payload
    assert "writing_prompt" in payload
    assert "a cat astronaut, digital art, vivid colors" in payload
    assert "event: message" in payload
    assert "event: done" in payload

    # The derived prompt reached the text provider with some conversation context.
    assert text.calls, "expected the text provider to be asked for a prompt"
    context = text.calls[0]
    assert any(message.role == "system" for message in context)
    assert any(message.role == "assistant" for message in context)

    messages = (
        await client.get(f"/api/sessions/{session['id']}/messages", headers=auth_headers)
    ).json()
    image_message = next(message for message in messages if message["images"])
    assert image_message["content"] == "a cat astronaut, digital art, vivid colors"


async def test_stream_image_auto_prompt_requires_a_text_provider(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    # No text provider configured, only the comfyui one.
    provider = await make_comfyui_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch)

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/images/stream",
        json={"provider_id": provider["id"], "prompt": ""},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: error" in payload
    assert "No provider configured" in payload
    assert "event: done" in payload

    messages = (
        await client.get(f"/api/sessions/{session['id']}/messages", headers=auth_headers)
    ).json()
    assert not any(message["images"] for message in messages)


async def test_stream_image_reports_auto_prompt_failures(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    await make_text_provider(client, auth_headers)
    provider = await make_comfyui_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch, text=StubTextClient(error="the model is overloaded"))

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/images/stream",
        json={"provider_id": provider["id"]},
        headers=auth_headers,
    ) as response:
        payload = "".join([chunk async for chunk in response.aiter_text()])

    assert "event: error" in payload
    assert "the model is overloaded" in payload
    assert "event: done" in payload


async def test_branching_duplicates_generated_image_files(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict, monkeypatch
) -> None:
    """A branch's image message must point at its own file, not the original's,
    so deleting one session's message never deletes the other's picture."""
    provider = await make_comfyui_provider(client, auth_headers)
    character = await make_character(client, auth_headers, v2_card)
    session = await make_session(client, auth_headers, character["id"])
    install_stub(monkeypatch)

    async with client.stream(
        "POST",
        f"/api/sessions/{session['id']}/images/stream",
        json={"provider_id": provider["id"], "prompt": "a cat astronaut"},
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        [_ async for _ in response.aiter_text()]

    image_message = next(
        message
        for message in (
            await client.get(f"/api/sessions/{session['id']}/messages", headers=auth_headers)
        ).json()
        if message["images"]
    )

    branch = (
        await client.post(
            f"/api/sessions/{session['id']}/branch", json={}, headers=auth_headers
        )
    ).json()
    branch_image_message = next(message for message in branch["messages"] if message["images"])

    branch_image = await client.get(
        f"/api/sessions/{branch['id']}/messages/{branch_image_message['id']}/images/0",
        headers=auth_headers,
    )
    assert branch_image.status_code == 200
    assert branch_image.content == b"PNGDATA"

    # Deleting the branch's copy must leave the original's file in place.
    await client.delete(
        f"/api/sessions/{branch['id']}/messages/{branch_image_message['id']}",
        headers=auth_headers,
    )
    original_image = await client.get(
        f"/api/sessions/{session['id']}/messages/{image_message['id']}/images/0",
        headers=auth_headers,
    )
    assert original_image.status_code == 200
    assert original_image.content == b"PNGDATA"
