"""PNG `tEXt` chunk reading and writing.

The PNGs used as input here are assembled by an independent chunk builder, so a
mistake in the writer's CRC or layout handling is not masked by reusing its own
helpers.
"""

import base64
import json
import struct
import zlib

import pytest

from sparklchat.services.png import (
    PNG_SIGNATURE,
    PngError,
    blank_png,
    card_keyword,
    embed_card_json,
    is_png,
    read_asset_chunks,
    read_card_json,
)

IHDR_BYTES = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)


def build_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def build_text_chunk(keyword: str, text: str) -> bytes:
    payload = keyword.encode("latin-1") + b"\x00" + text.encode("latin-1")
    return build_chunk(b"tEXt", payload)


def build_png(*middle: bytes) -> bytes:
    return (
        PNG_SIGNATURE
        + build_chunk(b"IHDR", IHDR_BYTES)
        + b"".join(middle)
        + build_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00"))
        + build_chunk(b"IEND", b"")
    )


def parse_chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    """Independently split and CRC-check a PNG."""
    assert png.startswith(PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    offset = len(PNG_SIGNATURE)
    while offset < len(png):
        (length,) = struct.unpack_from(">I", png, offset)
        chunk_type = png[offset + 4 : offset + 8]
        data = png[offset + 8 : offset + 8 + length]
        (crc,) = struct.unpack_from(">I", png, offset + 8 + length)
        assert crc == zlib.crc32(chunk_type + data) & 0xFFFFFFFF, chunk_type
        chunks.append((chunk_type, data))
        offset += 12 + length
    return chunks


def encode(card: dict) -> str:
    return base64.b64encode(json.dumps(card).encode("utf-8")).decode("ascii")


def text_of(png: bytes, keyword: str) -> str | None:
    for chunk_type, data in parse_chunks(png):
        if chunk_type != b"tEXt":
            continue
        name, _, text = data.partition(b"\x00")
        if name.decode("latin-1").lower() == keyword.lower():
            return text.decode("latin-1")
    return None


def test_blank_png_is_a_valid_uncompressed_card_container() -> None:
    png = blank_png()
    assert is_png(png)
    types = [chunk_type for chunk_type, _ in parse_chunks(png)]
    assert types == [b"IHDR", b"IDAT", b"IEND"]
    with pytest.raises(PngError, match="no character card data"):
        read_card_json(png)


def test_embed_then_read_round_trips(v2_card: dict) -> None:
    png = embed_card_json(blank_png(), v2_card)
    assert read_card_json(png) == v2_card


def test_card_keyword_picks_ccv3_for_v3() -> None:
    assert card_keyword({"spec": "chara_card_v3"}) == "ccv3"
    assert card_keyword({"spec": "chara_card_v2"}) == "chara"
    assert card_keyword({"name": "V1"}) == "chara"


def test_embed_v3_card_under_the_ccv3_keyword() -> None:
    card = {"spec": "chara_card_v3", "spec_version": "3.0", "data": {"name": "V3"}}
    png = embed_card_json(blank_png(), card)

    assert text_of(png, "ccv3") is not None
    assert text_of(png, "chara") is None
    assert read_card_json(png) == card


def test_embed_clears_the_other_card_chunk() -> None:
    """A stale `ccv3` must not survive a V2 export (readers prefer it)."""
    v3 = {"spec": "chara_card_v3", "spec_version": "3.0", "data": {"name": "V3"}}
    png = embed_card_json(blank_png(), v3)
    assert text_of(png, "ccv3") is not None

    v2 = {"spec": "chara_card_v2", "spec_version": "2.0", "data": {"name": "V2"}}
    reexported = embed_card_json(png, v2)
    assert text_of(reexported, "ccv3") is None
    assert read_card_json(reexported) == v2


def test_embed_clears_a_stale_chara_when_writing_ccv3() -> None:
    v2 = {"spec": "chara_card_v2", "spec_version": "2.0", "data": {"name": "V2"}}
    png = embed_card_json(blank_png(), v2)

    v3 = {"spec": "chara_card_v3", "spec_version": "3.0", "data": {"name": "V3"}}
    reexported = embed_card_json(png, v3)
    assert text_of(reexported, "chara") is None
    assert read_card_json(reexported) == v3


def test_reads_asset_chunks_with_their_original_case() -> None:
    payload = base64.b64encode(b"fake png bytes").decode("ascii")
    png = build_png(
        build_text_chunk("chara-ext-asset_:assets/icon/images/Main.png", payload),
        build_text_chunk("chara-ext-asset_:assets/background/other/BG.jpg", payload),
        build_text_chunk("Comment", "not an asset"),
    )
    assets = read_asset_chunks(png)

    assert assets == {
        "assets/icon/images/Main.png": b"fake png bytes",
        "assets/background/other/BG.jpg": b"fake png bytes",
    }


def test_asset_chunks_skip_undecodable_payloads() -> None:
    png = build_png(build_text_chunk("chara-ext-asset_:broken.png", "!!!not base64!!!"))
    assert read_asset_chunks(png) == {}


def test_no_asset_chunks_yields_an_empty_map(v2_card: dict) -> None:
    assert read_asset_chunks(embed_card_json(blank_png(), v2_card)) == {}


def test_embed_inserts_after_ihdr_and_keeps_other_chunks() -> None:
    original = build_png(build_text_chunk("Comment", "hello"), build_text_chunk("Author", "me"))
    png = embed_card_json(original, {"name": "Haruhi"})

    chunks = parse_chunks(png)
    assert [chunk_type for chunk_type, _ in chunks][:3] == [b"IHDR", b"tEXt", b"tEXt"]
    # Unrelated text chunks survive verbatim.
    assert text_of(png, "comment") == "hello"
    assert text_of(png, "author") == "me"
    assert read_card_json(png) == {"name": "Haruhi"}


def test_embed_replaces_an_existing_card_chunk() -> None:
    original = build_png(build_text_chunk("chara", encode({"name": "Old"})))
    png = embed_card_json(original, {"name": "New"})

    card_chunks = [
        data
        for chunk_type, data in parse_chunks(png)
        if chunk_type == b"tEXt" and data.partition(b"\x00")[0].lower() == b"chara"
    ]
    assert len(card_chunks) == 1
    assert read_card_json(png) == {"name": "New"}


def test_read_prefers_ccv3_over_chara() -> None:
    """The spec says the V3 chunk wins when a file carries both."""
    png = build_png(
        build_text_chunk("ccv3", encode({"name": "V3"})),
        build_text_chunk("chara", encode({"name": "V2"})),
    )
    assert read_card_json(png) == {"name": "V3"}


def test_read_falls_back_to_chara() -> None:
    png = build_png(build_text_chunk("chara", encode({"name": "V2"})))
    assert read_card_json(png) == {"name": "V2"}


def test_keyword_matching_is_case_insensitive() -> None:
    png = build_png(build_text_chunk("Chara", encode({"name": "Haruhi"})))
    assert read_card_json(png) == {"name": "Haruhi"}


def test_reads_base64_without_padding() -> None:
    text = encode({"name": "Haruhi"})
    png = build_png(build_text_chunk("chara", text.rstrip("=")))
    assert read_card_json(png) == {"name": "Haruhi"}


def test_reads_line_wrapped_base64() -> None:
    text = encode({"name": "Haruhi"})
    wrapped = "\n".join(text[i : i + 16] for i in range(0, len(text), 16))
    png = build_png(build_text_chunk("chara", wrapped))
    assert read_card_json(png) == {"name": "Haruhi"}


def test_reads_raw_json_as_a_fallback() -> None:
    png = build_png(build_text_chunk("chara", json.dumps({"name": "Raw"})))
    assert read_card_json(png) == {"name": "Raw"}


def test_rejects_non_png() -> None:
    with pytest.raises(PngError, match="not a PNG"):
        read_card_json(b"not a png at all")


def test_rejects_corrupt_crc() -> None:
    png = bytearray(build_png(build_text_chunk("chara", encode({"name": "Haruhi"}))))
    png[-1] ^= 0xFF  # damage the IEND CRC
    with pytest.raises(PngError, match="bad CRC"):
        read_card_json(bytes(png))


def test_rejects_unreadable_card_payload() -> None:
    png = build_png(build_text_chunk("chara", "!!! not json !!!"))
    with pytest.raises(PngError, match="not valid JSON"):
        read_card_json(png)


def test_embed_requires_ihdr_and_iend() -> None:
    no_ihdr = PNG_SIGNATURE + build_chunk(b"IEND", b"")
    with pytest.raises(PngError, match="IHDR"):
        embed_card_json(no_ihdr, {"name": "Haruhi"})

    no_iend = PNG_SIGNATURE + build_chunk(b"IHDR", IHDR_BYTES)
    with pytest.raises(PngError, match="IEND"):
        embed_card_json(no_iend, {"name": "Haruhi"})
