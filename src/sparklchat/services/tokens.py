"""Token counting.

Pluggable: `tiktoken` gives real counts when it is installed and its BPE data is
available (it is downloaded once and cached), otherwise a character-based
estimate keeps budgeting working offline.
"""

from functools import lru_cache
from typing import Any

from sparklchat.config import get_settings

# Rough average for English prose; only used by the fallback.
_CHARS_PER_TOKEN = 4


def count_tokens(text: str) -> int:
    """Approximate the token length of `text`."""
    if not text:
        return 0
    if get_settings().tokenizer != "heuristic":
        encoding = _encoding()
        if encoding is not None:
            return len(encoding.encode(text, disallowed_special=()))
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


@lru_cache(maxsize=1)
def _encoding() -> Any | None:
    """Return the tiktoken encoding, or `None` when it is unavailable."""
    try:
        import tiktoken
    except ImportError:
        return None
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        # Offline or a corrupted cache: fall back to the estimate.
        return None
