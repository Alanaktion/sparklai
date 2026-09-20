"""Prompt assembly: card + session + history -> provider chat messages.

Ordering follows PLAN §5 and the Character Card V3 additions. Text that the spec
forbids sending to the model (`creator_notes`, `tags`, `creator`,
`character_version`, and book-entry `comment`/`id`/`name`) is never read here.
Curly-braced macros are expanded with `services.macros`, so `{{// …}}` and
`{{comment: …}}` collapse to nothing before the model sees them.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sparklchat.models.card import CharacterBook, CharacterCard
from sparklchat.services.cards import card_nickname
from sparklchat.services.lorebook import (
    MatchContext,
    MatchedEntries,
    MatchedEntry,
    merge_matched,
    select_entries,
    select_stacked_entries,
)
from sparklchat.services.macros import MacroContext, expand_macros
from sparklchat.services.providers import ChatMessage
from sparklchat.services.tokens import count_tokens

DEFAULT_SYSTEM_PROMPT = (
    "Write {{char}}'s next reply in a fictional roleplay between {{char}} and "
    "{{user}}. Stay in character and never write {{user}}'s lines."
)
# The internal fallback for post-history instructions is "nothing extra".
DEFAULT_POST_HISTORY = ""
DEFAULT_CONTEXT_RESERVE = 512

# `{{original}}` is resolved before macro expansion.
_ORIGINAL = re.compile(r"{{original}}", re.IGNORECASE)
# `@@position` values that we place relative to a character section.
_DESCRIPTION_POSITIONS = frozenset({"before_desc", "after_desc", "personality", "scenario"})


@dataclass(frozen=True, slots=True)
class PromptContext:
    character_name: str = "Character"
    user_name: str = "User"


@dataclass(frozen=True, slots=True)
class HistoryTurn:
    role: str
    content: str
    is_greeting: bool = False


@dataclass(frozen=True, slots=True)
class CastMember:
    """One character in a (possibly single-character) session cast."""

    name: str
    card: CharacterCard


def substitute_macros(text: str, context: PromptContext) -> str:
    """Replace the shared macros (`{{char}}`, `{{user}}`, and `<BOT>`/`<USER>`)."""
    if not text:
        return text
    return expand_macros(text, MacroContext(context.character_name, context.user_name))


def resolve_original(template: str, original: str) -> str:
    """Expand `{{original}}` to the prompt that would otherwise have been used."""
    if not template or not _ORIGINAL.search(template):
        return template
    return _ORIGINAL.sub(lambda _match: original, template)


def resolve_system_prompt(
    card: CharacterCard,
    *,
    default_system_prompt: str = "",
    override: str | None = None,
) -> str:
    """Character system prompt replaces the global one; empty falls back."""
    base = (default_system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT
    character = (card.data.system_prompt or "").strip()
    resolved = resolve_original(character, base) if character else base
    if override and override.strip():
        resolved = resolve_original(override.strip(), resolved)
    return resolved


def resolve_post_history(
    card: CharacterCard,
    *,
    default_post_history: str = "",
    override: str | None = None,
) -> str:
    base = (default_post_history or "").strip() or DEFAULT_POST_HISTORY
    character = (card.data.post_history_instructions or "").strip()
    resolved = resolve_original(character, base) if character else base
    if override and override.strip():
        resolved = resolve_original(override.strip(), resolved)
    return resolved


def build_prompt(
    card: CharacterCard,
    history: Sequence[HistoryTurn],
    *,
    context: PromptContext | None = None,
    default_system_prompt: str = "",
    default_post_history: str = "",
    system_prompt_override: str | None = None,
    post_history_override: str | None = None,
    use_character_book: bool = True,
    world_book: CharacterBook | None = None,
    use_world_book: bool = True,
    cast: Sequence[CastMember] | None = None,
    context_window: int = 8192,
    context_reserve: int = DEFAULT_CONTEXT_RESERVE,
    greeting_index: int | None = None,
    user_icon: str | None = None,
    activation_counts: Mapping[str, int] | None = None,
    matched_keys: set[str] | None = None,
) -> list[ChatMessage]:
    """Build the message array for a provider."""
    context = context or PromptContext()
    turns = list(history)
    macro_context = MacroContext(
        character_name=card_nickname(card) or context.character_name,
        user_name=context.user_name,
        # Deterministic `{{pick}}`, stable across regenerations of a prompt.
        seed=f"{context.character_name}\x00{context.user_name}",
    )

    match_context = MatchContext(
        history=tuple(turn.content for turn in turns),
        assistant_count=sum(1 for turn in turns if turn.role == "assistant"),
        token_count=sum(count_tokens(turn.content) for turn in turns),
        max_context_tokens=max(0, context_window - context_reserve),
        greeting_index=greeting_index,
        user_icon=user_icon,
        activation_counts=dict(activation_counts or {}),
        macro_context=macro_context,
    )

    matched = _matched_entries(
        card,
        list(cast or []),
        world_book,
        [turn.content for turn in turns],
        match_context=match_context,
        matched_keys=matched_keys,
        use_character_book=use_character_book,
        use_world_book=use_world_book,
    )
    disabled = {ui for item in matched.all for ui in item.decorators.disable_ui_prompt}
    positioned = _positioned(matched, macro_context)

    system_text = ""
    if "system_prompt" not in disabled:
        system_text = _expand(
            resolve_system_prompt(
                card,
                default_system_prompt=default_system_prompt,
                override=system_prompt_override,
            ),
            macro_context,
        )
    post_history = ""
    if "post_history_instructions" not in disabled:
        post_history = _expand(
            resolve_post_history(
                card,
                default_post_history=default_post_history,
                override=post_history_override,
            ),
            macro_context,
        )

    sections = [system_text, _character_section(card, cast, context, positioned)]
    before = _contents(
        [item for item in matched.before_char if not _positioned_out(item)], macro_context
    )
    after = _contents(
        [item for item in matched.after_char if not _positioned_out(item)], macro_context
    )
    if before:
        sections.append("\n".join(before))
    if after:
        sections.append("\n".join(after))

    examples = (card.data.mes_example or "").strip()
    if examples:
        sections.append("Example dialogue:\n" + _expand(examples, macro_context))

    system_message = ChatMessage(
        role="system", content="\n\n".join(section for section in sections if section)
    )

    budget = (
        context_window
        - context_reserve
        - count_tokens(system_message.content)
        - count_tokens(post_history)
    )
    messages = [system_message]
    messages.extend(
        ChatMessage(role=turn.role, content=turn.content) for turn in _truncate(turns, budget)
    )
    _interleave_depth(messages, matched.chat, macro_context)
    if post_history:
        messages.append(ChatMessage(role="system", content=post_history))
    return messages


GROUP_DIRECTIVE = (
    "This is a group scene with several characters. Write only {character}'s next "
    "reply, in their voice, and never write another character's lines."
)


def _character_section(
    card: CharacterCard,
    cast: Sequence[CastMember] | None,
    context: PromptContext,
    positioned: Mapping[str, list[str]],
) -> str:
    """The character definition block: one character, or the whole group."""
    members = list(cast or [])
    if len(members) <= 1:
        return _character_block(card, context, positioned)

    blocks = [_member_block(member, context) for member in members]
    extra = [text for texts in positioned.values() for text in texts]
    if extra:
        blocks.append("\n".join(extra))
    blocks.append(GROUP_DIRECTIVE.format(character=context.character_name))
    return "\n\n".join(blocks)


def _character_block(
    card: CharacterCard, context: PromptContext, positioned: Mapping[str, list[str]]
) -> str:
    """One character's definition, with `@@position` content interleaved."""
    data = card.data
    macro_context = MacroContext(card_nickname(card) or context.character_name, context.user_name)
    lines = [f"Character: {context.character_name}"]
    lines.extend(positioned.get("before_desc", []))
    if (data.description or "").strip():
        lines.append(_expand(data.description.strip(), macro_context))
    lines.extend(positioned.get("after_desc", []))
    personality = (data.personality or "").strip()
    personality_extra = positioned.get("personality", [])
    if personality or personality_extra:
        lines.append(
            "Personality: "
            + "\n".join([_expand(personality, macro_context), *personality_extra]).strip()
        )
    scenario = (data.scenario or "").strip()
    scenario_extra = positioned.get("scenario", [])
    if scenario or scenario_extra:
        lines.append(
            "Scenario: " + "\n".join([_expand(scenario, macro_context), *scenario_extra]).strip()
        )
    return "\n".join(lines)


