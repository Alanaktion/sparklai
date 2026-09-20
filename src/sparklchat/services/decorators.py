"""Character Card V3 lorebook entry "decorators".

Decorators are declared one per line at the top of a lorebook entry's `content`,
prefixed with `@@`. A line prefixed with `@@@` is a fallback for the decorator it
immediately follows: when the app does not recognise the primary name, each
fallback is tried in order and the first recognised name is selected.

Only the first decorator of a given name is applied, except `additional_keys`
(and `disable_ui_prompt`), which accumulate. Every decorator line is removed
from the content, recognised or not, so the remainder can be sent to the model.
"""

import re
from dataclasses import dataclass

_ROLES = frozenset({"system", "user", "assistant"})

_INTEGER_NAMES = frozenset(
    {
        "activate_only_after",
        "activate_only_every",
        "depth",
        "instruct_depth",
        "reverse_depth",
        "reverse_instruct_depth",
        "scan_depth",
        "instruct_scan_depth",
        "is_greeting",
    }
)
_FLAG_NAMES = frozenset(
    {
        "keep_activate_after_match",
        "dont_activate_after_match",
        "ignore_on_max_context",
        "dont_activate",
        "activate",
    }
)
_STRING_NAMES = frozenset({"role", "position", "is_user_icon"})
# Recognised names handled outside the generic first-occurrence-wins path.
_ACCUMULATING_NAMES = frozenset({"additional_keys", "disable_ui_prompt"})
_RECOGNIZED = _INTEGER_NAMES | _FLAG_NAMES | _STRING_NAMES | _ACCUMULATING_NAMES | {"exclude_keys"}

_NAME_RE = re.compile(r"[A-Za-z_]*")
_INT_RE = re.compile(r"[+-]?[0-9]+")

# Distinguishes an invalid value from a legitimately parsed one.
_INVALID = object()


@dataclass(frozen=True, slots=True)
class Decorators:
    activate_only_after: int | None = None
    activate_only_every: int | None = None
    keep_activate_after_match: bool = False
    dont_activate_after_match: bool = False
    depth: int | None = None
    instruct_depth: int | None = None
    reverse_depth: int | None = None
    reverse_instruct_depth: int | None = None
    role: str | None = None
    scan_depth: int | None = None
    instruct_scan_depth: int | None = None
    is_greeting: int | None = None
    position: str | None = None
    ignore_on_max_context: bool = False
    additional_keys: tuple[tuple[str, ...], ...] = ()
    exclude_keys: tuple[str, ...] = ()
    is_user_icon: str | None = None
    dont_activate: bool = False
    activate: bool = False
    disable_ui_prompt: tuple[str, ...] = ()


def parse_decorators(content: str) -> tuple[Decorators, str]:
    """Return (decorators, content with decorator lines removed)."""
    kept: list[str] = []
    values: dict[str, object] = {}
    seen: set[str] = set()
    additional_keys: list[tuple[str, ...]] = []
    ui_prompts: list[str] = []

    lines = content.split("\n")
    index = 0
    while index < len(lines):
        if not _is_decorator_line(lines[index]):
            kept.append(lines[index])
            index += 1
            continue

        # A chain is one primary decorator plus the `@@@` lines that directly
        # follow it; a plain `@@` line begins the next chain.
        chain = [_split_decorator(lines[index])]
        index += 1
        while index < len(lines) and _is_fallback_line(lines[index]):
            chain.append(_split_decorator(lines[index]))
            index += 1

        selected = next((item for item in chain if item[0] in _RECOGNIZED), None)
        if selected is None:
            continue
        name, value = selected

        if name == "additional_keys":
            additional_keys.append(tuple(_split_list(value)))
            continue
        if name == "disable_ui_prompt":
            if value:
                ui_prompts.append(value)
            continue
        if name in seen:
            continue
        # The name was selected, so a later chain cannot reconsider this decorator.
        seen.add(name)
        parsed = _parse_value(name, value)
        if parsed is not _INVALID:
            values[name] = parsed

    values["additional_keys"] = tuple(additional_keys)
    values["disable_ui_prompt"] = tuple(ui_prompts)
    return Decorators(**values), _trim_edges(kept)


def strip_decorators(content: str) -> str:
    """Return content with all decorator lines removed."""
    return parse_decorators(content)[1]


def _parse_value(name: str, value: str) -> object:
    if name in _INTEGER_NAMES:
        return int(value) if _INT_RE.fullmatch(value) else _INVALID
    if name in _FLAG_NAMES:
        # Flags take no value; a stray value makes the decorator invalid.
        return True if not value else _INVALID
    if name == "role":
        role = value.lower()
        return role if role in _ROLES else _INVALID
    if name in ("position", "is_user_icon"):
        return value if value else _INVALID
    if name == "exclude_keys":
        return tuple(_split_list(value))
    return _INVALID


def _split_decorator(line: str) -> tuple[str, str]:
    """Split a decorator line into its lowercased name and value."""
    body = line.strip().lstrip("@")
    match = _NAME_RE.match(body)
    name = match.group(0) if match else ""
    return name.lower(), body[len(name) :].strip()


def _split_list(value: str) -> list[str]:
    """Split a comma-separated value, honouring backslash-escaped commas."""
    parts: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and value[index + 1 : index + 2] == ",":
            current.append(",")
            index += 2
            continue
        if char == ",":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
        index += 1
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def _is_decorator_line(line: str) -> bool:
    return line.strip().startswith("@@")


def _is_fallback_line(line: str) -> bool:
    return line.strip().startswith("@@@")


def _trim_edges(lines: list[str]) -> str:
    """Drop whitespace-only edge lines, preserving the remaining structure."""
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])
