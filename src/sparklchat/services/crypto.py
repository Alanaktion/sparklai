"""Symmetric encryption for provider API keys at rest."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from sparklchat.config import get_settings


class EncryptionError(Exception):
    """Raised when a value cannot be encrypted or decrypted."""


def _fernet() -> Fernet:
    settings = get_settings()
    if settings.encryption_key:
        key = settings.encryption_key.encode("utf-8")
    else:
        # Derive a stable key from SECRET_KEY so no extra setup is required.
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode("utf-8")).digest())
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise EncryptionError(
            "ENCRYPTION_KEY must be a valid Fernet key (44 url-safe base64 characters)"
        ) from exc


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise EncryptionError(
            "could not decrypt the stored value; was SECRET_KEY or ENCRYPTION_KEY changed?"
        ) from exc
