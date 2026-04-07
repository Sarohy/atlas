"""Password hashing helpers for authentication."""

from __future__ import annotations

import hashlib
import hmac
import secrets

HASH_ALGORITHM = "pbkdf2_sha256"
HASH_ITERATIONS = 120000
SALT_BYTES = 16
HASH_PARTS = 4


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 password hash."""
    salt = secrets.token_bytes(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, HASH_ITERATIONS)
    return (
        f"{HASH_ALGORITHM}${HASH_ITERATIONS}"
        f"${salt.hex()}${derived_key.hex()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    """Return True when the password matches the stored hash."""
    try:
        algorithm, iterations, salt_hex, expected_hash = password_hash.split("$", HASH_PARTS - 1)
    except ValueError:
        return False

    if algorithm != HASH_ALGORITHM:
        return False

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(salt_hex),
        int(iterations),
    )
    return hmac.compare_digest(derived_key.hex(), expected_hash)
