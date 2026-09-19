"""Ollama native chat API client (`POST /api/chat`)."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from sparklchat.services.providers.base import BaseClient, ChatMessage, ProviderError


class OllamaClient(BaseClient):
    def _payload(self, messages: Sequence[ChatMessage], *, stream: bool) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if self.config.temperature is not None:
            options["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            options["top_p"] = self.config.top_p
        # Ollama spells the output limit `num_predict`.
        if self.config.max_tokens is not None:
            options["num_predict"] = self.config.max_tokens

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [message.as_dict() for message in messages],
            "stream": stream,
            "options": options,
        }
        for key, value in self.config.extra_params.items():
            if key == "options" and isinstance(value, dict):
                payload["options"] = {**options, **value}
            else:
                payload.setdefault(key, value)
        return payload

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        data = await self._post_json(self._url("/api/chat"), self._payload(messages, stream=False))
        return _text_from(data)

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        payload = self._payload(messages, stream=True)
        async for event in self._stream_json_lines(self._url("/api/chat"), payload):
            text = (event.get("message") or {}).get("content")
            if text:
                yield text
            if event.get("done"):
                return


def _text_from(data: dict[str, Any]) -> str:
    message = data.get("message")
    if not isinstance(message, dict):
        raise ProviderError("ollama returned an unexpected payload")
    return message.get("content") or ""
