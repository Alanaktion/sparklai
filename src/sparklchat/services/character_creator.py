"""The interactive character-creator assistant.

The assistant is just a chat completion with a system prompt that asks the
model to (a) talk the user through fleshing out a concept and (b) after its
reply, emit a machine-readable patch describing what changed. There is no
provider-side tool-calling here — `BaseClient` only exposes plain
`complete`/`stream`, and providers vary in tool-call support — so the patch
rides along as text, delimited by `DRAFT_MARKER`, and is parsed out the same
lenient way `services/macros.py`/`services/decorators.py` parse the spec's
other curly/`@@` text conventions.

The draft itself is kept as an ordinary V2 card JSON dict, so it can be handed
straight to `services/cards.parse_card`/`dump_card` for validation/round-trip,
and straight to the frontend's `draftFromCard`/`CharacterEditor` for the final
handoff — no separate draft schema to keep in sync.
"""

import copy
import json
import re
from collections.abc import Sequence
from typing import Any

from sparklchat.services.cards import CardError, dump_card, parse_card
from sparklchat.services.providers import ChatMessage

# Delimits the assistant's human-readable reply from its machine-readable patch.
# Chosen to be extremely unlikely to appear in ordinary roleplay writing.
DRAFT_MARKER = "%%%SPARKLCHAT_DRAFT%%%"

# Card fields the assistant is allowed to set directly; anything else in a
# patch is ignored rather than rejecting the whole turn.
CORE_FIELDS = frozenset(
    {
        "name",
        "nickname",
        "description",
        "personality",
        "scenario",
        "first_mes",
        "mes_example",
        "alternate_greetings",
        "tags",
        "creator_notes",
        "character_version",
    }
)

SYSTEM_PROMPT = f"""You are a collaborative writing assistant that helps a user turn a rough \
idea into a complete Character Card (a persona for an AI roleplay chatbot). You are talking \
to the *user*, not roleplaying as the character.

Guidelines:
- Ask focused clarifying questions when the concept is vague, but do not stall: even from a \
one-line concept, propose a concrete first draft of every core field so the user has something \
to react to, then refine it from their feedback.
- Keep your conversational reply short (a few sentences plus, when useful, one clarifying \
question). The full field text belongs in the patch below, not repeated in the reply.
- `description` and `personality` are written for the model that will play the character \
(facts, traits, speech patterns), not addressed to the user.
- `first_mes` is the character's in-character opening line of a chat, written in the second \
person to `{{{{user}}}}`.
- Write everything in-character content in whatever voice fits the concept; keep your own \
conversational replies in plain, friendly English.

After your reply, always append a line containing exactly {DRAFT_MARKER} followed by a single \
JSON object with the fields you are adding or changing this turn (omit fields you are not \
touching this turn; send a field's full new value, not a diff of it). If you have nothing to \
change, still emit the marker followed by {{}}. Recognized keys: name, nickname, description, \
personality, scenario, first_mes, mes_example, alternate_greetings (array of strings), tags \
(array of strings), creator_notes, character_version, and lorebook_entries (array of \
{{"keys": [string, ...], "content": string}}, appended to the character's lorebook — only for \
background facts too, that shouldn't sit in the main description).

This is a strict rule that applies to *every* reply you send, including the second, third, and \
every later turn of this same conversation — never skip it just because you already sent one \
earlier. The marker and its JSON object must never appear anywhere else: never inside your \
conversational reply, never without the marker in front of it, and never omitted. Your \
conversational reply (everything before the marker) must not contain any curly braces or JSON \
of its own.

Example ending:
{DRAFT_MARKER}
{{"name": "Rook", "description": "A retired dragon-slayer turned baker.", "tags": ["fantasy"]}}
"""


def _empty_card() -> dict[str, Any]:
    return {"spec": "chara_card_v2", "spec_version": "2.0", "data": {}}


def build_messages(draft: dict[str, Any], turns: Sequence[Any]) -> list[ChatMessage]:
    """The prompt sent to the provider: instructions, current draft, then history."""
    context = ChatMessage(
        role="system",
        content=(
            "Current draft card (JSON; empty object means nothing written yet):\n"
            f"{json.dumps(draft or {}, ensure_ascii=False)}"
        ),
    )
    history = [
        ChatMessage(role=turn.role, content=turn.content) for turn in turns if turn.content.strip()
    ]
    return [ChatMessage(role="system", content=SYSTEM_PROMPT), context, *history]