def _member_block(member: CastMember, context: PromptContext) -> str:
    member_context = PromptContext(character_name=member.name, user_name=context.user_name)
    data = member.card.data
    lines = [f"Character: {member.name}"]
    if (data.description or "").strip():
        lines.append(substitute_macros(data.description.strip(), member_context))
    if (data.personality or "").strip():
        lines.append(f"Personality: {substitute_macros(data.personality.strip(), member_context)}")
    if (data.scenario or "").strip():
        lines.append(f"Scenario: {substitute_macros(data.scenario.strip(), member_context)}")
    return "\n".join(lines)


def _matched_entries(
    card: CharacterCard,
    cast: Sequence[CastMember],
    world_book: CharacterBook | None,
    history: Sequence[str],
    *,
    match_context: MatchContext,
    matched_keys: set[str] | None,
    use_character_book: bool,
    use_world_book: bool,
) -> MatchedEntries:
    """Lorebook entries to inject, or an empty result when no book is in play.

    A single character stacks its book over the world book (§4.4). In a group, the
    acting character's book wins, then the other members' in cast order, then the
    world book. Substitutions use the acting character's context.
    """
    if len(cast) <= 1:
        if not use_character_book and not (use_world_book and world_book is not None):
            return MatchedEntries()
        return select_stacked_entries(
            card.data.character_book,
            world_book,
            history,
            context=match_context,
            matched_keys=matched_keys,
            use_character_book=use_character_book,
            use_world_book=use_world_book,
        )

    groups = []
    if use_character_book:
        groups.append(
            select_entries(
                card.data.character_book,
                history,
                context=match_context,
                matched_keys=matched_keys,
            )
        )
        for member in cast:
            if member.card is card:
                continue
            groups.append(
                select_entries(member.card.data.character_book, history, context=match_context)
            )
    if use_world_book:
        groups.append(select_entries(world_book, history, context=match_context))
    return merge_matched(groups)


