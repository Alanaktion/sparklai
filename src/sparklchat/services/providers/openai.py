"""OpenAI-compatible chat completions client.

Serves OpenAI, OpenRouter, LM Studio, vLLM, KoboldCpp's OpenAI-compatible
endpoint, and anything else exposing `POST /chat/completions`.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Any

from sparklchat.services.providers.base import BaseClient, ChatMessage, ProviderError


class OpenAIClient(BaseClient):
    def _payload(self, messages: Sequence[ChatMessage], *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [message.as_dict() for message in messages],
            "stream": stream,
            **self._sampling(),
        }
        # `extra_params` extends the request with provider-specific fields; the
        # dedicated columns win when both set the same key.
        for key, value in self.config.extra_params.items():
            payload.setdefault(key, value)
        return payload

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        data = await self._post_json(
            self._url("/chat/completions"), self._payload(messages, stream=False)
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"{self.provider_type} returned an unexpected payload: {exc}"
            ) from exc
        return content or ""

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        payload = self._payload(messages, stream=True)
        async for event in self._stream_sse(self._url("/chat/completions"), payload):
            choices = event.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            text = delta.get("content")
            if text:
                yield text
