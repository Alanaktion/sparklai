"""LLM chat client.

The requested model is resolved fresh per call from an explicit parameter, falling back to
`settings.chat_model` — a pure function of its inputs, not shared process state. There is
deliberately no module-level "current model" global that concurrent requests could race each
other to mutate.
"""

import json
import re
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


def _message_text(message) -> str:
    """Some OpenAI-compatible backends (LM Studio, vLLM) route a reasoning/"thinking" model's
    entire answer through a non-standard `reasoning_content` field and leave `content` empty —
    even for a structured `response_format` request where the schema was actually satisfied.
    Falling back to it here (rather than only in the final printed text) is what makes
    `schema_completion`'s `json.loads()` below see real JSON instead of an empty string."""
    content = message.content
    if content:
        return content
    return getattr(message, "reasoning_content", None) or ""


# Raw ASCII control characters (other than tab/newline/CR, which are legitimate in prose) have no
# business appearing in generated text. Seen in practice: a local inference backend garbling an
# accented character into a couple of stray control bytes under strict JSON-schema-constrained
# decoding (e.g. "BL\x06H\x05AJ" instead of "BLÅHAJ") — a backend-side sampler artifact we can't
# fix at the source, but shouldn't let leak into the DB/UI as literal control characters either
# (renders as "Invalid Date"-style mojibake, or worse, in various contexts).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _normalize_llm_output(value):
    if isinstance(value, str):
        marker = "</think>"
        if marker in value:
            return _normalize_llm_output(value[value.index(marker) + len(marker) :])
        cleaned = value.replace("\\\\n", "\n").replace("\\n", "\n").replace('\\"', '"')
        return _CONTROL_CHARS_RE.sub("", cleaned)
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
    raw_text = _message_text(response.choices[0].message)
    if "</think>" in raw_text:
        raw_text = raw_text[raw_text.index("</think>") + len("</think>") :].strip()
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Chat model {active_model!r} returned no parseable JSON for the {schema_name!r} "
            "schema (empty content, and no usable reasoning_content fallback)"
        ) from exc
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
    return _normalize_llm_output(_message_text(response.choices[0].message))


_TRANSLATE_SYSTEM = (
    "You are a translation engine. Translate the user text into natural English. "
    "If the text is already English, return it unchanged. Return only translated text and no "
    "other commentary."
)


async def translate_to_english(text: str, model: str | None = None) -> str:
    """Used by comments and chat messages."""
    source = text.strip()
    if not source:
        return ""

    messages: list[LlamaMessage] = [
        {"role": "system", "content": _TRANSLATE_SYSTEM},
        {"role": "user", "content": source},
    ]
    translated = await completion(None, messages, model=model)
    return translated.strip()
