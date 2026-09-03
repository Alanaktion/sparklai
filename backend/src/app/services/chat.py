"""LLM chat client, ported from `src/lib/server/chat/index.ts`.

Unlike the original, there is no module-level `model` global that every request mutates
(`hooks.server.ts` called `initChatModel()` on every single request, racing concurrent creators
against each other). The requested model is instead resolved fresh per call from an explicit
parameter, falling back to `settings.chat_model` — a pure function of its inputs, not shared
process state.
"""

import json
from typing import Literal, TypedDict

from openai import AsyncOpenAI

from app.config import settings
from app.services.chat_prompts import POST_IMAGE_SYSTEM, POST_SYSTEM, USER_SYSTEM
from app.services.schema_loader import load_schema

_TEMPERATURE = 0.7

_client = AsyncOpenAI(api_key=settings.chat_api_key or "no-key", base_url=settings.chat_url)

SchemaName = Literal["post", "user", "post_image"]

_SCHEMAS: dict[SchemaName, tuple[dict, str]] = {
    "post": (load_schema("post.schema.json"), POST_SYSTEM),
    "user": (load_schema("user.schema.json"), USER_SYSTEM),
    "post_image": (load_schema("post_image.schema.json"), POST_IMAGE_SYSTEM),
}


class LlamaMessage(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str


def _normalize_model(value: str | None) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        return ""
    if (trimmed.startswith('"') and trimmed.endswith('"')) or (
        trimmed.startswith("'") and trimmed.endswith("'")
    ):
        return trimmed[1:-1].strip()
    return trimmed


def _normalize_llm_output(value):
    if isinstance(value, str):
        marker = "</think>"
        if marker in value:
            return _normalize_llm_output(value[value.index(marker) + len(marker) :])
        return value.replace("\\\\n", "\n").replace("\\n", "\n").replace('\\"', '"')
    if isinstance(value, list):
        return [_normalize_llm_output(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_llm_output(item) for key, item in value.items()}
    return value


async def fetch_models() -> list[str]:
    response = await _client.models.list()
    return [m.id for m in response.data]


async def resolve_model(requested: str | None = None) -> str:
    models = await fetch_models()
    if not models:
        raise RuntimeError(
            "No chat models available from CHAT_URL. Load a model in the backend or set CHAT_MODEL."
        )
    candidate = _normalize_model(requested) or _normalize_model(settings.chat_model)
    if candidate and candidate in models:
        return candidate
    return models[0]


async def schema_completion(
    schema_name: SchemaName,
    user_prompt: str | None = None,
    messages: list[LlamaMessage] | None = None,
    model: str | None = None,
):
    schema, system_text = _SCHEMAS[schema_name]
    all_messages: list[dict] = [{"role": "system", "content": system_text}, *(messages or [])]
    if user_prompt is not None:
        all_messages.append({"role": "user", "content": user_prompt})

    active_model = await resolve_model(model)
    response = await _client.chat.completions.create(
        model=active_model,
        messages=all_messages,
        temperature=_TEMPERATURE,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
    )
    parsed = json.loads(response.choices[0].message.content)
    return _normalize_llm_output(parsed)


async def completion(
    user_prompt: str | None = None,
    messages: list[LlamaMessage] | None = None,
    model: str | None = None,
) -> str:
    all_messages: list[dict] = list(messages or [])
    if user_prompt is not None:
        all_messages.append({"role": "user", "content": user_prompt})

    active_model = await resolve_model(model)
    response = await _client.chat.completions.create(
        model=active_model,
        messages=all_messages,
        temperature=_TEMPERATURE,
    )
    return _normalize_llm_output(response.choices[0].message.content)


_TRANSLATE_SYSTEM = (
    "You are a translation engine. Translate the user text into natural English. "
    "If the text is already English, return it unchanged. Return only translated text and no "
    "other commentary."
)


async def translate_to_english(text: str, model: str | None = None) -> str:
    """Port of `src/lib/server/chat/translate.ts`. Used by comments and chat messages."""
    source = text.strip()
    if not source:
        return ""

    messages: list[LlamaMessage] = [
        {"role": "system", "content": _TRANSLATE_SYSTEM},
        {"role": "user", "content": source},
    ]
    translated = await completion(None, messages, model=model)
    return translated.strip()
