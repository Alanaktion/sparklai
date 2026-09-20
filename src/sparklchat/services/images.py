"""Optimized WebP variants of uploaded images, for display.

Originals are always stored byte-for-byte so exports round-trip losslessly; the
UI loads a smaller WebP copy instead. Everything here is best-effort: when an
image cannot be decoded or re-encoded, the caller keeps using the original.
"""

from io import BytesIO

from PIL import Image, UnidentifiedImageError

# Longest edge of a stored display variant, in pixels. Avatars are never shown
# larger than this, so anything bigger is wasted bytes.
MAX_DISPLAY_SIZE = 512
WEBP_QUALITY = 82


def to_webp(data: bytes) -> bytes | None:
    """Return an optimized WebP copy of `data`, or None if it cannot be encoded.

    Animated images are flattened to their first frame, which is all the UI
    ever shows for an avatar or icon.
    """
    buffer = BytesIO()
    try:
        with Image.open(BytesIO(data)) as opened:
            frame = opened.convert(_mode_for(opened))
            frame.thumbnail((MAX_DISPLAY_SIZE, MAX_DISPLAY_SIZE), Image.Resampling.LANCZOS)
            frame.save(buffer, format="WEBP", quality=WEBP_QUALITY, method=6)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        return None
    return buffer.getvalue() or None


def _mode_for(image: Image.Image) -> str:
    """Keep transparency, flatten everything else to RGB for a smaller file."""
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        return "RGBA"
    return "RGB"
