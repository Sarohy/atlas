"""Unit tests for Position-related Pydantic schemas."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.schemas.ticker import (
    TickerCreate,
    TickerResponse,
    TickerUpdate,
    TickerSearchResult,
)

# ── TickerCreate ────────────────────────────────────────────────────────────


def test_ticker_create_valid() -> None:
    """TickerCreate accepts a valid ticker, company name, and positive shares."""
    data = TickerCreate(ticker="AAPL", company_name="Apple Inc.", shares=Decimal("150.5"))
    assert data.ticker == "AAPL"
    assert data.shares == Decimal("150.5")


def test_ticker_create_coerces_ticker_to_uppercase() -> None:
    """TickerCreate normalises ticker to upper-case."""
    data = TickerCreate(ticker="aapl", company_name="Apple Inc.", shares=Decimal("10"))
    assert data.ticker == "AAPL"


def test_ticker_create_rejects_zero_shares() -> None:
    """TickerCreate rejects zero or negative share counts."""
    with pytest.raises(ValidationError):
        TickerCreate(ticker="AAPL", company_name="Apple Inc.", shares=Decimal("0"))


def test_ticker_create_rejects_negative_shares() -> None:
    """TickerCreate rejects negative share counts."""
    with pytest.raises(ValidationError):
        TickerCreate(ticker="AAPL", company_name="Apple Inc.", shares=Decimal("-5"))


def test_ticker_create_rejects_empty_ticker() -> None:
    """TickerCreate rejects an empty ticker string."""
    with pytest.raises(ValidationError):
        TickerCreate(ticker="", company_name="Apple Inc.", shares=Decimal("10"))


def test_ticker_create_rejects_empty_company_name() -> None:
    """TickerCreate rejects a blank company name."""
    with pytest.raises(ValidationError):
        TickerCreate(ticker="AAPL", company_name="", shares=Decimal("10"))


# ── TickerUpdate ────────────────────────────────────────────────────────────


def test_ticker_update_valid() -> None:
    """TickerUpdate accepts a positive share count."""
    data = TickerUpdate(shares=Decimal("200"))
    assert data.shares == Decimal("200")


def test_ticker_update_rejects_non_positive_shares() -> None:
    """TickerUpdate rejects zero or negative shares."""
    with pytest.raises(ValidationError):
        TickerUpdate(shares=Decimal("0"))


# ── TickerResponse ──────────────────────────────────────────────────────────


def test_ticker_response_from_orm_fields() -> None:
    """TickerResponse can be constructed from ORM-like field values."""
    now = datetime.now(tz=UTC)
    resp = TickerResponse(
        id=1,
        ticker="MSFT",
        company_name="Microsoft Corporation",
        shares=Decimal("50"),
        created_at=now,
        updated_at=now,
    )
    assert resp.id == 1
    assert resp.ticker == "MSFT"


# ── TickerSearchResult ────────────────────────────────────────────────────────


def test_ticker_search_result_valid() -> None:
    """TickerSearchResult parses a typical Polygon API result."""
    result = TickerSearchResult(
        ticker="NVDA",
        name="NVIDIA Corporation",
        market="stocks",
        type="CS",
    )
    assert result.ticker == "NVDA"
    assert result.name == "NVIDIA Corporation"
