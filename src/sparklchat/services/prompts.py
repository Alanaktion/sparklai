"""Prompt assembly: card + session + history -> provider chat messages.

Ordering follows PLAN §5. Text that the spec forbids sending to the model
(`creator_notes`, `tags`, `creator`, `character_version`, and book-entry
`comment`/`id`/`name`) is never read here.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from sparklchat.models.card import CharacterBook, TavernCardV2
from sparklchat.services.lorebook import select_stacked_entries
from sparklchat.services.providers import ChatMessage
from sparklchat.services.tokens import count_tokens

DEFAULT_SYSTEM_PROMPT = (
    "Write {{char}}'s next reply in a fictional roleplay between {{char}} and "
    "{{user}}. Stay in character and never write {{user}}'s lines."
)
# The internal fallback for post-history instructions is "nothing extra".
DEFAULT_POST_HISTORY = ""
DEFAULT_CONTEXT_RESERVE = 512

_CHAR = re.compile(r"{{char}}|<bot>", re.IGNORECASE)
_USER = re.compile(r"{{user}}|<user>", re.IGNORECASE)
_ORIGINAL = re.compile(r"{{original}}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class PromptContext:
    character_name: str = "Character"
    user_name: str = "User"


@dataclass(frozen=True, slots=True)
class HistoryTurn:
    role: str
    content: str
    is_greeting: bool = False


def substitute_macros(text: str, context: PromptContext) -> str:
    """Replace `{{char}}`/`<BOT>` and `{{user}}`/`<USER>`, case-insensitively."""
    if not text:
        return text
    text = _CHAR.sub(lambda _match: context.character_name, text)
    return _USER.sub(lambda _match: context.user_name, text)


def resolve_original(template: str, original: str) -> str:
    """Expand `{{original}}` to the prompt that would otherwise have been used."""
    if not template or not _ORIGINAL.search(template):
        return template
    return _ORIGINAL.sub(lambda _match: original, template)


def resolve_system_prompt(
    card: TavernCardV2,
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
    card: TavernCardV2,
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
    card: TavernCardV2,
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
    context_window: int = 8192,
    context_reserve: int = DEFAULT_CONTEXT_RESERVE,
) -> list[ChatMessage]:
    """Build the message array for a provider."""
    context = context or PromptContext()

    system_text = substitute_macros(
        resolve_system_prompt(
            card,
            default_system_prompt=default_system_prompt,
            override=system_prompt_override,
        ),
        context,
    )
    post_history = substitute_macros(
        resolve_post_history(
            card,
            default_post_history=default_post_history,
            override=post_history_override,
        ),
        context,
    )

    sections = [system_text, _character_block(card, context)]

    if _has_book(card.data.character_book, use_character_book, world_book, use_world_book):
        matched = select_stacked_entries(
            card.data.character_book,
            world_book,
            [turn.content for turn in history],
            use_character_book=use_character_book,
            use_world_book=use_world_book,
        )
        before = _contents(matched.before_char, context)
        after = _contents(matched.after_char, context)
        if before:
            sections.append("\n".join(before))
        if after:
            sections.append("\n".join(after))

    examples = (card.data.mes_example or "").strip()
    if examples:
        sections.append("Example dialogue:\n" + substitute_macros(examples, context))

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
        ChatMessage(role=turn.role, content=turn.content) for turn in _truncate(history, budget)
    )
    if post_history:
        messages.append(ChatMessage(role="system", content=post_history))
    return messages


def _has_book(
    character_book: CharacterBook | None,
    use_character_book: bool,
    world_book: CharacterBook | None,
    use_world_book: bool,
) -> bool:
    return (use_character_book and character_book is not None) or (
        use_world_book and world_book is not None
    )


def _character_block(card: TavernCardV2, context: PromptContext) -> str:
    data = card.data
    lines = [f"Character: {context.character_name}"]
    if (data.description or "").strip():
        lines.append(substitute_macros(data.description.strip(), context))
    if (data.personality or "").strip():
        lines.append(f"Personality: {substitute_macros(data.personality.strip(), context)}")
    if (data.scenario or "").strip():
        lines.append(f"Scenario: {substitute_macros(data.scenario.strip(), context)}")
    return "\n".join(lines)


def _contents(entries, context: PromptContext) -> list[str]:
    return [
        substitute_macros(entry.content.strip(), context)
        for entry in entries
        if (entry.content or "").strip()
    ]


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
