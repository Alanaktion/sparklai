"""Prompt assembly for the Character Card V3 additions: macros, nicknames, and
lorebook decorators that reposition or suppress prompt content."""

from sparklchat.models.card import TavernCardV2, TavernCardV3
from sparklchat.services.prompts import HistoryTurn, PromptContext, build_prompt

CONTEXT = PromptContext(character_name="Haruhi", user_name="Ash")

BASE = {
    "name": "Haruhi",
    "description": "A blunt student.",
    "personality": "Bold.",
    "scenario": "The club room.",
    "first_mes": "Hi {{user}}!",
    "mes_example": "",
}


def card(**overrides) -> TavernCardV2:
    data = {**BASE, **overrides}
    return TavernCardV2.model_validate(
        {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}
    )


def v3(**overrides) -> TavernCardV3:
    data = {**BASE, **overrides}
    return TavernCardV3.model_validate(
        {"spec": "chara_card_v3", "spec_version": "3.0", "data": data}
    )


def book(*entries: dict) -> dict:
    return {"extensions": {}, "entries": list(entries)}


def turns(*pairs: tuple[str, str]) -> list[HistoryTurn]:
    return [HistoryTurn(role=role, content=content) for role, content in pairs]


def system_of(prompt) -> str:
    return prompt[0].content


# --- nicknames and macros ---------------------------------------------------


def test_nickname_replaces_char_in_prompts() -> None:
    card_ = v3(nickname="Haru", system_prompt="You are {{char}} with {{user}}.")
    prompt = build_prompt(card_, [], context=CONTEXT)
    assert "You are Haru with Ash." in system_of(prompt)
    assert "{{char}}" not in system_of(prompt)


def test_nickname_falls_back_to_the_name() -> None:
    card_ = v3(nickname="", system_prompt="You are {{char}}.")
    assert "You are Haruhi." in system_of(build_prompt(card_, [], context=CONTEXT))


def test_comment_macros_never_reach_the_model() -> None:
    card_ = card(
        description="Visible. {{// secret note}}{{comment: another note}}",
        system_prompt="Rules. {{// hidden}}",
    )
    prompt = build_prompt(card_, [], context=CONTEXT)
    system = system_of(prompt)

    assert "Visible." in system
    assert "secret note" not in system
    assert "another note" not in system
    assert "hidden" not in system


def test_reverse_and_roll_macros_expand() -> None:
    card_ = card(description="Code {{reverse:secret}}.")
    system = system_of(build_prompt(card_, [], context=CONTEXT))
    assert "Code terces." in system


def test_random_macros_pick_from_their_values() -> None:
    card_ = card(description="{{random:alpha,beta}}")
    system = system_of(build_prompt(card_, [], context=CONTEXT))
    assert "alpha" in system or "beta" in system


def test_pick_macros_are_stable_for_a_prompt() -> None:
    card_ = card(description="{{pick:alpha,beta,gamma}}")
    first = system_of(build_prompt(card_, [], context=CONTEXT))
    second = system_of(build_prompt(card_, [], context=CONTEXT))
    assert first == second


# --- decorator-driven placement ---------------------------------------------


def test_position_after_desc_sits_between_description_and_personality() -> None:
    card_ = card(
        character_book=book(
            {"keys": ["brigade"], "content": "@@position after_desc\nAFTER-DESC", "extensions": {}}
        )
    )
    system = system_of(build_prompt(card_, turns(("user", "brigade")), context=CONTEXT))

    assert system.index("A blunt student.") < system.index("AFTER-DESC")
    assert system.index("AFTER-DESC") < system.index("Personality:")


def test_position_before_desc_sits_before_description() -> None:
    card_ = card(
        character_book=book(
            {
                "keys": ["brigade"],
                "content": "@@position before_desc\nBEFORE-DESC",
                "extensions": {},
            }
        )
    )
    system = system_of(build_prompt(card_, turns(("user", "brigade")), context=CONTEXT))

    assert system.index("BEFORE-DESC") < system.index("A blunt student.")


