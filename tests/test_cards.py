"""Character Card V1/V2 parsing, upconversion, and round-trip fidelity."""

import copy

import pytest

from sparklchat.services.cards import (
    CardError,
    detect_format,
    dump_v1,
    dump_v2,
    parse_card,
)

V1_FIELDS = (
    "name",
    "description",
    "personality",
    "scenario",
    "first_mes",
    "mes_example",
)


def test_detects_v1_and_v2(v1_card: dict, v2_card: dict) -> None:
    assert detect_format(v1_card) == "v1"
    assert detect_format(v2_card) == "v2"


def test_v2_without_spec_but_with_data_is_v2(v2_card: dict) -> None:
    raw = copy.deepcopy(v2_card)
    del raw["spec"]
    assert detect_format(raw) == "v2"


def test_v1_upconverts_with_v2_defaults(v1_card: dict) -> None:
    card, source = parse_card(v1_card)

    assert source == "v1"
    assert card.spec == "chara_card_v2"
    assert card.spec_version == "2.0"
    # The six shared fields are carried over verbatim.
    for field in V1_FIELDS:
        assert getattr(card.data, field) == v1_card[field]
    # V2-only fields take their documented defaults.
    assert card.data.creator_notes == ""
    assert card.data.system_prompt == ""
    assert card.data.post_history_instructions == ""
    assert card.data.alternate_greetings == []
    assert card.data.tags == []
    assert card.data.creator == ""
    assert card.data.character_version == ""
    assert card.data.extensions == {}
    assert card.data.character_book is None


def test_v1_reexports_unchanged(v1_card: dict) -> None:
    card, _ = parse_card(v1_card)
    assert dump_v1(card) == v1_card


def test_v1_round_trips_through_v2(v1_card: dict) -> None:
    canonical = dump_v2(parse_card(v1_card)[0])
    reparsed = parse_card(canonical)[0]
    assert dump_v1(reparsed) == v1_card


def test_v2_round_trip_is_stable(v2_card: dict) -> None:
    first = dump_v2(parse_card(v2_card)[0])
    second = dump_v2(parse_card(first)[0])
    assert first == second


def test_v2_parses_every_book_entry_field(v2_card: dict) -> None:
    card, source = parse_card(v2_card)
    entry = card.data.character_book.entries[0]  # type: ignore[union-attr]

    assert source == "v2"
    assert entry.keys == ["brigade"]
    assert entry.secondary_keys == ["club"]
    assert entry.content == "The SOS Brigade."
    assert entry.enabled is True
    assert entry.insertion_order == 10
    assert entry.case_sensitive is False
    assert entry.selective is True
    assert entry.constant is False
    assert entry.position == "before_char"
    assert entry.priority == 5
    assert entry.id == 1
    assert entry.comment == "club lore"
    assert entry.name == "Brigade"


def test_extensions_survive_import_export(v2_card: dict) -> None:
    """The spec forbids destroying unknown keys inside any `extensions` map."""
    exported = dump_v2(parse_card(v2_card)[0])
    data = exported["data"]

    assert data["extensions"] == {"card_ext": {"nested": "value"}}
    assert data["character_book"]["extensions"] == {"book_ext": {"keep": True}}
    assert data["character_book"]["entries"][0]["extensions"] == {"entry_ext": [1, 2, 3]}


def test_unknown_top_level_keys_survive(v2_card: dict) -> None:
    raw = copy.deepcopy(v2_card)
    raw["future_field"] = {"custom": True}
    exported = dump_v2(parse_card(raw)[0])
    assert exported["future_field"] == {"custom": True}


def test_unknown_data_keys_survive(v2_card: dict) -> None:
    raw = copy.deepcopy(v2_card)
    raw["data"]["future_data_field"] = ["a", "b"]
    exported = dump_v2(parse_card(raw)[0])
    assert exported["data"]["future_data_field"] == ["a", "b"]


def test_missing_spec_version_is_normalised(v2_card: dict) -> None:
    raw = copy.deepcopy(v2_card)
    del raw["spec_version"]
    card, _ = parse_card(raw)
    assert card.spec_version == "2.0"


def test_unsupported_spec_is_rejected(v2_card: dict) -> None:
    raw = copy.deepcopy(v2_card)
    raw["spec"] = "chara_card_v3"
    with pytest.raises(CardError, match="unsupported character card spec"):
        parse_card(raw)


def test_unsupported_spec_version_is_rejected(v2_card: dict) -> None:
    raw = copy.deepcopy(v2_card)
    raw["spec_version"] = "3.0"
    with pytest.raises(CardError, match="spec_version"):
        parse_card(raw)


def test_invalid_field_types_are_rejected(v2_card: dict) -> None:
    raw = copy.deepcopy(v2_card)
    raw["data"]["character_book"]["entries"][0]["keys"] = "not-a-list"
    with pytest.raises(CardError, match="invalid character card"):
        parse_card(raw)


def test_invalid_entry_position_is_rejected(v2_card: dict) -> None:
    raw = copy.deepcopy(v2_card)
    raw["data"]["character_book"]["entries"][0]["position"] = "sideways"
    with pytest.raises(CardError, match="invalid character card"):
        parse_card(raw)


def test_non_object_is_rejected() -> None:
    with pytest.raises(CardError):
        parse_card(["not", "an", "object"])  # type: ignore[arg-type]


def test_dump_v1_drops_v2_only_fields(v2_card: dict) -> None:
    assert set(dump_v1(parse_card(v2_card)[0])) == set(V1_FIELDS)


def test_canonical_card_has_expected_shape(v2_card: dict) -> None:
    exported = dump_v2(parse_card(v2_card)[0])

    assert exported["spec"] == "chara_card_v2"
    assert exported["spec_version"] == "2.0"
    assert set(exported["data"]) >= {
        "name",
        "description",
        "personality",
        "scenario",
        "first_mes",
        "mes_example",
        "creator_notes",
        "system_prompt",
        "post_history_instructions",
        "alternate_greetings",
        "character_book",
        "tags",
        "creator",
        "character_version",
        "extensions",
    }


def test_unset_optional_fields_are_omitted(v1_card: dict) -> None:
    exported = dump_v2(parse_card(v1_card)[0])
    # Optional-when-absent fields are dropped rather than emitted as null.
    assert "character_book" not in exported["data"]
