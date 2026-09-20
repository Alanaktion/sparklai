"""Minimal PNG `tEXt` chunk reader/writer for character cards.

Cards embed their JSON as base64 inside a `tEXt` chunk: `chara` for V1/V2 and
`ccv3` for V3. The spec says `ccv3` wins when a file carries both, so that is the
order we look in; `chara` is the fallback.

PNGs may also carry binary assets in `chara-ext-asset_:{path}` chunks. New
applications are told to prefer CHARX, so we only *read* these, never write them.

Only the chunks we care about are touched — every other chunk (including
unrelated `tEXt` metadata) is copied through byte-for-byte, and chunk CRCs are
verified on read.
"""

import base64
import binascii
import json
import struct
import zlib
from collections.abc import Iterator
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Ordered by preference: the spec says `ccv3` wins when both are present.
CARD_KEYWORDS = ("ccv3", "chara")
# Keyword prefix for a binary asset embedded in a `tEXt` chunk.
ASSET_PREFIX = "chara-ext-asset_:"
_TEXT_CHUNK = b"tEXt"


class PngError(ValueError):
    """Raised when a file is not a readable PNG or holds no usable card data."""


def is_png(data: bytes) -> bool:
    return data.startswith(PNG_SIGNATURE)


def iter_chunks(png: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Yield `(type, data)` for each chunk, verifying lengths and CRCs."""
    if not is_png(png):
        raise PngError("not a PNG file")

    offset = len(PNG_SIGNATURE)
    while offset + 8 <= len(png):
        (length,) = struct.unpack_from(">I", png, offset)
        chunk_type = png[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        if data_end + 4 > len(png):
            raise PngError("truncated PNG chunk")
        data = png[data_start:data_end]
        (expected_crc,) = struct.unpack_from(">I", png, data_end)
        actual_crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise PngError(f"bad CRC on {chunk_type!r} chunk")
        yield chunk_type, data
        offset = data_end + 4
        if chunk_type == b"IEND":
            return


def read_card_json(png: bytes) -> dict[str, Any]:
    """Extract the embedded character card object from a PNG."""
    texts = _text_chunks(png)
    for keyword in CARD_KEYWORDS:
        text = texts.get(keyword)
        if text is not None:
            return _decode(text)
    raise PngError("no character card data found in the PNG")


def read_asset_chunks(png: bytes) -> dict[str, bytes]:
    """Extract embedded binary assets, keyed by their `chara-ext-asset_:` path.

    Asset paths are case sensitive, so the raw keyword is read rather than the
    lowercased map `_text_chunks` builds.
    """
    assets: dict[str, bytes] = {}
    for chunk_type, data in iter_chunks(png):
        if chunk_type != _TEXT_CHUNK:
            continue
        keyword, _, text = data.partition(b"\x00")
        name = keyword.decode("latin-1")
        if not name.lower().startswith(ASSET_PREFIX):
            continue
        path = name[len(ASSET_PREFIX) :]
        if not path:
            continue
        try:
            assets[path] = _decode_base64(text.decode("latin-1"))
        except (binascii.Error, ValueError):
            continue
    return assets


def card_keyword(card_json: dict[str, Any]) -> str:
    """The chunk keyword a card should be embedded under: `ccv3` for V3."""
    return "ccv3" if card_json.get("spec") == "chara_card_v3" else "chara"


def embed_card_json(png: bytes, card_json: dict[str, Any], keyword: str | None = None) -> bytes:
    """Return `png` with `card_json` embedded in a `tEXt` chunk.

    The new chunk is placed directly after `IHDR`. Every existing card chunk
    (`chara` and `ccv3` alike) is replaced, so re-exporting a different format
    cannot leave a stale chunk behind that a reader would prefer. The keyword
    defaults to `ccv3` for V3 cards and `chara` otherwise.
    """
    if not is_png(png):
        raise PngError("not a PNG file")

    keyword = keyword or card_keyword(card_json)
    payload = base64.b64encode(_serialize(card_json).encode("utf-8"))
    new_chunk = _text_chunk(keyword, payload.decode("ascii"))

    out = bytearray(PNG_SIGNATURE)
    inserted = False
    saw_iend = False
    for chunk_type, data in iter_chunks(png):
        if chunk_type == b"IHDR":
            out += _chunk(b"IHDR", data)
            out += new_chunk
            inserted = True
            continue
        if chunk_type == _TEXT_CHUNK:
            name = data.partition(b"\x00")[0].decode("latin-1").lower()
            if name in CARD_KEYWORDS:
                continue  # superseded by the chunk we just inserted
        if chunk_type == b"IEND":
            saw_iend = True
        out += _chunk(chunk_type, data)

    if not inserted:
        raise PngError("PNG is missing an IHDR chunk")
    if not saw_iend:
        raise PngError("PNG is missing an IEND chunk")
    return bytes(out)


def blank_png(width: int = 1, height: int = 1) -> bytes:
    """A minimal transparent RGBA PNG, used when a character has no avatar."""
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x00\x00\x00\x00" * width
    pixels = zlib.compress(row * height)
    return PNG_SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", pixels) + _chunk(b"IEND", b"")


def _text_chunks(png: bytes) -> dict[str, str]:
    """Collect `tEXt` chunks keyed by lowercased keyword (first one wins)."""
    found: dict[str, str] = {}
    for chunk_type, data in iter_chunks(png):
        if chunk_type != _TEXT_CHUNK:
            continue
        keyword, _, text = data.partition(b"\x00")
        found.setdefault(keyword.decode("latin-1").lower(), text.decode("latin-1"))
    return found


def _decode(text: str) -> dict[str, Any]:
    """Decode base64-encoded JSON, tolerating missing padding."""
    try:
        raw = _decode_base64(text)
    except (binascii.Error, ValueError):
        raw = None

    if raw is not None:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    # A few tools embed the JSON directly rather than base64-encoding it.
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        raise PngError("character card data in the PNG is not valid JSON") from None
    if not isinstance(parsed, dict):
        raise PngError("character card data in the PNG is not a JSON object")
    return parsed


def _decode_base64(text: str) -> bytes:
    """Base64-decode chunk text, tolerating whitespace and missing padding."""
    compact = "".join(text.split())
    padded = compact + "=" * (-len(compact) % 4)
    return base64.b64decode(padded, validate=True)


def _serialize(card_json: dict[str, Any]) -> str:
    return json.dumps(card_json, ensure_ascii=False, separators=(",", ":"))


def _text_chunk(keyword: str, text: str) -> bytes:
    payload = keyword.encode("latin-1") + b"\x00" + text.encode("latin-1")
    return _chunk(_TEXT_CHUNK, payload)


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)
