"""Character Card V3 parsing, V2/V3 conversion, and the V3 helper functions."""

import copy

import pytest

from sparklchat.models.card import CharacterBook, TavernCardV2, TavernCardV3
from sparklchat.services.cards import (
    CardError,
    card_assets,
    card_group_greetings,
    card_icon,
    card_nickname,
    card_user_icon,
    creator_notes_for,
    detect_format,
    dump_card,
    dump_lorebook,
    dump_v1,
    dump_v2,
    dump_v3,
    load_card,
    parse_card,
    parse_lorebook,
    spec_warnings,
    stamp_creation,
    stamp_modification,
    to_v2,
    to_v3,
)


def entry_of(card) -> object:
    return card.data.character_book.entries[0]


def test_detects_v3(v3_card: dict) -> None:
    assert detect_format(v3_card) == "v3"


def test_parses_every_v3_field(v3_card: dict) -> None:
    card, source = parse_card(v3_card)

    assert source == "v3"
    assert isinstance(card, TavernCardV3)
    assert card.spec == "chara_card_v3"
    assert card.spec_version == "3.0"
    assert card.data.nickname == "Haru"
    assert card.data.group_only_greetings == ["Everyone, listen up!"]
    assert card.data.source == ["example-id", "https://example.com/haruhi.png"]
    assert card.data.creator_notes_multilingual == {
        "en": "English notes.",
        "ja": "Japanese notes.",
    }
    assert card.data.creation_date == 1700000000
    assert card.data.modification_date == 1700000100
    assert [asset.type for asset in card.data.assets or []] == ["icon", "user_icon"]
    assert card.data.assets[0].uri == "embeded://assets/icon/images/main.png"
    assert entry_of(card).use_regex is True
    assert entry_of(card).id == "brigade-lore"


def test_v3_round_trip_is_stable(v3_card: dict) -> None:
    first = dump_v3(parse_card(v3_card)[0])
    second = dump_v3(parse_card(first)[0])
    assert first == second


def test_v3_unknown_keys_survive(v3_card: dict) -> None:
    raw = copy.deepcopy(v3_card)
    raw["data"]["future_field"] = {"custom": True}
    raw["data"]["character_book"]["entries"][0]["future_entry_key"] = 7

    exported = dump_v3(parse_card(raw)[0])
    assert exported["data"]["future_field"] == {"custom": True}
    assert exported["data"]["character_book"]["entries"][0]["future_entry_key"] == 7


def test_v3_export_to_v2_drops_the_v3_only_fields(v3_card: dict) -> None:
    exported = dump_v2(parse_card(v3_card)[0])
    data = exported["data"]

    assert exported["spec"] == "chara_card_v2"
    assert exported["spec_version"] == "2.0"
    for key in (
        "nickname",
        "creator_notes_multilingual",
        "source",
        "assets",
        "group_only_greetings",
        "creation_date",
        "modification_date",
    ):
        assert key not in data


def test_v3_export_to_v2_keeps_shared_fields_and_extensions(v3_card: dict) -> None:
    data = dump_v2(parse_card(v3_card)[0])["data"]

    assert data["name"] == "Haruhi"
    assert data["creator_notes"] == "Made for tests."
    assert data["extensions"] == {"card_ext": {"keep": True}}
    assert data["character_book"]["entries"][0]["extensions"] == {"entry_ext": [1, 2, 3]}


def test_v3_export_to_v2_strips_decorator_lines(v3_card: dict) -> None:
    raw = copy.deepcopy(v3_card)
    raw["data"]["character_book"]["entries"][0]["content"] = "@@depth 1\nLore only."
    exported = dump_v2(parse_card(raw)[0])
    assert exported["data"]["character_book"]["entries"][0]["content"] == "Lore only."


