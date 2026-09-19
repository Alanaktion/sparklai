"""Provider client request/response handling, exercised without network access.

Each test injects an `httpx.AsyncClient` backed by a `MockTransport`, so the
exact request the client would send is asserted directly.
"""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from sparklchat.services.providers import (
    BaseClient,
    ChatMessage,
    ProviderConfig,
    ProviderError,
    build_client,
)
from sparklchat.services.providers.openai import OpenAIClient

MESSAGES = [
    ChatMessage(role="system", content="be nice"),
    ChatMessage(role="user", content="hi"),
]

Handler = Callable[[httpx.Request], httpx.Response]


def config(**overrides: Any) -> ProviderConfig:
    values: dict[str, Any] = {
        "provider_type": "openai",
        "base_url": "https://api.example/v1",
        "model": "test-model",
        "api_key": "sk-1",
    }
    values.update(overrides)
    return ProviderConfig(**values)


@asynccontextmanager
async def client_for(cfg: ProviderConfig, handler: Handler) -> AsyncIterator[BaseClient]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        yield build_client(cfg, http_client=http)


def test_koboldcpp_and_custom_use_the_openai_client() -> None:
    assert isinstance(build_client(config(provider_type="koboldcpp")), OpenAIClient)
    assert isinstance(build_client(config(provider_type="custom")), OpenAIClient)


def test_unsupported_provider_type_is_rejected() -> None:
    with pytest.raises(ProviderError, match="unsupported provider type"):
        build_client(config(provider_type="mystery"))


async def test_openai_complete_sends_a_chat_completion() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    async with client_for(config(), handler) as client:
        assert await client.complete(MESSAGES) == "hello"

    assert captured["url"] == "https://api.example/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer sk-1"
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["stream"] is False
    assert captured["body"]["messages"] == [
        {"role": "system", "content": "be nice"},
        {"role": "user", "content": "hi"},
    ]


async def test_openai_sampling_fields_win_over_extra_params() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    cfg = config(
        temperature=0.7,
        max_tokens=64,
        top_p=0.9,
        extra_params={"frequency_penalty": 0.5, "model": "ignored", "stream": True},
    )
    async with client_for(cfg, handler) as client:
        await client.complete(MESSAGES)

    body = captured["body"]
    assert body["temperature"] == 0.7
    assert body["max_tokens"] == 64
    assert body["top_p"] == 0.9
    assert body["frequency_penalty"] == 0.5
    # The request envelope is not overridable from extra_params.
    assert body["model"] == "test-model"
    assert body["stream"] is False


async def test_openai_stream_yields_content_deltas() -> None:
    body = "\n".join(
        [
            'data: {"choices":[{"delta":{"content":"Hel"}}]}',
            'data: {"choices":[{"delta":{"content":"lo"}}]}',
            'data: {"choices":[{"delta":{}}]}',
            'data: {"choices":[]}',
            "data: [DONE]",
            "",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    async with client_for(config(), handler) as client:
        chunks = [chunk async for chunk in client.stream(MESSAGES)]

    assert chunks == ["Hel", "lo"]


async def test_openai_reports_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    async with client_for(config(), handler) as client:
        with pytest.raises(ProviderError, match="HTTP 401"):
            await client.complete(MESSAGES)


async def test_openai_reports_unexpected_payloads() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    async with client_for(config(), handler) as client:
        with pytest.raises(ProviderError, match="unexpected payload"):
            await client.complete(MESSAGES)


async def test_anthropic_lifts_system_prompt_and_uses_api_key_header() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hello"}]})

    cfg = config(
        provider_type="anthropic",
        base_url="https://api.anthropic.com",
        api_key="ak-1",
    )
    async with client_for(cfg, handler) as client:
        assert await client.complete(MESSAGES) == "hello"

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "ak-1"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert "authorization" not in captured["headers"]

    body = captured["body"]
    assert body["system"] == "be nice"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    # Anthropic requires max_tokens, so a default is supplied.
    assert body["max_tokens"] == 4096


async def test_anthropic_stream_reads_content_block_deltas() -> None:
    body = "\n".join(
        [
            "event: content_block_delta",
            'data: {"type":"content_block_delta","delta":{"text":"Hi"}}',
            "",
            'data: {"type":"content_block_delta","delta":{"text":"!"}}',
            "",
            'data: {"type":"message_stop"}',
            "",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    async with client_for(config(provider_type="anthropic"), handler) as client:
        chunks = [chunk async for chunk in client.stream(MESSAGES)]

    assert chunks == ["Hi", "!"]


async def test_ollama_uses_options_and_omits_auth_without_a_key() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "hi"}})

    cfg = config(
        provider_type="ollama",
        base_url="http://127.0.0.1:11434",
        api_key=None,
        temperature=0.5,
        max_tokens=128,
        top_p=0.8,
    )
    async with client_for(cfg, handler) as client:
        assert await client.complete(MESSAGES) == "hi"

    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert "authorization" not in captured["headers"]
    assert captured["body"]["options"] == {
        "temperature": 0.5,
        "top_p": 0.8,
        "num_predict": 128,
    }


async def test_ollama_stream_reads_newline_delimited_json() -> None:
    body = "\n".join(
        [
            '{"message":{"content":"Hel"},"done":false}',
            '{"message":{"content":"lo"},"done":false}',
            '{"message":{"content":""},"done":true}',
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with client_for(config(provider_type="ollama"), handler) as client:
        chunks = [chunk async for chunk in client.stream(MESSAGES)]

    assert chunks == ["Hel", "lo"]
