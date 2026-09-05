"""Small formatting helpers used when building chat prompts."""

from datetime import UTC, datetime


def now_str() -> str:
    """Used to tell the chat-response persona what time it currently is."""
    now = datetime.now()
    hour = now.hour % 12 or 12
    ampm = "pm" if now.hour >= 12 else "am"
    return f"{hour} {ampm} on {now.strftime('%A')}"


def format_date(iso_date: str) -> str:
    """`iso_date` is a SQLite `CURRENT_TIMESTAMP` string (naive UTC, space-separated) — parsed as
    UTC before diffing against now."""
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