def test_v2_export_to_v3_then_back_keeps_content_without_decorators(v3_card: dict) -> None:
    # `to_v2` is lossy on purpose: a V2 reader must not see `@@…` lines.
    raw = copy.deepcopy(v3_card)
    raw["data"]["character_book"]["entries"][0]["content"] = "@@activate\nKept."
    card, _ = parse_card(raw)
    entry_content = dump_v3(card)["data"]["character_book"]["entries"][0]["content"]
    assert entry_content == "@@activate\nKept."
    assert dump_v2(card)["data"]["character_book"]["entries"][0]["content"] == "Kept."


def test_v3_export_to_v1_is_the_six_legacy_fields(v3_card: dict) -> None:
    exported = dump_v1(parse_card(v3_card)[0])
    assert set(exported) == {
        "name",
        "description",
        "personality",
        "scenario",
        "first_mes",
        "mes_example",
    }


def test_v2_upgrades_to_v3_with_defaults(v2_card: dict) -> None:
    v2, _ = parse_card(v2_card)
    upgraded = to_v3(v2)

    assert isinstance(upgraded, TavernCardV3)
    assert upgraded.spec_version == "3.0"
    # The one MUST-be-present V3 field gets its empty default.
    assert upgraded.data.group_only_greetings == []
    assert upgraded.data.nickname is None
    assert upgraded.data.assets is None
    # V2 content comes along.
    assert upgraded.data.character_book is not None
    assert upgraded.data.tags == ["Anime", "school"]
    assert upgraded.data.creator_notes == "Made for tests."


def test_v1_can_be_exported_as_v3(v1_card: dict) -> None:
    exported = dump_card(parse_card(v1_card)[0], "v3")
    assert exported["spec"] == "chara_card_v3"
    assert exported["data"]["name"] == "Haruhi"
    assert exported["data"]["group_only_greetings"] == []


def test_v2_round_trips_through_v3(v2_card: dict) -> None:
    v2, _ = parse_card(v2_card)
    v3 = to_v3(v2)
    back = to_v2(v3)
    assert isinstance(back, TavernCardV2)
    assert back.data.model_dump(exclude_none=True) == v2.data.model_dump(exclude_none=True)


def test_load_card_dispatches_on_the_spec(v2_card: dict, v3_card: dict) -> None:
    assert isinstance(load_card(v2_card), TavernCardV2)
    assert isinstance(load_card(v3_card), TavernCardV3)


def test_assets_default_to_the_documented_icon(v2_card: dict) -> None:
    card, _ = parse_card(v2_card)
    assets = card_assets(card)

    assert len(assets) == 1
    assert assets[0].type == "icon"
    assert assets[0].uri == "ccdefault:"
    assert assets[0].name == "main"
    assert assets[0].ext == "png"


def test_card_icon_prefers_the_main_asset(v3_card: dict) -> None:
    raw = copy.deepcopy(v3_card)
    raw["data"]["assets"].append(
        {"type": "icon", "uri": "https://example.com/other.png", "name": "other", "ext": "png"}
    )
    card, _ = parse_card(raw)
    assert card_icon(card).name == "main"

    raw["data"]["assets"] = [a for a in raw["data"]["assets"] if a["name"] != "main"]
    card, _ = parse_card(raw)
    assert card_icon(card).name == "other"


def test_card_user_icon_and_group_greetings(v3_card: dict) -> None:
    card, _ = parse_card(v3_card)
    assert card_user_icon(card).name == "Ash"
    assert card_group_greetings(card) == ["Everyone, listen up!"]


def test_card_nickname_falls_back_to_the_name(v2_card: dict) -> None:
    v2, _ = parse_card(v2_card)
    v3, _ = parse_card(
        {
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            "data": {"name": "Haruhi", "nickname": "   "},
        }
    )
    assert card_nickname(v2) == "Haruhi"
    assert card_nickname(v3) == "Haruhi"


