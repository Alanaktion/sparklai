"""Curly-braced macro expansion (Character Card V3 spec)."""

import random

from sparklchat.services.macros import MacroContext, expand_macros, match_text

CONTEXT = MacroContext(character_name="Haruhi", user_name="Ash")


def test_char_and_user_spellings_are_case_insensitive() -> None:
    assert expand_macros("{{char}} and <char> and <BOT>", CONTEXT) == (
        "Haruhi and Haruhi and Haruhi"
    )
    assert expand_macros("{{CHAR}}", CONTEXT) == "Haruhi"
    assert expand_macros("{{user}} and <USER>", CONTEXT) == "Ash and Ash"


def test_multiple_macros_and_empty_input() -> None:
    assert expand_macros("{{char}} greets {{user}}", CONTEXT) == "Haruhi greets Ash"
    assert expand_macros("", CONTEXT) == ""


def test_random_always_returns_one_of_the_values() -> None:
    for _ in range(20):
        assert expand_macros("{{random:red, green,blue}}", MacroContext()) in {
            "red",
            "green",
            "blue",
        }


def test_random_is_reproducible_when_seeded() -> None:
    random.seed(1234)
    first = expand_macros("{{random:a,b,c}}", MacroContext())
    random.seed(1234)
    assert expand_macros("{{random:a,b,c}}", MacroContext()) == first


def test_random_treats_escaped_comma_as_literal() -> None:
    seen = {expand_macros("{{random:a\\,b,c}}", MacroContext()) for _ in range(50)}
    assert seen == {"a,b", "c"}


def test_random_without_values_is_left_unchanged() -> None:
    assert expand_macros("{{random}}", MacroContext()) == "{{random}}"
    assert expand_macros("{{random:}}", MacroContext()) == "{{random:}}"


def test_pick_is_stable_and_taken_from_the_list() -> None:
    context = MacroContext(seed="seed")
    assert expand_macros("{{pick:A,A,A}}", context) == "A"

    first = expand_macros("{{pick:A,B,C}}", context)
    assert first in {"A", "B", "C"}
    assert expand_macros("{{pick:A,B,C}}", context) == first


def test_pick_accepts_an_optional_leading_colon() -> None:
    context = MacroContext(seed="seed")
    assert expand_macros("{{pick::A,A}}", context) == "A"
    assert expand_macros("{{pick::A,B}}", context) in {"A", "B"}


def test_roll_stays_within_range_and_is_reproducible() -> None:
    for _ in range(20):
        assert expand_macros("{{roll:6}}", MacroContext()) in {str(n) for n in range(1, 7)}

    random.seed(99)
    first = expand_macros("{{roll:6}}", MacroContext())
    random.seed(99)
    assert expand_macros("{{roll:6}}", MacroContext()) == first


def test_roll_accepts_dice_notation() -> None:
    random.seed(5)
    first = expand_macros("{{roll:6}}", MacroContext())
    random.seed(5)
    assert expand_macros("{{roll:d6}}", MacroContext()) == first
    random.seed(5)
    assert expand_macros("{{roll:D6}}", MacroContext()) == first


def test_roll_with_invalid_die_is_left_unchanged() -> None:
    assert expand_macros("{{roll:0}}", MacroContext()) == "{{roll:0}}"
    assert expand_macros("{{roll:abc}}", MacroContext()) == "{{roll:abc}}"


def test_comments_and_hidden_keys_expand_to_empty() -> None:
    assert expand_macros("{{// secret}}", MacroContext()) == ""
    assert expand_macros("{{comment: note}}", MacroContext()) == ""
    assert expand_macros("{{hidden_key:x}}", MacroContext()) == ""


def test_reverse_reverses_its_value() -> None:
    assert expand_macros("{{reverse:Hello}}", MacroContext()) == "olleH"
    assert expand_macros("{{reverse: Hello}}", MacroContext()) == "olleH"


def test_unknown_and_unclosed_macros_are_left_verbatim() -> None:
    assert expand_macros("{{something}}", MacroContext()) == "{{something}}"
    assert expand_macros("before {{oops", MacroContext()) == "before {{oops"


def test_match_text_controls_hidden_keys() -> None:
    text = "{{hidden_key:club room}}"
    assert match_text(text, MacroContext(), include_hidden=True) == "club room"
    assert match_text(text, MacroContext()) == ""
    assert expand_macros(text, MacroContext()) == ""


def test_match_text_expands_other_macros_like_expand_macros() -> None:
    text = "{{char}} meets {{reverse:ab}} {{// hidden}}"
    assert match_text(text, CONTEXT) == expand_macros(text, CONTEXT)
