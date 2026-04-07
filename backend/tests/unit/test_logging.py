"""Unit tests for the structured logging module."""

import structlog

from atlas.core.logging import configure_logging, get_logger


def test_configure_logging_development() -> None:
    """configure_logging in development mode should not raise."""
    configure_logging("development")
    # After configuration the structlog config should be set
    assert structlog.is_configured()


def test_configure_logging_production() -> None:
    """configure_logging in production mode should not raise."""
    configure_logging("production")
    assert structlog.is_configured()


def test_get_logger_returns_bound_logger() -> None:
    """get_logger should return a usable structlog BoundLogger."""
    configure_logging("development")
    logger = get_logger("test")
    assert logger is not None
    # Should be able to log without raising
    logger.info("test log message", key="value")
