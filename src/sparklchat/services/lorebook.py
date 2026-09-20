"""Character book (lorebook) matching.

Implements PLAN §4.3 plus the Character Card V3 additions: `use_regex` keys,
entry decorators (`@@…` lines parsed by `services.decorators`), and recursive
scanning that can see `{{hidden_key:…}}` values.

`select_entries` returns entries split by their `position`. Entries carrying a
`@@depth` decorator (with no `@@position`) land in the `chat` bucket instead, for
prompt assembly to interleave into the message log.

§4.4 stacks a user-level world book underneath the character book; see
`select_stacked_entries`.
"""

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sparklchat.models.card import CharacterBook, CharacterBookEntry
from sparklchat.services.decorators import Decorators, parse_decorators
from sparklchat.services.macros import MacroContext, match_text
from sparklchat.services.tokens import count_tokens

DEFAULT_SCAN_DEPTH = 4
DEFAULT_TOKEN_BUDGET = 512
# Absent `priority` values sort here so they are not the first to be dropped.
DEFAULT_PRIORITY = 100
# Bound on the recursive scanning pass count, to avoid trigger loops.
MAX_RECURSIVE_PASSES = 3

# A `/pattern/flags` regex literal, as the spec's "regex pattern" definition.
_REGEX_LITERAL = re.compile(r"^/(?P<body>.*)/(?P<flags>[a-z]*)$", re.DOTALL)
_REGEX_FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}


@dataclass(frozen=True, slots=True)
class MatchContext:
    """Everything outside the book that can influence whether an entry matches.

    All fields are optional; the defaults keep `select_entries` behaving like a
    plain "does the recent history mention this key" scan.
    """

    history: tuple[str, ...] = ()
    # Number of assistant turns in the chat log, for `@@activate_only_after` and
    # `@@activate_only_every`.
    assistant_count: int = 0
    # Total tokens in the untruncated context, for `@@ignore_on_max_context`.
    token_count: int = 0
    max_context_tokens: int | None = None
    # Active greeting index (0 = `first_mes`), for `@@is_greeting`.
    greeting_index: int | None = None
    # Active user icon name, for `@@is_user_icon`.
    user_icon: str | None = None
    # How many times each entry has matched in previous turns, for
    # `@@keep_activate_after_match` / `@@dont_activate_after_match`.
    activation_counts: Mapping[str, int] = field(default_factory=dict)
    macro_context: MacroContext = field(default_factory=MacroContext)

    @property
    def at_max_context(self) -> bool:
        if self.max_context_tokens is None:
            return False
        return self.token_count >= self.max_context_tokens


@dataclass(frozen=True, slots=True)
class MatchedEntry:
    """An entry selected for injection, with its decorators already parsed."""

    entry: CharacterBookEntry
    decorators: Decorators
    # Entry content with the decorator lines removed.
    content: str
    # Stable identifier used for cross-turn activation bookkeeping.
    key: str

    @property
    def keys(self) -> list[str]:
        return self.entry.keys

    @property
    def insertion_order(self) -> int | float:
        return self.entry.insertion_order

    @property
    def priority(self) -> int | float | None:
        return self.entry.priority

    @property
    def position(self) -> str | None:
        return self.entry.position


@dataclass(frozen=True, slots=True)
class MatchedEntries:
    before_char: list[MatchedEntry] = field(default_factory=list)
    after_char: list[MatchedEntry] = field(default_factory=list)
    # Entries positioned inside the chat log by `@@depth`.
    chat: list[MatchedEntry] = field(default_factory=list)

    @property
    def all(self) -> list[MatchedEntry]:
        return [*self.before_char, *self.after_char, *self.chat]

    def __bool__(self) -> bool:
        return bool(self.before_char or self.after_char or self.chat)


