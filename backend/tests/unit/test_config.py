"""Unit tests for application configuration."""

import os

from atlas.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Settings should have sensible defaults when no overrides are present."""
    # Clear any env vars that might bleed in from the shell
    for key in ("APP_NAME", "ENVIRONMENT", "DATABASE_URL", "ALLOWED_ORIGINS"):
        os.environ.pop(key, None)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.app_name == "atlas-backend"
    assert settings.environment == "development"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.allowed_origins == "http://localhost:3000"


def test_settings_override_via_env(monkeypatch: object) -> None:
    """Settings can be overridden by environment variables."""
    os.environ["APP_NAME"] = "test-app"
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://localhost/test"
    os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,https://example.com"
    try:
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.app_name == "test-app"
        assert settings.environment == "test"
        assert settings.allowed_origins == "http://localhost:3000,https://example.com"
    finally:
        os.environ.pop("APP_NAME", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("ALLOWED_ORIGINS", None)


def test_get_settings_returns_settings_instance() -> None:
    """get_settings() must return a Settings object."""
    settings = get_settings()
    assert isinstance(settings, Settings)
