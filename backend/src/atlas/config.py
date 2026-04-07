"""Application configuration via Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration is read from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = Field(default="atlas-backend")
    environment: str = Field(default="development")
    database_url: str = Field(default="postgresql+asyncpg://localhost:5432/atlas_dev")


def get_settings() -> Settings:
    """Return a Settings instance (cached via dependency injection in prod)."""
    return Settings()
