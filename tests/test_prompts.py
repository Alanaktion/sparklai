"""Prompt assembly: PLAN §5 and the spec invariants in PLAN §9."""

from sparklchat.models.card import TavernCardV2
from sparklchat.services.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    HistoryTurn,
    PromptContext,
    build_prompt,
    resolve_original,
    resolve_post_history,
    resolve_system_prompt,
    substitute_macros,
)

CONTEXT = PromptContext(character_name="Haruhi", user_name="Ash")


def make_card(**overrides) -> TavernCardV2:
    data: dict = {
        "name": "Haruhi",
        "description": "A blunt student.",
        "personality": "Bold.",
        "scenario": "The club room.",
        "first_mes": "Hi {{user}}!",
        "mes_example": "",
    }
    data.update(overrides)
    return TavernCardV2.model_validate(
        {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}
    )


def turns(*pairs: tuple[str, str]) -> list[HistoryTurn]:
    return [HistoryTurn(role=role, content=content) for role, content in pairs]


# --- macros -----------------------------------------------------------------


def test_substitute_macros_handles_both_spellings_and_case() -> None:
    text = "{{char}} and <BOT> talk to {{user}} and <user>."
    assert substitute_macros(text, CONTEXT) == "Haruhi and Haruhi talk to Ash and Ash."


def test_substitute_macros_ignores_unrelated_text() -> None:
    assert substitute_macros("no macros here", CONTEXT) == "no macros here"


def test_resolve_original_expands_the_placeholder() -> None:
    assert resolve_original("A: {{original}}", "default") == "A: default"
    assert resolve_original("no placeholder", "default") == "no placeholder"


# --- system prompt precedence ----------------------------------------------


def test_character_system_prompt_replaces_the_global_one() -> None:
    card = make_card(system_prompt="Character rules.")
    resolved = resolve_system_prompt(card, default_system_prompt="Global rules.")
    assert resolved == "Character rules."


def test_system_prompt_macros_are_substituted_during_assembly() -> None:
    card = make_card(system_prompt="You are {{char}} writing for {{user}}.")
    prompt = build_prompt(card, [], context=CONTEXT)
    assert "You are Haruhi writing for Ash." in prompt[0].content
    assert "{{char}}" not in prompt[0].content


def test_empty_character_system_prompt_falls_back_to_the_global_one() -> None:
    card = make_card(system_prompt="")
    assert resolve_system_prompt(card, default_system_prompt="Global rules.") == ("Global rules.")


def test_empty_global_system_prompt_falls_back_to_the_internal_one() -> None:
    card = make_card(system_prompt="")
    assert resolve_system_prompt(card, default_system_prompt="") == DEFAULT_SYSTEM_PROMPT


def test_original_placeholder_resolves_to_the_global_prompt() -> None:
    card = make_card(system_prompt="Global says: {{original}}")
    assert resolve_system_prompt(card, default_system_prompt="Global rules.") == (
        "Global says: Global rules."
    )


def test_session_override_wins_and_can_reference_the_original() -> None:
    card = make_card(system_prompt="")
    resolved = resolve_system_prompt(
        card,
        default_system_prompt="Global rules.",
        override="Override over {{original}}",
    )
    assert resolved == "Override over Global rules."


def test_post_history_precedence_matches_the_system_prompt() -> None:
    card = make_card(post_history_instructions="Character UJB")
    assert resolve_post_history(card, default_post_history="User UJB") == "Character UJB"

    empty = make_card(post_history_instructions="")
    assert resolve_post_history(empty, default_post_history="") == ""


# --- assembly ---------------------------------------------------------------


def test_first_message_is_the_system_prompt_and_character_block() -> None:
    prompt = build_prompt(make_card(), [], context=CONTEXT)

    assert prompt[0].role == "system"
    assert "Haruhi" in prompt[0].content
    assert "A blunt student." in prompt[0].content
    assert "Personality: Bold." in prompt[0].content
    assert "Scenario: The club room." in prompt[0].content


def test_history_is_appended_in_order() -> None:
    prompt = build_prompt(
        make_card(),
        turns(("assistant", "Hi!"), ("user", "Hello"), ("assistant", "Hey")),
        context=CONTEXT,
    )
    assert [(m.role, m.content) for m in prompt[1:]] == [
        ("assistant", "Hi!"),
        ("user", "Hello"),
        ("assistant", "Hey"),
    ]


