"""Unit tests for the Ticker ORM model."""

from decimal import Decimal

import pytest
from sqlalchemy import inspect

from atlas.models.ticker import Ticker


def test_ticker_tablename() -> None:
    """Ticker model maps to the 'tickers' table."""
    assert Ticker.__tablename__ == "tickers"


def test_ticker_columns_exist() -> None:
    """Ticker model declares all required columns."""
    mapper = inspect(Ticker)
    col_names = {col.key for col in mapper.columns}
    assert {"id", "ticker", "company_name", "shares", "created_at", "updated_at"} <= col_names


def test_ticker_ticker_column_is_unique() -> None:
    """Ticker column carries a unique constraint."""
    mapper = inspect(Ticker)
    ticker_col = mapper.columns["ticker"]
    assert ticker_col.unique is True


def test_ticker_ticker_max_length() -> None:
    """Ticker column max length is 20."""
    mapper = inspect(Ticker)
    ticker_col = mapper.columns["ticker"]
    assert ticker_col.type.length == 20


def test_ticker_repr_contains_ticker() -> None:
    """__repr__ includes the ticker symbol for easy debugging."""
    ticker = Ticker(ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100"))
    assert "AAPL" in repr(ticker)


@pytest.mark.parametrize("ticker", ["AAPL", "BRK.B", "GOOGL"])
def test_ticker_accepts_valid_tickers(ticker: str) -> None:
    """Ticker model can be instantiated with typical US ticker symbols."""
    t = Ticker(ticker=ticker, company_name="Test Corp", shares=Decimal("10"))
    assert t.ticker == ticker
