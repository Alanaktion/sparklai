"""Character book (lorebook) matching.

Implements PLAN §4.3: scan the recent history for trigger keys, honour
`selective`/`secondary_keys` and `constant` entries, order by `insertion_order`,
enforce `token_budget` by dropping the lowest `priority` first, optionally
re-scan matched content (bounded), and split into `before_char`/`after_char`.

§4.4 stacks a user-level world book underneath the character book; see
`select_stacked_entries`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from sparklchat.models.card import CharacterBook, CharacterBookEntry
from sparklchat.services.tokens import count_tokens

DEFAULT_SCAN_DEPTH = 4
DEFAULT_TOKEN_BUDGET = 512
# Absent `priority` values sort here so they are not the first to be dropped.
DEFAULT_PRIORITY = 100
# Bound on the recursive scanning pass count, to avoid trigger loops.
MAX_RECURSIVE_PASSES = 3


@dataclass(frozen=True, slots=True)
class MatchedEntries:
    before_char: list[CharacterBookEntry] = field(default_factory=list)
    after_char: list[CharacterBookEntry] = field(default_factory=list)

    @property
    def all(self) -> list[CharacterBookEntry]:
        return [*self.before_char, *self.after_char]


def select_entries(
    book: CharacterBook | None,
    history: Sequence[str],
    *,
    default_scan_depth: int = DEFAULT_SCAN_DEPTH,
    default_token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> MatchedEntries:
    """Return the entries to inject, split by their `position`."""
    if book is None or not book.entries:
        return MatchedEntries()

    scan_depth = int(book.scan_depth) if book.scan_depth else default_scan_depth
    budget = int(book.token_budget) if book.token_budget else default_token_budget

    recent = list(history)[-scan_depth:] if scan_depth > 0 else []
    haystack = "\n".join(recent)

    matched: list[CharacterBookEntry] = []
    seen: set[int] = set()

    def consider(text: str) -> list[CharacterBookEntry]:
        lower = text.lower()
        found: list[CharacterBookEntry] = []
        for index, entry in enumerate(book.entries):
            if index in seen or not entry.enabled:
                continue
            if _matches(entry, lower, text):
                seen.add(index)
                found.append(entry)
        return found

    matched.extend(consider(haystack))

    if book.recursive_scanning:
        pending = "\n".join(entry.content for entry in matched)
        for _ in range(MAX_RECURSIVE_PASSES):
            newly = consider(pending)
            if not newly:
                break
            matched.extend(newly)
            pending = "\n".join(entry.content for entry in newly)

    kept = _apply_budget(matched, budget)
    ordered = sorted(kept, key=lambda entry: entry.insertion_order)
    return MatchedEntries(
        before_char=[e for e in ordered if e.position != "after_char"],
        after_char=[e for e in ordered if e.position == "after_char"],
    )


def select_stacked_entries(
    character_book: CharacterBook | None,
    world_book: CharacterBook | None,
    history: Sequence[str],
    *,
    use_character_book: bool = True,
    use_world_book: bool = True,
    default_scan_depth: int = DEFAULT_SCAN_DEPTH,
    default_token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> MatchedEntries:
    """Match the character book and the world book, character book first.

    Each book honours its own `scan_depth` and `token_budget`. The character book
    takes precedence (PLAN §4.4): a world entry whose trigger keys collide with a
    selected character entry is dropped. Both books are on by default, and either
    can be switched off per session.
    """
    matched = (
        select_entries(
            character_book,
            history,
            default_scan_depth=default_scan_depth,
            default_token_budget=default_token_budget,
        )
        if use_character_book
        else MatchedEntries()
    )
    if not use_world_book or world_book is None:
        return matched

    world = select_entries(
        world_book,
        history,
        default_scan_depth=default_scan_depth,
        default_token_budget=default_token_budget,
    )
    character_keys = _normalized_keys(matched.all)
    extra = [entry for entry in world.all if not _normalized_keys([entry]) & character_keys]
    if not extra:
        return matched

    # Character entries come first, so a stable sort keeps them ahead on ties.
    ordered = sorted([*matched.all, *extra], key=lambda entry: entry.insertion_order)
    return MatchedEntries(
        before_char=[e for e in ordered if e.position != "after_char"],
        after_char=[e for e in ordered if e.position == "after_char"],
    )


def _normalized_keys(entries: Sequence[CharacterBookEntry]) -> set[str]:
    """Trigger keys compared case-insensitively, for precedence resolution."""
    return {key.strip().lower() for entry in entries for key in entry.keys if key.strip()}


def _matches(entry: CharacterBookEntry, lower: str, raw: str) -> bool:
    if entry.constant:
        return True
    if not entry.keys:
        return False
    haystack = raw if entry.case_sensitive else lower
    if not _contains(haystack, entry.keys, entry.case_sensitive):
        return False
    if entry.selective:
        # `selective` requires a hit from both lists.
        secondary = entry.secondary_keys or []
        if not secondary:
            return False
        return _contains(haystack, secondary, entry.case_sensitive)
    return True


def _contains(haystack: str, needles: Sequence[str], case_sensitive: bool) -> bool:
    for needle in needles:
        if not needle:
            continue
        if case_sensitive:
            if needle in haystack:
                return True
        elif needle.lower() in haystack:
            return True
    return False


def _apply_budget(entries: list[CharacterBookEntry], budget: int) -> list[CharacterBookEntry]:
    """Drop the lowest-priority entries until the content fits `budget`."""
    if budget <= 0:
        return entries

    total = sum(count_tokens(entry.content) for entry in entries)
    if total <= budget:
        return entries

    drop_order = sorted(
        range(len(entries)),
        key=lambda index: (
            entries[index].priority if entries[index].priority is not None else DEFAULT_PRIORITY,
            -index,
        ),
    )
    dropped: set[int] = set()
    for index in drop_order:
        if total <= budget:
            break
        total -= count_tokens(entries[index].content)
        dropped.add(index)
    return [entry for index, entry in enumerate(entries) if index not in dropped]
