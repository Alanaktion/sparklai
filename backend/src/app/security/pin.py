"""PBKDF2 PIN hashing, ported 1:1 from `src/lib/server/auth.ts` so existing `creators.password_hash`
values keep verifying: same iteration count, digest, key length, and `hex(salt):hex(hash)` format.
This is a straight port, not a hash-scheme upgrade — don't change the parameters below."""

import hashlib
import hmac
import os

_ITERATIONS = 100_000
_KEY_LENGTH = 32  # bytes
_DIGEST = "sha256"


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(_DIGEST, pin.encode(), salt, _ITERATIONS, dklen=_KEY_LENGTH)
    return f"{salt.hex()}:{derived.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split(":", 1)
    except ValueError:
        return False
    if not salt_hex or not hash_hex:
        return False
    salt = bytes.fromhex(salt_hex)
    derived = hashlib.pbkdf2_hmac(_DIGEST, pin.encode(), salt, _ITERATIONS, dklen=_KEY_LENGTH)
    return hmac.compare_digest(derived.hex(), hash_hex)