def test_position_scenario_appends_to_the_scenario_section() -> None:
    card_ = card(
        character_book=book(
            {
                "keys": ["brigade"],
                "content": "@@position scenario\nEXTRA-SCENARIO",
                "extensions": {},
            }
        )
    )
    system = system_of(build_prompt(card_, turns(("user", "brigade")), context=CONTEXT))

    assert "Scenario: The club room.\nEXTRA-SCENARIO" in system


def test_depth_inserts_into_the_chat_log() -> None:
    card_ = card(
        character_book=book(
            {"keys": ["brigade"], "content": "@@depth 1\nINJECTED", "extensions": {}}
        )
    )
    prompt = build_prompt(
        card_,
        turns(("user", "hey"), ("assistant", "hello"), ("user", "brigade")),
        context=CONTEXT,
    )

    assert [(m.role, m.content) for m in prompt[1:]] == [
        ("user", "hey"),
        ("assistant", "hello"),
        ("system", "INJECTED"),
        ("user", "brigade"),
    ]
    # Deep entries stay out of the system block.
    assert "INJECTED" not in prompt[0].content


def test_depth_zero_appends_after_the_most_recent_message() -> None:
    card_ = card(
        character_book=book(
            {
                "keys": ["brigade"],
                "content": "@@depth 0\n@@role assistant\nPREFILL",
                "extensions": {},
            }
        )
    )
    prompt = build_prompt(card_, turns(("user", "brigade")), context=CONTEXT)

    assert (prompt[-1].role, prompt[-1].content) == ("assistant", "PREFILL")


def test_a_huge_depth_goes_before_the_oldest_message() -> None:
    card_ = card(
        character_book=book({"keys": ["brigade"], "content": "@@depth 99\nEARLY", "extensions": {}})
    )
    prompt = build_prompt(card_, turns(("user", "brigade"), ("assistant", "hi")), context=CONTEXT)

    assert prompt[1].content == "EARLY"


def test_disable_ui_prompt_suppresses_the_system_prompt() -> None:
    card_ = card(
        system_prompt="SECRET-SYSTEM",
        character_book=book(
            {
                "keys": ["brigade"],
                "content": "@@disable_ui_prompt system_prompt\nLore.",
                "extensions": {},
            }
        ),
    )
    prompt = build_prompt(card_, turns(("user", "brigade")), context=CONTEXT)

    assert "SECRET-SYSTEM" not in system_of(prompt)
    assert "Lore." in system_of(prompt)


def test_disable_ui_prompt_suppresses_post_history_instructions() -> None:
    card_ = card(
        post_history_instructions="SECRET-UJB",
        character_book=book(
            {
                "keys": ["brigade"],
                "content": "@@disable_ui_prompt post_history_instructions\nLore.",
                "extensions": {},
            }
        ),
    )
    prompt = build_prompt(card_, turns(("user", "brigade")), context=CONTEXT)

    assert all("SECRET-UJB" not in message.content for message in prompt)


def test_unmatched_entries_never_leak_into_the_prompt() -> None:
    card_ = card(
        character_book=book(
            {"keys": ["trombone"], "content": "@@position after_desc\nNOPE", "extensions": {}}
        )
    )
    prompt = build_prompt(card_, turns(("user", "brigade")), context=CONTEXT)
    assert "NOPE" not in system_of(prompt)


def test_is_greeting_uses_the_active_greeting_index() -> None:
    card_ = card(
        character_book=book(
            {"keys": ["brigade"], "content": "@@is_greeting 1\nALT-LORE", "extensions": {}}
        )
    )
    history = turns(("assistant", "Hi!"), ("user", "brigade"))

    greeting = build_prompt(card_, history, context=CONTEXT, greeting_index=1)
    other = build_prompt(card_, history, context=CONTEXT, greeting_index=0)

    assert "ALT-LORE" in system_of(greeting)
    assert "ALT-LORE" not in system_of(other)
