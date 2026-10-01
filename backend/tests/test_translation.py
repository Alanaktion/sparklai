"""translate_to_english: dedicated translation model and configurable prompt template.

The chat-model preference cookie (the text-generation default) is passed through as `model`;
TRANSLATION_MODEL overrides it when set, and TRANSLATION_PROMPT's `{text}` placeholder
controls how the text reaches the model.
"""

from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import chat


def _capture_completion(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Patch chat.completion with a fake that records its arguments."""
    captured: dict = {}

    async def fake_completion(user_prompt=None, messages=None, model=None, *, trust_model=False) -> str:
        captured["user_prompt"] = user_prompt
        captured["messages"] = messages
        captured["model"] = model
        captured["trust_model"] = trust_model
        return "  Hello  "

    monkeypatch.setattr(chat, "completion", fake_completion)
    return captured


async def test_translation_model_overrides_chat_default(monkeypatch: pytest.MonkeyPatch):
    captured = _capture_completion(monkeypatch)
    monkeypatch.setattr(settings, "translation_model", "Hy-MT2-1.8B")

    result = await chat.translate_to_english("Hola", model="llama3.1:8b")

    assert result == "Hello"  # whitespace-stripped by translate_to_english
    assert captured["model"] == "Hy-MT2-1.8B"
    # A dedicated translation model is trusted as-is, bypassing the "must appear in the live
    # /v1/models listing" check used for the chat-model preference cookie — otherwise a
    # translation model that isn't loaded yet gets silently dropped in favor of the base model.
    assert captured["trust_model"] is True
    assert captured["user_prompt"] is None
    # Default prompt has no {text} placeholder: system prompt + text as user message.
    assert [(m["role"], m["content"]) for m in captured["messages"]] == [
        ("system", chat._TRANSLATE_SYSTEM),
        ("user", "Hola"),
    ]


async def test_translation_falls_back_to_chat_model_when_unset(monkeypatch: pytest.MonkeyPatch):
    captured = _capture_completion(monkeypatch)
    monkeypatch.setattr(settings, "translation_model", "")

    result = await chat.translate_to_english("Hola", model="llama3.1:8b")

    assert result == "Hello"
    assert captured["model"] == "llama3.1:8b"
    # No dedicated translation model configured: fall back to the normal preference-cookie
    # resolution, which is allowed to substitute a different available model.
    assert captured["trust_model"] is False


async def test_custom_translation_prompt_with_text_placeholder(monkeypatch: pytest.MonkeyPatch):
    captured = _capture_completion(monkeypatch)
    monkeypatch.setattr(settings, "translation_model", "Hy-MT2-1.8B")
    monkeypatch.setattr(
        settings,
        "translation_prompt",
        "Translate the following segment into English, without additional explanation.\n\n{text}",
    )

    await chat.translate_to_english("Hola")

    # {text} inlines the source: a single system message, no separate user message.
    assert [(m["role"], m["content"]) for m in captured["messages"]] == [
        (
            "system",
            "Translate the following segment into English, without additional explanation.\n\nHola",
        )
    ]


async def test_custom_translation_prompt_without_placeholder(monkeypatch: pytest.MonkeyPatch):
    captured = _capture_completion(monkeypatch)
    monkeypatch.setattr(settings, "translation_prompt", "Translate to English, output only.")

    await chat.translate_to_english("Hola")

    assert [(m["role"], m["content"]) for m in captured["messages"]] == [
        ("system", "Translate to English, output only."),
        ("user", "Hola"),
    ]


async def test_translation_empty_text_skips_completion(monkeypatch: pytest.MonkeyPatch):
    captured = _capture_completion(monkeypatch)

    assert await chat.translate_to_english("   ") == ""
    assert captured == {}


async def test_translation_model_used_even_when_backend_does_not_list_it(
    monkeypatch: pytest.MonkeyPatch,
):
    """Regression test: a dedicated translation model that isn't (yet) reported by the chat
    backend's `/v1/models` must still be sent as-is, not silently replaced by whatever
    `resolve_model()` would otherwise pick."""
    monkeypatch.setattr(settings, "translation_model", "Hy-MT2-1.8B")

    async def fake_fetch_models() -> list[str]:
        return ["llama3.1:8b"]  # the translation model is absent from this list

    monkeypatch.setattr(chat, "fetch_models", fake_fetch_models)

    captured_model = {}

    async def fake_create(**kwargs):
        captured_model["model"] = kwargs["model"]
        message = SimpleNamespace(content="Hello", reasoning_content=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(chat._client.chat.completions, "create", fake_create)

    result = await chat.translate_to_english("Hola", model="llama3.1:8b")

    assert result == "Hello"
    assert captured_model["model"] == "Hy-MT2-1.8B"
