"""CHARX package reading and writing."""

import io
import json
import zipfile

import pytest

from sparklchat.services.charx import (
    CARD_ENTRY,
    CharxError,
    is_charx,
    read_charx,
    write_charx,
)

CARD = {"spec": "chara_card_v3", "spec_version": "3.0", "data": {"name": "Haruhi"}}


def make_zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_is_charx_recognises_the_zip_magic() -> None:
    assert is_charx(write_charx(CARD))
    assert not is_charx(b"\x89PNG\r\n\x1a\n")


def test_round_trips_the_card_and_assets() -> None:
    assets = {
        "assets/icon/images/main.png": b"\x89PNG fake",
        "assets/background/other/bg.jpg": b"jpeg bytes",
    }
    package = read_charx(write_charx(CARD, assets))

    assert package.card == CARD
    assert package.assets == assets
    assert package.asset("assets/icon/images/main.png") == b"\x89PNG fake"
    assert package.asset("missing.png") is None


def test_round_trips_without_assets() -> None:
    package = read_charx(write_charx(CARD))
    assert package.card == CARD
    assert package.assets == {}


def test_reading_any_zip_with_a_root_card_json() -> None:
    raw = make_zip({CARD_ENTRY: json.dumps(CARD).encode(), "extra.txt": b"hi"})
    package = read_charx(raw)
    assert package.card == CARD
    assert package.assets == {"extra.txt": b"hi"}


def test_missing_card_json_is_rejected() -> None:
    raw = make_zip({"other.json": b"{}"})
    with pytest.raises(CharxError, match="no `card.json`"):
        read_charx(raw)


def test_card_json_must_be_a_json_object() -> None:
    raw = make_zip({CARD_ENTRY: b"[1, 2, 3]"})
    with pytest.raises(CharxError, match="must be a JSON object"):
        read_charx(raw)


def test_card_json_must_be_valid_json() -> None:
    raw = make_zip({CARD_ENTRY: b"{oops"})
    with pytest.raises(CharxError, match="not valid JSON"):
        read_charx(raw)


def test_non_zip_is_rejected() -> None:
    with pytest.raises(CharxError, match="not a valid CHARX"):
        read_charx(b"not a zip at all")


def test_encrypted_packages_are_rejected() -> None:
    raw = bytearray(write_charx(CARD))
    # Set the "encrypted" bit on the central directory entry.
    central = raw.index(b"PK\x01\x02")
    raw[central + 8] |= 0x1

    with pytest.raises(CharxError, match="encrypted"):
        read_charx(bytes(raw))


def test_write_rejects_unsafe_asset_paths() -> None:
    for path in ("../escape.png", "/absolute.png", "café.png", ""):
        with pytest.raises(CharxError):
            write_charx(CARD, {path: b"x"})


def test_written_package_names_are_ascii_and_relative() -> None:
    package = read_charx(write_charx(CARD, {"assets/icon/images/main.png": b"x"}))
    assert list(package.assets) == ["assets/icon/images/main.png"]
