"""Helpers for building file downloads."""

import re

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def download_filename(name: str, extension: str) -> str:
    """Turn a title into a safe `Content-Disposition` filename."""
    slug = _UNSAFE.sub("-", name).strip("-")
    return f"{(slug or 'download')[:64]}.{extension}"


def attachment_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}
