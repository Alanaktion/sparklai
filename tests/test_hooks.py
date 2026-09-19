"""TTS/STT hooks read from a card's `extensions.sparklchat` (M8)."""

import copy

from httpx import AsyncClient

from sparklchat.models.card import TavernCardV2
from sparklchat.models.hooks import CharacterHooks, hooks_from_extensions
from sparklchat.services.prompts import PromptContext, build_prompt

EXAMPLE = {
    "tts": {"enabled": True, "voice": "Google UK English Female", "lang": "en-GB", "rate": 1.2},
    "stt": {"enabled": True, "lang": "en-GB", "continuous": True},
}


def extensions(**namespace) -> dict:
    return {"sparklchat": namespace} if namespace else {}


def test_defaults_when_no_namespace_is_declared() -> None:
    assert hooks_from_extensions({}) == CharacterHooks()
    assert hooks_from_extensions(None) == CharacterHooks()
    assert hooks_from_extensions({"other_extension": {"tts": {"enabled": True}}}) == (
        CharacterHooks()
    )


def test_reads_the_declared_hooks() -> None:
    hooks = hooks_from_extensions(extensions(**EXAMPLE))
    assert hooks.tts.enabled is True
    assert hooks.tts.voice == "Google UK English Female"
    assert hooks.tts.rate == 1.2
    assert hooks.stt.enabled is True
    assert hooks.stt.lang == "en-GB"
    assert hooks.stt.continuous is True


def test_unknown_keys_inside_the_namespace_are_kept() -> None:
    hooks = hooks_from_extensions({"sparklchat": {"tts": {"voice_id": "abc123"}}})
    assert hooks.tts.enabled is False
    assert hooks.tts.model_extra == {"voice_id": "abc123"}


def test_a_malformed_namespace_degrades_to_the_defaults() -> None:
    assert hooks_from_extensions({"sparklchat": "not-an-object"}) == CharacterHooks()
    # An out-of-range rate would make the Web Speech API throw, so it is rejected.
    assert hooks_from_extensions(extensions(tts={"enabled": True, "rate": 999})) == CharacterHooks()


def text_card(**extensions_kwargs) -> dict:
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "Voicey",
            "description": "Has a voice.",
            "first_mes": "Hi!",
            "mes_example": "",
            "extensions": extensions(**extensions_kwargs),
        },
    }


async def test_character_detail_exposes_the_hooks(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post("/api/characters", json=text_card(**EXAMPLE), headers=auth_headers)
    assert created.status_code == 201, created.text
    hooks = created.json()["hooks"]
    assert hooks["tts"]["enabled"] is True
    assert hooks["tts"]["voice"] == "Google UK English Female"
    assert hooks["stt"]["continuous"] is True

    fetched = await client.get(f"/api/characters/{created.json()['id']}", headers=auth_headers)
    assert fetched.json()["hooks"] == hooks


async def test_character_detail_defaults_the_hooks(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post("/api/characters", json=text_card(), headers=auth_headers)
    assert created.json()["hooks"] == {
        "tts": {"enabled": False, "voice": None, "lang": None, "rate": None, "pitch": None},
        "stt": {"enabled": False, "lang": None, "continuous": False},
    }


async def test_hooks_do_not_disturb_the_card_round_trip(
    client: AsyncClient, auth_headers: dict[str, str], v2_card: dict
) -> None:
    card = copy.deepcopy(v2_card)
    card["data"]["extensions"]["sparklchat"] = copy.deepcopy(EXAMPLE)

    created = await client.post("/api/characters", json=card, headers=auth_headers)
    assert created.status_code == 201, created.text
    assert created.json()["card"] == card

    exported = await client.get(
        f"/api/characters/{created.json()['id']}/export", headers=auth_headers
    )
    assert exported.json() == card
    assert TavernCardV2.model_validate(exported.json()).data.extensions["sparklchat"] == EXAMPLE


def test_hooks_are_never_injected_into_prompts() -> None:
    card = TavernCardV2.model_validate(text_card(**EXAMPLE))
    prompt = build_prompt(card, [], context=PromptContext())
    assert "Google UK English Female" not in prompt[0].content
