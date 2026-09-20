"""Avatar file storage."""

from pathlib import Path
from uuid import uuid4

from sparklchat.config import get_settings
from sparklchat.services.images import to_webp


def save_avatar(data: bytes, suffix: str = ".png") -> str:
    """Write avatar bytes to the avatar directory and return the file name."""
    return _write(data, suffix)


def save_display_avatar(data: bytes) -> str | None:
    """Store the optimized WebP variant the UI loads, or None if unencodable.

    The original avatar stays untouched so exports keep the source image.
    """
    payload = to_webp(data)
    if payload is None:
        return None
    return _write(payload, ".webp")


def avatar_file(name: str) -> Path:
    """Resolve a stored avatar file name inside the avatar directory."""
    # `Path.name` keeps a stored value from escaping the directory.
    return get_settings().avatar_dir / Path(name).name


def delete_avatar(name: str | None) -> None:
    if not name:
        return
    avatar_file(name).unlink(missing_ok=True)


def _write(data: bytes, suffix: str) -> str:
    directory = get_settings().avatar_dir
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    (directory / filename).write_bytes(data)
    return filename
