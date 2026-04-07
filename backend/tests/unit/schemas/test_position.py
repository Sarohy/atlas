"""Unit tests for Position-related Pydantic schemas."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.schemas.position import (
    PositionCreate,
    PositionResponse,
    PositionUpdate,
    TickerSearchResult,
)

# ── PositionCreate ────────────────────────────────────────────────────────────


def test_position_create_valid() -> None:
    """PositionCreate accepts a valid ticker, company name, and positive shares."""
    data = PositionCreate(ticker="AAPL", company_name="Apple Inc.", shares=Decimal("150.5"))
    assert data.ticker == "AAPL"
    assert data.shares == Decimal("150.5")


def test_position_create_coerces_ticker_to_uppercase() -> None:
    """PositionCreate normalises ticker to upper-case."""
    data = PositionCreate(ticker="aapl", company_name="Apple Inc.", shares=Decimal("10"))
    assert data.ticker == "AAPL"


def test_position_create_rejects_zero_shares() -> None:
    """PositionCreate rejects zero or negative share counts."""
    with pytest.raises(ValidationError):
        PositionCreate(ticker="AAPL", company_name="Apple Inc.", shares=Decimal("0"))


def test_position_create_rejects_negative_shares() -> None:
    """PositionCreate rejects negative share counts."""
    with pytest.raises(ValidationError):
        PositionCreate(ticker="AAPL", company_name="Apple Inc.", shares=Decimal("-5"))


def test_position_create_rejects_empty_ticker() -> None:
    """PositionCreate rejects an empty ticker string."""
    with pytest.raises(ValidationError):
        PositionCreate(ticker="", company_name="Apple Inc.", shares=Decimal("10"))


def test_position_create_rejects_empty_company_name() -> None:
    """PositionCreate rejects a blank company name."""
    with pytest.raises(ValidationError):
        PositionCreate(ticker="AAPL", company_name="", shares=Decimal("10"))


# ── PositionUpdate ────────────────────────────────────────────────────────────


def test_position_update_valid() -> None:
    """PositionUpdate accepts a positive share count."""
    data = PositionUpdate(shares=Decimal("200"))
    assert data.shares == Decimal("200")


def test_position_update_rejects_non_positive_shares() -> None:
    """PositionUpdate rejects zero or negative shares."""
    with pytest.raises(ValidationError):
        PositionUpdate(shares=Decimal("0"))


# ── PositionResponse ──────────────────────────────────────────────────────────


def test_position_response_from_orm_fields() -> None:
    """PositionResponse can be constructed from ORM-like field values."""
    now = datetime.now(tz=UTC)
    resp = PositionResponse(
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
