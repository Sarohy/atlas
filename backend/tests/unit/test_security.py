"""Unit tests for password hashing utilities."""

from atlas.core.security import hash_password, verify_password


def test_hash_password_returns_non_plaintext_hash() -> None:
    """Hashed passwords should not equal the original plaintext."""
    password_hash = hash_password("admin@123")

    assert password_hash != "admin@123"
    assert password_hash.startswith("pbkdf2_sha256$")


def test_verify_password_accepts_matching_password() -> None:
    """verify_password returns True for a matching password."""
    password_hash = hash_password("admin@123")

    assert verify_password("admin@123", password_hash) is True


def test_verify_password_rejects_non_matching_password() -> None:
    """verify_password returns False for a non-matching password."""
    password_hash = hash_password("admin@123")

    assert verify_password("not-admin", password_hash) is False


def test_verify_password_rejects_invalid_hash_format() -> None:
    """verify_password returns False for malformed stored hashes."""
    assert verify_password("admin@123", "invalid-hash") is False