def test_mes_example_is_included() -> None:
    card = make_card(mes_example="{{user}}: hi\n{{char}}: hello")
    prompt = build_prompt(card, [], context=CONTEXT)
    assert "Example dialogue:" in prompt[0].content
    assert "Ash: hi" in prompt[0].content


def test_post_history_is_a_trailing_system_message() -> None:
    card = make_card(post_history_instructions="Stay in character.")
    prompt = build_prompt(card, turns(("user", "hi")), context=CONTEXT)

    assert prompt[-1].role == "system"
    assert prompt[-1].content == "Stay in character."


def test_post_history_is_omitted_when_empty() -> None:
    prompt = build_prompt(make_card(), turns(("user", "hi")), context=CONTEXT)
    assert [message.role for message in prompt] == ["system", "user"]


def test_creator_notes_tags_creator_and_version_never_reach_the_model() -> None:
    card = make_card(
        creator_notes="SECRET-NOTES",
        tags=["SECRET-TAG"],
        creator="SECRET-CREATOR",
        character_version="SECRET-VERSION",
    )
    prompt = build_prompt(card, turns(("user", "hi")), context=CONTEXT)
    joined = "\n".join(message.content for message in prompt)

    for secret in ("SECRET-NOTES", "SECRET-TAG", "SECRET-CREATOR", "SECRET-VERSION"):
        assert secret not in joined


def test_lorebook_entries_are_placed_before_and_after_char() -> None:
    card = make_card(
        character_book={
            "extensions": {},
            "entries": [
                {
                    "keys": ["brigade"],
                    "content": "BEFORE-MARKER",
                    "position": "before_char",
                    "extensions": {},
                },
                {
                    "keys": ["brigade"],
                    "content": "AFTER-MARKER",
                    "position": "after_char",
                    "extensions": {},
                },
            ],
        }
    )
    prompt = build_prompt(card, turns(("user", "the brigade")), context=CONTEXT)
    system = prompt[0].content

    assert "BEFORE-MARKER" in system
    assert "AFTER-MARKER" in system
    assert system.index("BEFORE-MARKER") < system.index("AFTER-MARKER")


def test_lorebook_entry_metadata_is_not_sent() -> None:
    card = make_card(
        character_book={
            "extensions": {},
            "entries": [
                {
                    "keys": ["brigade"],
                    "content": "Club lore.",
                    "comment": "SECRET-COMMENT",
                    "name": "SECRET-NAME",
                    "id": 42,
                    "extensions": {},
                }
            ],
        }
    )
    prompt = build_prompt(card, turns(("user", "brigade")), context=CONTEXT)
    system = prompt[0].content

    assert "Club lore." in system
    for secret in ("SECRET-COMMENT", "SECRET-NAME"):
        assert secret not in system


def test_character_book_can_be_switched_off_per_session() -> None:
    card = make_card(
        character_book={
            "extensions": {},
            "entries": [{"keys": ["brigade"], "content": "MARKER", "extensions": {}}],
        }
    )
    history = turns(("user", "brigade"))

    included = build_prompt(card, history, context=CONTEXT)
    excluded = build_prompt(card, history, context=CONTEXT, use_character_book=False)

    assert "MARKER" in included[0].content
    assert "MARKER" not in excluded[0].content


# --- truncation -------------------------------------------------------------


def test_oldest_non_greeting_turns_are_dropped_first() -> None:
    history = [
        HistoryTurn(role="assistant", content="GREETING", is_greeting=True),
        HistoryTurn(role="user", content="oldest " * 100),
        HistoryTurn(role="assistant", content="reply " * 100),
        HistoryTurn(role="user", content="newest " * 100),
    ]
    prompt = build_prompt(
        make_card(), history, context=CONTEXT, context_window=400, context_reserve=0
    )
    contents = [message.content for message in prompt[1:]]

    assert "GREETING" in contents
    assert "newest " * 100 in contents
    assert "oldest " * 100 not in contents
    assert len(contents) < len(history)


def test_the_greeting_survives_even_with_no_budget() -> None:
    history = [
        HistoryTurn(role="assistant", content="GREETING", is_greeting=True),
        HistoryTurn(role="user", content="a" * 400),
    ]
    prompt = build_prompt(
        make_card(), history, context=CONTEXT, context_window=1, context_reserve=0
    )
    assert [message.content for message in prompt[1:]] == ["GREETING"]
