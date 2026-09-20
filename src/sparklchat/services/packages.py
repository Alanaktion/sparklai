"""Stored card packages (CHARX archives or PNG cards) with binary assets.

A character's card JSON is the source of truth, but V3 cards can reference binary
assets (`embeded://…`). Keeping the package the card arrived in lets us serve
those assets and re-export a CHARX losslessly.
"""

from pathlib import Path
from uuid import uuid4

from sparklchat.config import get_settings


def save_package(data: bytes, suffix: str = ".charx") -> str:
    """Write package bytes to the package directory and return the file name."""
    directory = get_settings().package_dir
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    (directory / filename).write_bytes(data)
    return filename


def package_file(name: str) -> Path:
    """Resolve a stored package file name inside the package directory."""
    # `Path.name` keeps a stored value from escaping the directory.
    return get_settings().package_dir / Path(name).name


def package_bytes(name: str | None) -> bytes | None:
    if not name:
        return None
    path = package_file(name)
    return path.read_bytes() if path.is_file() else None


def delete_package(name: str | None) -> None:
    if not name:
        return
    package_file(name).unlink(missing_ok=True)
