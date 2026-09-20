"""Curly-braced macro syntaxes from the Character Card V3 spec.

`expand_macros` is what prompt assembly should use: it strips every macro the
spec forbids sending to the model. `match_text` is the same expansion except
that it can reveal `{{hidden_key:...}}` values, which lets a caller test text
against hidden keywords without leaking them into a prompt.
"""

import hashlib
import random
import re
from dataclasses import dataclass

# A braced macro (matched non-greedily) or one of the legacy bare spellings.
_MACRO = re.compile(
    r"\{\{(?P<body>.*?)\}\}|<(?P<legacy>char|bot|user)>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class MacroContext:
    character_name: str = "Character"
    user_name: str = "User"
    seed: str = ""


def expand_macros(text: str, context: MacroContext) -> str:
    """Expand every macro in `text`; hidden keys expand to an empty string."""
    return _substitute(text, context, include_hidden=False)


def match_text(text: str, context: MacroContext, *, include_hidden: bool = False) -> str:
    """Like `expand_macros`, but `{{hidden_key:...}}` yields its value when asked."""
    return _substitute(text, context, include_hidden=include_hidden)


def _substitute(text: str, context: MacroContext, *, include_hidden: bool) -> str:
    def replace(match: re.Match[str]) -> str:
        legacy = match.group("legacy")
        if legacy is not None:
            return context.user_name if legacy.lower() == "user" else context.character_name
        return _expand_body(match.group("body"), match.group(0), context, include_hidden)

    return _MACRO.sub(replace, text)


def _expand_body(body: str, matched: str, context: MacroContext, include_hidden: bool) -> str:
    """Dispatch on one macro's body; `matched` is returned verbatim when unknown."""
    if body.lstrip().startswith("//"):
        return ""  # `{{// ...}}` is a comment.
    name, _, rest = body.partition(":")
    name = name.strip().lower()

    if name == "char":
        return context.character_name
    if name == "user":
        return context.user_name
    if name == "random":
        values = _split_values(rest)
        return random.choice(values) if values else matched
    if name == "pick":
        values = _split_values(rest)
        return _pick(values, matched, context) if values else matched
    if name == "roll":
        sides = _die_sides(rest)
        return str(random.randint(1, sides)) if sides else matched
    if name == "reverse":
        return rest.strip()[::-1]
    if name == "hidden_key":
        return rest.strip() if include_hidden else ""
    if name == "comment":
        return ""
    return matched


def _split_values(raw: str) -> list[str]:
    """Split on unescaped commas, turning `\\,` into a literal comma.

    A single leading `:` is ignored so `{{pick::A,B}}` works like `{{pick:A,B}}`.
    Values are stripped, and empty ones are dropped (so `{{random:}}` is untouched).
    """
    if raw.startswith(":"):
        raw = raw[1:]
    values: list[str] = []
    current: list[str] = []
    escaped = False
    for char in raw:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ",":
            values.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if escaped:  # A lone trailing backslash is a literal backslash.
        current.append("\\")
    values.append("".join(current).strip())
    return [value for value in values if value]


def _pick(values: list[str], matched: str, context: MacroContext) -> str:
    """Choose deterministically from `values` for the same seed and macro text."""
    digest = hashlib.sha256(f"{context.seed}\x00{matched}".encode()).digest()
    return values[int.from_bytes(digest[:8], "big") % len(values)]


def _die_sides(raw: str) -> int:
    """Parse `6` or `d6`/`D6` into a positive die size, or `0` when invalid."""
    text = raw.strip()
    if text[:1] in ("d", "D"):
        text = text[1:]
    return int(text) if text.isascii() and text.isdigit() and int(text) > 0 else 0
