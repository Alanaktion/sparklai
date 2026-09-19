"""Typed views of our own namespace inside a card's `extensions`.

The spec leaves `extensions` open so editors never destroy unknown keys, so we
read *our* namespace (`extensions.sparklchat`) leniently: a missing or malformed
block degrades to the defaults rather than making a card unloadable. Nothing here
is ever written back by prompt assembly.

A card opts into voice features like this:

    "extensions": {
      "sparklchat": {
        "tts": {"enabled": true, "voice": "Google UK English Female", "lang": "en-GB"},
        "stt": {"enabled": true, "lang": "en-GB"}
      }
    }

The front end acts on these with the browser's own speech APIs, so no provider
credentials are involved.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

HOOKS_NAMESPACE = "sparklchat"


class SpeechOutput(BaseModel):
    """Text-to-speech preferences."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    voice: str | None = None
    lang: str | None = None
    # Kept inside the ranges the Web Speech API accepts.
    rate: float | None = Field(default=None, ge=0.1, le=10)
    pitch: float | None = Field(default=None, ge=0, le=2)


class SpeechInput(BaseModel):
    """Speech-to-text preferences."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    lang: str | None = None
    continuous: bool = False


class CharacterHooks(BaseModel):
    model_config = ConfigDict(extra="allow")

    tts: SpeechOutput = Field(default_factory=SpeechOutput)
    stt: SpeechInput = Field(default_factory=SpeechInput)


def hooks_from_extensions(extensions: Any) -> CharacterHooks:
    """Read the `sparklchat` namespace, falling back to the defaults."""
    if not isinstance(extensions, dict):
        return CharacterHooks()
    raw = extensions.get(HOOKS_NAMESPACE)
    if not isinstance(raw, dict):
        return CharacterHooks()
    try:
        return CharacterHooks.model_validate(raw)
    except ValidationError:
        return CharacterHooks()


def hooks_from_card_json(card_json: Any) -> CharacterHooks:
    """Read hooks out of a stored card without re-validating the whole thing."""
    if not isinstance(card_json, dict):
        return CharacterHooks()
    data = card_json.get("data")
    extensions = data.get("extensions") if isinstance(data, dict) else None
    return hooks_from_extensions(extensions)
