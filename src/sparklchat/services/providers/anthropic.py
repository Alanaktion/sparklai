"""Anthropic Messages API client."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from sparklchat.services.providers.base import BaseClient, ChatMessage, ProviderError

ANTHROPIC_VERSION = "2023-06-01"
# Anthropic requires `max_tokens`; this is the fallback when none is configured.
DEFAULT_MAX_TOKENS = 4096


class AnthropicClient(BaseClient):
    def _headers(self) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key
        return headers

    def _payload(self, messages: Sequence[ChatMessage], *, stream: bool) -> dict[str, Any]:
        # Anthropic takes the system prompt as a top-level field, not a message.
        system = [message.content for message in messages if message.role == "system"]
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [message.as_dict() for message in messages if message.role != "system"],
            "max_tokens": self.config.max_tokens or DEFAULT_MAX_TOKENS,
            "stream": stream,
        }
        if system:
            payload["system"] = "\n\n".join(system)
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p
        for key, value in self.config.extra_params.items():
            payload.setdefault(key, value)
        return payload

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        data = await self._post_json(
            self._url("/v1/messages"), self._payload(messages, stream=False)
        )
        return _text_from(data)

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        payload = self._payload(messages, stream=True)
        async for event in self._stream_sse(self._url("/v1/messages"), payload):
            event_type = event.get("type")
            if event_type == "content_block_delta":
                text = (event.get("delta") or {}).get("text")
                if text:
                    yield text
            elif event_type == "message_stop":
                return


def _text_from(data: dict[str, Any]) -> str:
    blocks = data.get("content")
    if not isinstance(blocks, list):
        raise ProviderError("anthropic returned an unexpected payload")
    return "".join(
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    )