def _positioned(matched: MatchedEntries, macro_context: MacroContext) -> dict[str, list[str]]:
    """Group `@@position` entries by the section they want to sit in."""
    positioned: dict[str, list[str]] = {}
    for item in matched.all:
        position = item.decorators.position
        if position in _DESCRIPTION_POSITIONS and item.content.strip():
            positioned.setdefault(position, []).append(_expand(item.content, macro_context))
    return positioned


def _positioned_out(item: MatchedEntry) -> bool:
    """Whether an entry was already placed by a `@@position` decorator."""
    return item.decorators.position in _DESCRIPTION_POSITIONS


def _interleave_depth(
    messages: list[ChatMessage], entries: Sequence[MatchedEntry], macro_context: MacroContext
) -> None:
    """Insert `@@depth` entries into the chat log, newest-first counting.

    Depth counts assistant-visible messages from the end: `1` lands just before
    the most recent message, a value at or above the log length goes before the
    oldest message, and `0` is appended after the most recent message.
    """
    for item in entries:
        depth = item.decorators.depth
        if depth is None or not item.content.strip():
            continue
        index = len(messages) if depth <= 0 else max(1, len(messages) - depth)
        messages.insert(
            index,
            ChatMessage(role=_depth_role(item), content=_expand(item.content, macro_context)),
        )


def _depth_role(item: MatchedEntry) -> str:
    role = item.decorators.role
    return role if role in {"system", "user", "assistant"} else "system"


def _contents(entries: Sequence[MatchedEntry], macro_context: MacroContext) -> list[str]:
    return [_expand(item.content, macro_context) for item in entries if item.content.strip()]


def _expand(text: str, macro_context: MacroContext) -> str:
    return expand_macros(text, macro_context)


def _truncate(history: Sequence[HistoryTurn], budget: int) -> list[HistoryTurn]:
    """Drop the oldest non-greeting turns until the history fits `budget`."""
    turns = list(history)

    def total() -> int:
        return sum(count_tokens(turn.content) for turn in turns)

    if budget <= 0:
        return [turn for turn in turns if turn.is_greeting]

    while turns and total() > budget:
        index = next(
            (i for i, turn in enumerate(turns) if not turn.is_greeting),
            None,
        )
        if index is None:
            break
        turns.pop(index)
    return turns
