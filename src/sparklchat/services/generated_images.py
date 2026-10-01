"""Storage for images a ComfyUI provider generated for a chat message.

Mirrors `avatars.py`: files are kept byte-for-byte (ComfyUI already rendered
at the requested size, so there is nothing to re-encode or downscale) and
addressed by an opaque stored file name, never a caller-supplied path.
"""

from pathlib import Path
from uuid import uuid4

from sparklchat.config import get_settings

_EXTENSION_BY_CONTENT_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_CONTENT_TYPE_BY_EXTENSION = {ext: mime for mime, ext in _EXTENSION_BY_CONTENT_TYPE.items()}


def save_generated_image(data: bytes, content_type: str) -> str:
    """Write generated image bytes and return the stored file name."""
    suffix = _EXTENSION_BY_CONTENT_TYPE.get(content_type.lower().strip(), ".bin")
    directory = get_settings().generated_image_dir
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    (directory / filename).write_bytes(data)
    return filename


def generated_image_file(name: str) -> Path:
    """Resolve a stored file name inside the generated-image directory."""
    # `Path.name` keeps a stored value from escaping the directory.
    return get_settings().generated_image_dir / Path(name).name


def generated_image_content_type(name: str) -> str:
    return _CONTENT_TYPE_BY_EXTENSION.get(Path(name).suffix.lower(), "application/octet-stream")


def delete_generated_image(name: str | None) -> None:
    if not name:
        return
    generated_image_file(name).unlink(missing_ok=True)


def copy_generated_image(name: str | None) -> str | None:
    """Duplicate a stored file under a new name, e.g. when branching a session,
    so the copy can later be deleted without taking the original's file with it.

    Returns None (silently) if the source is already gone, matching how a
    missing image is otherwise treated as absent rather than an error.
    """
    if not name:
        return None
    source = generated_image_file(name)
    if not source.is_file():
        return None
    directory = get_settings().generated_image_dir
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{source.suffix}"
    (directory / filename).write_bytes(source.read_bytes())
    return filename
