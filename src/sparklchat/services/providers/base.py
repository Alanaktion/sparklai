"""Shared plumbing for provider clients.

Clients are constructed from a `ProviderConfig` and optionally accept an
`httpx.AsyncClient`; tests inject one backed by a `MockTransport` so request
shapes can be asserted without network access.
"""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx

from sparklchat.models.provider import ChatRole

DEFAULT_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class ProviderError(Exception):
    """Raised when a provider request fails or returns something unusable."""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider_type: str
    base_url: str
    model: str
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    extra_params: Mapping[str, Any] = field(default_factory=dict)


class BaseClient:
    """HTTP plumbing shared by the concrete clients."""

    def __init__(
        self, config: ProviderConfig, *, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self.config = config
        self._http = http_client

    @property
    def provider_type(self) -> str:
        return self.config.provider_type

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        """Yield the injected client, or a short-lived one we own."""
        if self._http is not None:
            yield self._http
        else:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                yield client

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.config.api_key:
            headers["authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _sampling(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.config.temperature is not None:
            params["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            params["max_tokens"] = self.config.max_tokens
        if self.config.top_p is not None:
            params["top_p"] = self.config.top_p
        return params

    async def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        detail = (await response.aread()).decode("utf-8", "replace").strip()
        raise ProviderError(
            f"{self.provider_type} returned HTTP {response.status_code}: "
            f"{detail[:400] or 'no response body'}"
        )

    async def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as http:
            response = await http.post(url, json=payload, headers=self._headers())
            await self._raise_for_status(response)
            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                raise ProviderError(f"{self.provider_type} returned invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ProviderError(f"{self.provider_type} returned an unexpected payload")
        return data

    async def _stream_sse(self, url: str, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Yield `data:` JSON objects from a `text/event-stream` response."""
        async with (
            self._client() as http,
            http.stream("POST", url, json=payload, headers=self._headers()) as response,
        ):
            await self._raise_for_status(response)
            async for line in response.aiter_lines():
                chunk = line.strip()
                if not chunk or not chunk.startswith("data:"):
                    continue
                data = chunk[len("data:") :].strip()
                if data == "[DONE]":
                    return
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    yield event

    async def _stream_json_lines(
        self, url: str, payload: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield newline-delimited JSON objects (Ollama's streaming format)."""
        async with (
            self._client() as http,
            http.stream("POST", url, json=payload, headers=self._headers()) as response,
        ):
            await self._raise_for_status(response)
            async for line in response.aiter_lines():
                chunk = line.strip()
                if not chunk:
                    continue
                try:
                    event = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    yield event

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        raise NotImplementedError

    def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        raise NotImplementedError
