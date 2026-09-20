"""CHARX (`.charx`) packages.

A CHARX file is a zip holding the character card as `card.json` at the root,
plus the card's binary assets. Assets are addressed by `embeded://path` URIs
(note the spec's spelling, without a second `d`), and the path is case sensitive
and `/`-separated.

Only the pieces the spec names are interpreted here. Everything else in the zip
is preserved verbatim so an unchanged package can be written back out.
"""

import io
import json
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# Local file header signature; also the first bytes of every zip/CHARX.
ZIP_MAGIC = b"PK\x03\x04"
CARD_ENTRY = "card.json"
# Guard rails for untrusted packages.
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


class CharxError(ValueError):
    """Raised when a CHARX package cannot be read or is not valid."""


@dataclass(frozen=True, slots=True)
class CharxPackage:
    """A parsed CHARX file: the card plus its asset files."""

    card: dict[str, Any]
    # Asset path -> bytes, for every entry other than `card.json`.
    assets: dict[str, bytes] = field(default_factory=dict)

    def asset(self, path: str) -> bytes | None:
        return self.assets.get(path)


def is_charx(data: bytes) -> bool:
    return data.startswith(ZIP_MAGIC)


def read_charx(data: bytes) -> CharxPackage:
    """Parse a CHARX (or any zip with a root `card.json`)."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise CharxError("not a valid CHARX (zip) file") from exc

    with archive:
        if any(info.flag_bits & 0x1 for info in archive.infolist()):
            raise CharxError("CHARX file is encrypted, which is not supported")

        names = {info.filename for info in archive.infolist()}
        if CARD_ENTRY not in names:
            raise CharxError("CHARX file has no `card.json` at its root")

        try:
            raw_card = archive.read(CARD_ENTRY)
        except (RuntimeError, zipfile.BadZipFile) as exc:
            raise CharxError(f"could not read `card.json`: {exc}") from exc

        card = _parse_card_entry(raw_card)
        assets = _read_assets(archive)
    return CharxPackage(card=card, assets=assets)


def write_charx(card_json: dict[str, Any], assets: Mapping[str, bytes] | None = None) -> bytes:
    """Build a CHARX package containing `card_json` and `assets`.

    File names are validated to be relative, ASCII, and free of `..` segments, as
    the spec asks, so a package we write stays portable.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(CARD_ENTRY, _serialize(card_json))
        for path, payload in sorted((assets or {}).items()):
            archive.writestr(_safe_name(path), payload)
    return buffer.getvalue()


def _parse_card_entry(payload: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CharxError(f"`card.json` is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise CharxError("`card.json` must be a JSON object")
    return parsed


def _read_assets(archive: zipfile.ZipFile) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}
    total = 0
    for info in archive.infolist():
        if info.filename == CARD_ENTRY or info.is_dir():
            continue
        if info.file_size > MAX_ENTRY_BYTES:
            raise CharxError(f"asset {info.filename!r} is too large")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise CharxError("CHARX file's assets are too large")
        try:
            assets[info.filename] = archive.read(info)
        except (RuntimeError, zipfile.BadZipFile) as exc:
            raise CharxError(f"could not read asset {info.filename!r}: {exc}") from exc
    return assets


def _safe_name(path: str) -> str:
    """Reject names that could escape the archive or break portability."""
    cleaned = path.replace("\\", "/").lstrip("/")
    if not cleaned or cleaned != path:
        raise CharxError(f"invalid asset path {path!r}")
    if ".." in cleaned.split("/"):
        raise CharxError(f"invalid asset path {path!r}")
    if not cleaned.isascii():
        raise CharxError(f"asset path {path!r} must be ASCII")
    return cleaned


def _serialize(card_json: dict[str, Any]) -> str:
    return json.dumps(card_json, ensure_ascii=False, separators=(",", ":"))
