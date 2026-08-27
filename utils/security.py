"""Password hashing using stdlib PBKDF2-HMAC (no native-build dependency,
avoids bcrypt wheel issues on Windows). Good enough for an SIH prototype;
a production deployment should still consider argon2/bcrypt behind a
proper auth provider.
"""
from __future__ import annotations

import hashlib
import hmac
import os

_ITERATIONS = 200_000
_ALGO = "sha256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(actual, expected)
