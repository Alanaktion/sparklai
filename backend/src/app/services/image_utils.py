"""Port of `src/lib/server/image-utils.ts`'s `toWebp()` — sharp → Pillow.

Converts arbitrary image bytes to compressed lossy WebP, resizing so the largest dimension is at
most MAX_DIMENSION. Never enlarges images. PNG text chunks (e.g. ComfyUI's "prompt"/"workflow",
read into Pillow's `Image.info` the same way sharp exposes them as `metadata.comments`) are mapped
to EXIF IFD0 fields with a matching "Prompt: " / "Workflow: " prefix; otherwise any EXIF already on
the input is carried through as-is.
"""

import io

from PIL import Image

MAX_DIMENSION = 1280
WEBP_QUALITY = 80

_EXIF_IMAGE_DESCRIPTION = 0x010E
_EXIF_MAKE = 0x010F


def to_webp(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as image:
        image.load()

        width, height = image.size
        scale = min(MAX_DIMENSION / width, MAX_DIMENSION / height, 1.0)
        if scale < 1.0:
            image = image.resize((round(width * scale), round(height * scale)), Image.LANCZOS)

        exif_bytes: bytes | None = None
        workflow = image.info.get("workflow")
        prompt = image.info.get("prompt")
        if workflow or prompt:
            exif = Image.Exif()
            if workflow:
                exif[_EXIF_IMAGE_DESCRIPTION] = f"Workflow: {workflow}"
            if prompt:
                exif[_EXIF_MAKE] = f"Prompt: {prompt}"
            exif_bytes = exif.tobytes()
        elif isinstance(image.info.get("exif"), bytes):
            exif_bytes = image.info["exif"]

        output = io.BytesIO()
        save_kwargs = {"format": "WEBP", "quality": WEBP_QUALITY}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        image.save(output, **save_kwargs)
        return output.getvalue()
