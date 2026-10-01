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


async def resolve_model(requested: str | None = None, *, trust_requested: bool = False) -> str:
    """Pick the model id to send to the chat backend.

    Normally `requested` must appear in the backend's live `/v1/models` listing, falling back to
    `models[0]` otherwise — this is what lets a stale `chat_model` preference cookie (pointing at
    a model that's no longer loaded) degrade gracefully instead of erroring.

    `trust_requested=True` skips that membership check and returns `requested` as-is. Use it for
    an explicit server-side model configuration (e.g. `settings.translation_model`) rather than a
    user preference: the backend may not list it until it's actually requested (common for
    on-demand/JIT model loading), and silently substituting a different model the admin didn't
    ask for is worse than just sending the configured id straight through.
    """
    normalized = _normalize_model(requested)
    if trust_requested and normalized:
        return normalized

    models = await fetch_models()
    if not models:
        raise RuntimeError(
            "No chat models available from CHAT_URL. Load a model in the backend or set CHAT_MODEL."
        )
    candidate = normalized or _normalize_model(settings.chat_model)
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
    *,
    trust_model: bool = False,
) -> str:
    all_messages: list[dict] = list(messages or [])
    if user_prompt is not None:
        all_messages.append({"role": "user", "content": user_prompt})

    active_model = await resolve_model(model, trust_requested=trust_model)
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

_TRANSLATE_TEXT_PLACEHOLDER = "{text}"


async def translate_to_english(text: str, model: str | None = None) -> str:
    """Used by comments and chat messages.

    Model resolution: the dedicated translation model wins when configured
    (`settings.translation_model`, env `TRANSLATION_MODEL`) and is trusted as-is — it's not
    required to appear in the backend's live `/v1/models` listing, since a dedicated
    translation model is often not loaded until first requested. Otherwise `model` (the
    caller's text-generation default, resolved from the chat-model preference cookie) passes
    through, and `resolve_model()` inside `completion()` finally falls back to
    `settings.chat_model`.

    The system prompt comes from `settings.translation_prompt` (env `TRANSLATION_PROMPT`),
    falling back to the built-in translation prompt when unset. If the prompt contains
    `{text}`, the text is substituted inline and no separate user message is sent — that
    instruction+text template matches what dedicated translation models (e.g. Hy-MT2-1.8B)
    expect.
    """
    source = text.strip()
    if not source:
        return ""

    dedicated_model = _normalize_model(settings.translation_model)
    effective_model = dedicated_model or model
    system_prompt = (settings.translation_prompt or "").strip() or _TRANSLATE_SYSTEM

    if _TRANSLATE_TEXT_PLACEHOLDER in system_prompt:
        messages: list[LlamaMessage] = [
            {
                "role": "system",
                "content": system_prompt.replace(_TRANSLATE_TEXT_PLACEHOLDER, source),
            }
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source},
        ]
    translated = await completion(
        None, messages, model=effective_model, trust_model=bool(dedicated_model)
    )
    return translated.strip()