def test_creator_notes_language_fallbacks(v3_card: dict) -> None:
    card, _ = parse_card(v3_card)
    assert creator_notes_for(card, "ja") == "Japanese notes."
    assert creator_notes_for(card, "en-GB") == "English notes."
    # Unknown language falls back to `en`.
    assert creator_notes_for(card, "fr") == "English notes."


def test_creator_notes_fall_back_when_there_is_no_en_entry() -> None:
    card, _ = parse_card(
        {
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            "data": {
                "name": "Haruhi",
                "creator_notes": "Plain notes.",
                "creator_notes_multilingual": {"fr": "Notes."},
            },
        }
    )
    assert creator_notes_for(card, "fr") == "Notes."
    assert creator_notes_for(card, "en") == "Plain notes."
    assert creator_notes_for(card, "de") == "Plain notes."


def test_creator_notes_without_the_map_use_the_plain_field(v2_card: dict) -> None:
    card, _ = parse_card(v2_card)
    assert creator_notes_for(card, "en") == "Made for tests."


def test_newer_spec_version_warns_but_imports() -> None:
    raw = {
        "spec": "chara_card_v3",
        "spec_version": "3.2",
        "data": {"name": "Future", "group_only_greetings": []},
    }
    card, source = parse_card(raw)

    assert source == "v3"
    assert card.spec_version == "3.2"
    warnings = spec_warnings(card)
    assert warnings and "newer version" in warnings[0]


def test_supported_spec_versions_do_not_warn(v3_card: dict, v2_card: dict) -> None:
    assert spec_warnings(parse_card(v3_card)[0]) == []
    assert spec_warnings(parse_card(v2_card)[0]) == []


def test_invalid_v3_field_types_are_rejected() -> None:
    raw = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {"name": "Haruhi", "group_only_greetings": "not-a-list"},
    }
    with pytest.raises(CardError, match="invalid character card"):
        parse_card(raw)


def test_asset_ext_is_normalised(v3_card: dict) -> None:
    raw = copy.deepcopy(v3_card)
    raw["data"]["assets"][0]["ext"] = ".PNG"
    card, _ = parse_card(raw)
    assert card.data.assets[0].ext == "png"


def test_parse_lorebook_accepts_the_v3_envelope_and_a_bare_book() -> None:
    bare = {"entries": [{"keys": ["club"], "content": "Lore."}]}
    enveloped = {"spec": "lorebook_v3", "data": bare}

    assert parse_lorebook(bare).entries[0].keys == ["club"]
    assert parse_lorebook(enveloped).entries[0].keys == ["club"]


def test_parse_lorebook_rejects_junk() -> None:
    with pytest.raises(CardError):
        parse_lorebook(["not", "an", "object"])  # type: ignore[arg-type]


def test_dump_lorebook_uses_the_v3_envelope() -> None:
    book = CharacterBook.model_validate({"entries": [{"keys": ["club"], "content": "Lore."}]})
    exported = dump_lorebook(book)
    assert exported["spec"] == "lorebook_v3"
    assert exported["data"]["entries"][0]["keys"] == ["club"]


def test_stamp_creation_only_fills_a_missing_date(v3_card: dict, v2_card: dict) -> None:
    missing = {"spec": "chara_card_v3", "data": {"name": "New"}}
    stamped = stamp_creation(copy.deepcopy(missing))
    assert isinstance(stamped["data"]["creation_date"], int)

    existing = copy.deepcopy(v3_card)
    assert stamp_creation(existing)["data"]["creation_date"] == 1700000000

    # V2 cards are left alone.
    assert "creation_date" not in stamp_creation(copy.deepcopy(v2_card))["data"]


def test_stamp_modification_marks_a_v3_card(v3_card: dict, v2_card: dict) -> None:
    stamped = stamp_modification(copy.deepcopy(v3_card))
    assert stamped["data"]["modification_date"] != 1700000100
    assert "modification_date" not in stamp_modification(copy.deepcopy(v2_card))["data"]