def _strip_fence(text: str) -> str:
    """Drop a ```json fenced code block wrapper, if the model added one anyway."""
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text.strip(), re.DOTALL)
    return match.group(1) if match else text


def _parse_patch(raw: str) -> dict[str, Any] | None:
    try:
        patch = json.loads(_strip_fence(raw))
    except json.JSONDecodeError:
        return None
    return patch if isinstance(patch, dict) else None


# Recovers a patch the model appended without the marker, fenced or bare: the
# far more common slip than inventing an unrecognisable format outright.
_FENCED_TAIL = re.compile(r"```(?:json)?\s*(\{.*\})\s*```\s*$", re.DOTALL)


def _fallback_patch(text: str) -> tuple[str, dict[str, Any]] | None:
    """Recover a trailing JSON object the model appended without the marker.

    A fenced block is tried first. Otherwise, since a JSON object's braces are
    balanced, the true start of a self-contained trailing object is the last
    `{` that parses cleanly all the way to the end of the string — an earlier
    one is either unrelated prose or a brace nested inside the real object,
    and both fail to parse alone once the string is cut there, so trying
    candidates from the right lands on the right one without guessing.
    """
    fenced = _FENCED_TAIL.search(text)
    if fenced is not None:
        patch = _parse_patch(fenced.group(1))
        if patch is not None:
            return text[: fenced.start()].strip(), patch

    stripped = text.rstrip()
    if not stripped.endswith("}"):
        return None
    starts = [index for index, char in enumerate(stripped) if char == "{"]
    for start in reversed(starts):
        try:
            patch = json.loads(stripped[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(patch, dict):
            return text[:start].strip(), patch
    return None


def split_reply(text: str) -> tuple[str, dict[str, Any] | None]:
    """Split a raw reply into (display text, patch).

    The model is asked to delimit its patch with `DRAFT_MARKER`, but it does
    not always follow that reliably turn after turn, so a missing or
    unparsable marker falls back to recovering a trailing JSON object
    (fenced or bare) instead of leaking raw JSON into the visible reply.
    `patch` is `None` only when no JSON can be recovered at all, in which case
    the whole reply is kept as display text — a malformed patch degrades to
    "the assistant just talked" rather than losing the turn.
    """
    marker_at = text.find(DRAFT_MARKER)
    if marker_at == -1:
        fallback = _fallback_patch(text)
        return fallback if fallback is not None else (text.strip(), None)

    display = text[:marker_at].strip()
    remainder = text[marker_at + len(DRAFT_MARKER) :]
    patch = _parse_patch(remainder)
    if patch is None:
        recovered = _fallback_patch(remainder)
        patch = recovered[1] if recovered is not None else None
    return display, patch


def _append_lorebook_entries(data: dict[str, Any], entries: Any) -> None:
    if not isinstance(entries, list):
        return
    book = data.get("character_book")
    if not isinstance(book, dict):
        book = {"entries": []}
        data["character_book"] = book
    existing = book.get("entries")
    if not isinstance(existing, list):
        existing = []
        book["entries"] = existing

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        keys = entry.get("keys")
        keys = [str(key) for key in keys] if isinstance(keys, list) else []
        existing.append({"keys": keys, "content": content, "enabled": True})


def apply_patch(draft: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge a patch into a draft card, without validating the result."""
    base = copy.deepcopy(draft) if isinstance(draft.get("data"), dict) else _empty_card()
    data = base["data"]

    for key in CORE_FIELDS:
        if key in patch:
            data[key] = patch[key]

    _append_lorebook_entries(data, patch.get("lorebook_entries"))
    base["data"] = data
    return base


def merge_and_validate(draft: dict[str, Any], patch: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Apply a patch and normalise it through the card parser.

    On a validation failure (the model wrote a field with the wrong type, say)
    the previous draft is kept as-is and `ok` is False, so one bad turn does
    not corrupt the draft the user has already built up.
    """
    merged = apply_patch(draft, patch)
    try:
        card, _source = parse_card(merged)
    except CardError:
        return draft, False
    return dump_card(card, "v2"), True