def select_entries(
    book: CharacterBook | None,
    history: Sequence[str],
    *,
    context: MatchContext | None = None,
    matched_keys: set[str] | None = None,
    default_scan_depth: int = DEFAULT_SCAN_DEPTH,
    default_token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> MatchedEntries:
    """Return the entries to inject, split by where they belong.

    `matched_keys`, when given, collects the identifiers of every entry that
    matched so a caller can persist activation counts for the next turn.
    """
    if book is None or not book.entries:
        return MatchedEntries()

    ctx = context or MatchContext(history=tuple(history))
    book_depth = int(book.scan_depth) if book.scan_depth else default_scan_depth
    budget = int(book.token_budget) if book.token_budget else default_token_budget

    prepared = [_prepare(entry) for entry in book.entries]
    matched: list[MatchedEntry] = []
    seen: set[int] = set()

    def consider(pending: str | None) -> list[MatchedEntry]:
        """Scan the history (or the recursive `pending` text) for new matches."""
        found: list[MatchedEntry] = []
        for index, item in enumerate(prepared):
            if index in seen or not item.entry.enabled:
                continue
            gate = _gate(item, ctx)
            if gate == "skip":
                continue
            haystack = (
                _history_haystack(ctx, book_depth, item.decorators)
                if pending is None
                else match_text(pending, ctx.macro_context, include_hidden=True)
            )
            if gate == "match" or _triggers(item, haystack):
                seen.add(index)
                found.append(item)
        return found

    matched.extend(consider(None))

    if book.recursive_scanning:
        pending = "\n".join(item.content for item in matched)
        for _ in range(MAX_RECURSIVE_PASSES):
            newly = consider(pending)
            if not newly:
                break
            matched.extend(newly)
            pending = "\n".join(item.content for item in newly)

    if matched_keys is not None:
        matched_keys.update(item.key for item in matched)

    kept = _apply_budget(matched, budget)
    ordered = sorted(kept, key=lambda item: item.insertion_order)
    return _split(ordered)


def select_stacked_entries(
    character_book: CharacterBook | None,
    world_book: CharacterBook | None,
    history: Sequence[str],
    *,
    context: MatchContext | None = None,
    matched_keys: set[str] | None = None,
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
    return merge_matched(
        [
            select_entries(
                character_book,
                history,
                context=context,
                matched_keys=matched_keys,
                default_scan_depth=default_scan_depth,
                default_token_budget=default_token_budget,
            )
            if use_character_book
            else MatchedEntries(),
            select_entries(
                world_book,
                history,
                context=context,
                matched_keys=matched_keys,
                default_scan_depth=default_scan_depth,
                default_token_budget=default_token_budget,
            )
            if use_world_book
            else MatchedEntries(),
        ]
    )


def merge_matched(groups: Sequence[MatchedEntries]) -> MatchedEntries:
    """Combine matched entries, resolving key collisions in favour of earlier groups.

    Used to stack books: the acting character's book first, then the other cast
    members', then the user's world book. Entries are re-sorted by
    `insertion_order`, with earlier groups winning ties.
    """
    groups = [group for group in groups if group.all]
    if not groups:
        return MatchedEntries()

    seen = _normalized_keys(groups[0].all)
    merged = list(groups[0].all)
    for group in groups[1:]:
        for item in group.all:
            keys = _normalized_keys([item])
            # Constant entries have no keys, so they never collide.
            if keys.intersection(seen):
                continue
            seen |= keys
            merged.append(item)

    ordered = sorted(merged, key=lambda item: item.insertion_order)
    return _split(ordered)


def entry_key(entry: CharacterBookEntry) -> str:
    """A stable identifier for activation bookkeeping.

    `id`/`name`/`comment` alone can collide across books, so the content and keys
    are hashed in to keep the identifier unique and reproducible.
    """
    label = entry.id if entry.id is not None else entry.name or entry.comment or ""
    digest = hashlib.sha1(("\x00".join([*entry.keys, entry.content])).encode("utf-8")).hexdigest()[
        :10
    ]
    return f"{label}#{digest}"


def _prepare(entry: CharacterBookEntry) -> MatchedEntry:
    decorators, content = parse_decorators(entry.content)
    return MatchedEntry(
        entry=entry,
        decorators=decorators,
        content=content,
        key=entry_key(entry),
    )


def _split(entries: Sequence[MatchedEntry]) -> MatchedEntries:
    """Route entries to the bucket their decorators/position ask for."""
    before: list[MatchedEntry] = []
    after: list[MatchedEntry] = []
    chat: list[MatchedEntry] = []
    for item in entries:
        decorators = item.decorators
        if decorators.depth is not None and decorators.position is None:
            chat.append(item)
        elif item.entry.position == "after_char":
            after.append(item)
        else:
            before.append(item)
    return MatchedEntries(before_char=before, after_char=after, chat=chat)


def _normalized_keys(entries: Sequence[MatchedEntry]) -> set[str]:
    """Trigger keys compared case-insensitively, for precedence resolution."""
    return {key.strip().lower() for item in entries for key in item.keys if key.strip()}


def _history_haystack(ctx: MatchContext, book_depth: int, decorators: Decorators) -> str:
    """The history text an entry is matched against.

    `@@scan_depth` overrides the book's depth for this entry. The `instruct_*`
    variants target non-chat contexts, so they are ignored here (the spec asks us
    to ignore them when the context is chat-based).
    """
    depth = decorators.scan_depth if decorators.scan_depth is not None else book_depth
    if depth <= 0:
        return ""
    recent = ctx.history[-depth:]
    return "\n".join(match_text(text, ctx.macro_context) for text in recent)


def _gate(item: MatchedEntry, ctx: MatchContext) -> str:
    """Decide whether decorators force a match, forbid one, or leave it to keys.

    Returns `"match"` (inject regardless of keys), `"skip"` (never inject), or
    `"keys"` (inject only when the entry's keys appear in the scanned text).
    """
    decorators = item.decorators
    prior = ctx.activation_counts.get(item.key, 0)

    if decorators.dont_activate and not decorators.activate:
        return "skip"
    if decorators.activate:
        return "match"
    if decorators.keep_activate_after_match and prior >= 2:
        return "match"
    if decorators.dont_activate_after_match and prior >= 2:
        return "skip"
    if decorators.is_greeting is not None and ctx.greeting_index != decorators.is_greeting:
        return "skip"
    if decorators.is_user_icon is not None and ctx.user_icon != decorators.is_user_icon:
        return "skip"
    if decorators.ignore_on_max_context and ctx.at_max_context:
        return "skip"
    if (
        decorators.activate_only_after is not None
        and ctx.assistant_count < decorators.activate_only_after
    ):
        return "skip"
    every = decorators.activate_only_every
    if every is not None and every > 0 and ctx.assistant_count % every != 0:
        return "skip"
    return "keys"


def _triggers(item: MatchedEntry, haystack: str) -> bool:
    """Whether the entry's keys (and decorator keys) appear in `haystack`."""
    entry = item.entry
    decorators = item.decorators

    if entry.use_regex:
        # `constant` and `secondary_keys` are ignored under `use_regex`; the
        # decorator's extra patterns act as alternative triggers.
        patterns = [*entry.keys, *[key for group in decorators.additional_keys for key in group]]
        return _regex_any(patterns, haystack)

    if decorators.exclude_keys and _contains(
        haystack, decorators.exclude_keys, entry.case_sensitive
    ):
        return False

    # `constant` matches regardless of `keys` and `secondary_keys`.
    if entry.constant:
        return True

    triggers = [*entry.keys, *[key for group in decorators.additional_keys for key in group]]
    if not _contains(haystack, triggers, entry.case_sensitive):
        return False
    if entry.selective:
        # `selective` requires a hit from both lists.
        secondary = entry.secondary_keys or []
        if not secondary:
            return False
        if not _contains(haystack, secondary, entry.case_sensitive):
            return False
    return True


def _contains(haystack: str, needles: Sequence[str], case_sensitive: bool) -> bool:
    if not haystack:
        return False
    if not case_sensitive:
        haystack = haystack.lower()
    for needle in needles:
        if not needle:
            continue
        if (needle if case_sensitive else needle.lower()) in haystack:
            return True
    return False


def _regex_any(patterns: Sequence[str], haystack: str) -> bool:
    """True when any pattern matches; any invalid pattern makes the entry miss."""
    if not patterns:
        return False
    matched = False
    for pattern in patterns:
        if not pattern:
            continue
        compiled = _compile_pattern(pattern)
        if compiled is None:
            # The spec says an entry with invalid regex keys never matches.
            return False
        if compiled.search(haystack):
            matched = True
    return matched


def _compile_pattern(pattern: str) -> re.Pattern[str] | None:
    """Compile a raw pattern or the spec's `/pattern/flags` literal."""
    flags = 0
    body = pattern
    literal = _REGEX_LITERAL.match(pattern)
    if literal:
        body = literal.group("body")
        for flag in literal.group("flags"):
            flags |= _REGEX_FLAGS.get(flag, 0)
    try:
        return re.compile(body, flags)
    except re.error:
        return None


def _apply_budget(entries: list[MatchedEntry], budget: int) -> list[MatchedEntry]:
    """Drop the lowest-priority entries until the content fits `budget`.

    Entries marked `@@ignore_on_max_context` are never dropped by the budget.
    When no entry declares a `priority`, the spec allows falling back to
    `insertion_order` (the earliest entries are dropped first).
    """
    if budget <= 0:
        return entries

    total = sum(count_tokens(item.content) for item in entries)
    if total <= budget:
        return entries

    order = _drop_order(entries)
    dropped: set[int] = set()
    for index in order:
        if total <= budget:
            break
        if entries[index].decorators.ignore_on_max_context:
            continue
        total -= count_tokens(entries[index].content)
        dropped.add(index)
    return [entry for index, entry in enumerate(entries) if index not in dropped]


def _drop_order(entries: list[MatchedEntry]) -> list[int]:
    has_priority = any(item.priority is not None for item in entries)
    if has_priority:
        return sorted(
            range(len(entries)),
            key=lambda index: (
                entries[index].priority
                if entries[index].priority is not None
                else DEFAULT_PRIORITY,
                -index,
            ),
        )
    return sorted(
        range(len(entries)),
        key=lambda index: (entries[index].insertion_order, -index),
    )
