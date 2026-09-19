"""Fernet encryption used for provider API keys at rest."""

import pytest
from cryptography.fernet import Fernet

from sparklchat.config import get_settings
from sparklchat.services.crypto import EncryptionError, decrypt, encrypt


def test_round_trip() -> None:
    token = encrypt("sk-secret-value")
    assert token != "sk-secret-value"
    assert decrypt(token) == "sk-secret-value"


def test_ciphertext_differs_per_call() -> None:
    assert encrypt("same input") != encrypt("same input")


def test_explicit_key_is_used(monkeypatch) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    try:
        token = encrypt("sk-secret-value")
    finally:
        get_settings.cache_clear()
    assert Fernet(key.encode()).decrypt(token.encode()).decode() == "sk-secret-value"


def test_invalid_explicit_key_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", "definitely-not-a-fernet-key")
    get_settings.cache_clear()
    try:
        with pytest.raises(EncryptionError, match="ENCRYPTION_KEY"):
            encrypt("sk-secret-value")
    finally:
        get_settings.cache_clear()


def test_decrypt_with_a_different_key_fails_clearly(monkeypatch) -> None:
    token = encrypt("sk-secret-value")

    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    try:
        with pytest.raises(EncryptionError, match="could not decrypt"):
            decrypt(token)
    finally:
        get_settings.cache_clear()
