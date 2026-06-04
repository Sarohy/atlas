"""Application configuration via Pydantic Settings."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so the server can be started from any cwd.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """All configuration is read from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    app_name: str = Field(default="atlas-backend")
    environment: str = Field(default="development")
    database_url: str = Field(default="postgresql+asyncpg://localhost:5432/atlas_dev")
    allowed_origins: str = Field(default="http://localhost:3000")

    # Polygon.io API key — required for F1 Momentum scoring
    polygon_api_key: str = Field(default="")

    # Alpha Vantage API key — required for F2 Earnings Quality and F5 Fundamental scoring
    # (INCOME_STATEMENT, EARNINGS, BALANCE_SHEET, CASH_FLOW, OVERVIEW endpoints)
    alphavantage_api_key: str = Field(default="")

    # Earnings Call Transcript API key — required for F2 Guidance Direction
    # and Backlog / Visibility scoring (FMP EARNINGS_CALL_TRANSCRIPT endpoint)
    earnings_transcript_api_key: str = Field(default="")

    # Benzinga API key — required for F3 Analyst Conviction scoring
    # (consensus-ratings and calendar/ratings endpoints)
    benzinga_api_key: str = Field(default="")

    # Unusual Whales API key — required for F4 Options Flow scoring
    # (flow-alerts, options-volume, darkpool endpoints)
    unusual_whales_api_key: str = Field(default="")

    # sec-api.io API key — required for F5 Fundamental Quality scoring
    # (Form 4 insider trading data via POST /insider-trading)
    sec_api_key: str = Field(default="")


def get_settings() -> Settings:
    """Return a Settings instance (cached via dependency injection in prod)."""
    return Settings()
