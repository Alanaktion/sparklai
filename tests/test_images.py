"""The WebP display-variant encoder."""

from io import BytesIO

from PIL import Image

from sparklchat.services.images import MAX_DISPLAY_SIZE, to_webp


def make_png(width: int, height: int, mode: str = "RGB") -> bytes:
    buffer = BytesIO()
    Image.new(mode, (width, height), (200, 40, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_returns_none_for_bytes_that_are_not_images() -> None:
    assert to_webp(b"just some text") is None


def test_returns_none_for_a_truncated_image() -> None:
    assert to_webp(make_png(8, 8)[:16]) is None


def test_encodes_a_webp_variant() -> None:
    payload = to_webp(make_png(64, 64))
    assert payload is not None
    assert payload[:4] == b"RIFF"
    assert payload[8:12] == b"WEBP"


def test_downscales_to_the_display_size() -> None:
    payload = to_webp(make_png(1200, 600))
    assert payload is not None
    with Image.open(BytesIO(payload)) as image:
        assert image.size == (MAX_DISPLAY_SIZE, MAX_DISPLAY_SIZE // 2)


def test_does_not_upscale_small_images() -> None:
    payload = to_webp(make_png(24, 24))
    assert payload is not None
    with Image.open(BytesIO(payload)) as image:
        assert image.size == (24, 24)


def test_keeps_transparency() -> None:
    buffer = BytesIO()
    Image.new("RGBA", (32, 32), (200, 40, 90, 128)).save(buffer, format="PNG")
    payload = to_webp(buffer.getvalue())
    assert payload is not None
    with Image.open(BytesIO(payload)) as image:
        assert image.mode == "RGBA"


def test_flattens_an_animated_gif_to_the_first_frame() -> None:
    buffer = BytesIO()
    frames = [Image.new("RGB", (32, 32), color) for color in ((255, 0, 0), (0, 0, 255))]
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:], duration=100)

    payload = to_webp(buffer.getvalue())
    assert payload is not None
    with Image.open(BytesIO(payload)) as image:
        assert image.size == (32, 32)
