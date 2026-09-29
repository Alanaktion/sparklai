"""translate_to_english: dedicated translation model and configurable prompt template.

The chat-model preference cookie (the text-generation default) is passed through as `model`;
TRANSLATION_MODEL overrides it when set, and TRANSLATION_PROMPT's `{text}` placeholder
controls how the text reaches the model.
"""

import pytest

from app.config import settings
from app.services import chat


def _capture_completion(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Patch chat.completion with a fake that records its arguments."""
    captured: dict = {}

    async def fake_completion(user_prompt=None, messages=None, model=None) -> str:
        captured["user_prompt"] = user_prompt
        captured["messages"] = messages
        captured["model"] = model
        return "  Hello  "

    monkeypatch.setattr(chat, "completion", fake_completion)
    return captured


async def test_translation_model_overrides_chat_default(monkeypatch: pytest.MonkeyPatch):
    captured = _capture_completion(monkeypatch)
    monkeypatch.setattr(settings, "translation_model", "Hy-MT2-1.8B")

    result = await chat.translate_to_english("Hola", model="llama3.1:8b")

    assert result == "Hello"  # whitespace-stripped by translate_to_english
    assert captured["model"] == "Hy-MT2-1.8B"
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
