"""Unit tests for the Position ORM model."""

from decimal import Decimal

import pytest
from sqlalchemy import inspect

from atlas.models.position import Position


def test_position_tablename() -> None:
    """Position model maps to the 'positions' table."""
    assert Position.__tablename__ == "positions"


def test_position_columns_exist() -> None:
    """Position model declares all required columns."""
    mapper = inspect(Position)
    col_names = {col.key for col in mapper.columns}
    assert {"id", "ticker", "company_name", "shares", "created_at", "updated_at"} <= col_names


def test_position_ticker_column_is_unique() -> None:
    """Ticker column carries a unique constraint."""
    mapper = inspect(Position)
    ticker_col = mapper.columns["ticker"]
    assert ticker_col.unique is True


def test_position_ticker_max_length() -> None:
    """Ticker column max length is 20."""
    mapper = inspect(Position)
    ticker_col = mapper.columns["ticker"]
    assert ticker_col.type.length == 20


def test_position_repr_contains_ticker() -> None:
    """__repr__ includes the ticker symbol for easy debugging."""
    position = Position(ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100"))
    assert "AAPL" in repr(position)


@pytest.mark.parametrize("ticker", ["AAPL", "BRK.B", "GOOGL"])
def test_position_accepts_valid_tickers(ticker: str) -> None:
    """Position model can be instantiated with typical US ticker symbols."""
    position = Position(ticker=ticker, company_name="Test Corp", shares=Decimal("10"))
    assert position.ticker == ticker
