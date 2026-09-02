"""Port of the two server-used helpers from `src/lib/index.ts` (a universal module, but these two
functions were only ever called from `+server.ts` chat prompt-building code)."""

from datetime import UTC, datetime


def now_str() -> str:
    """Port of `nowStr()`. Used to tell the chat-response persona what time it currently is."""
    now = datetime.now()
    hour = now.hour % 12 or 12
    ampm = "pm" if now.hour >= 12 else "am"
    return f"{hour} {ampm} on {now.strftime('%A')}"


def format_date(iso_date: str) -> str:
    """Port of `formatDate()`. `iso_date` is a SQLite `CURRENT_TIMESTAMP` string (naive UTC,
    space-separated) — mirrors the original's `` `${isoDate}Z` `` parse-as-UTC trick."""
    now = datetime.now(UTC)
    date = datetime.fromisoformat(iso_date.replace(" ", "T")).replace(tzinfo=UTC)
    seconds = (now - date).total_seconds()

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if seconds >= 120 else ''} ago"
    if seconds < 64800:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if seconds >= 3600 * 2 else ''} ago"
    return date.strftime("%a, %-d %b, %-I:%M %p")
