"""Unit tests for TickerService — all DB interactions are mocked."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.services.ticker_service import TickerService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return a fully mocked AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def service(mock_session: AsyncMock) -> TickerService:
    return TickerService(mock_session)


# ── list_tickers ────────────────────────────────────────────────────────────


async def test_list_tickers_returns_all_records(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """list_tickers returns every Position row ordered by ticker."""
    from atlas.models.ticker import Ticker

    fake = [
        Ticker(id=1, ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100")),
        Ticker(id=2, ticker="MSFT", company_name="Microsoft", shares=Decimal("50")),
    ]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = fake
    mock_session.execute = AsyncMock(return_value=result_mock)

    positions = await service.list_tickers()
    assert len(positions) == 2
    assert positions[0].ticker == "AAPL"


async def test_list_tickers_returns_empty_list_when_none(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """list_tickers returns an empty list when no positions are saved."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    assert await service.list_tickers() == []


# ── get_by_ticker ─────────────────────────────────────────────────────────────


async def test_get_by_ticker_returns_position_when_found(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """get_by_ticker returns the matching Position row."""
    from atlas.models.ticker import Ticker

    existing = Ticker(id=1, ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100"))
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    mock_session.execute = AsyncMock(return_value=result_mock)

    found = await service.get_by_ticker("AAPL")
    assert found is not None
    assert found.ticker == "AAPL"


async def test_get_by_ticker_returns_none_when_missing(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """get_by_ticker returns None if the ticker is not in the portfolio."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result_mock)

    assert await service.get_by_ticker("ZZZZ") is None


# ── create_ticker ───────────────────────────────────────────────────────────


async def test_create_ticker_adds_and_refreshes(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """create_ticker adds the model to the session and flushes."""
    from atlas.models.ticker import Ticker
    from atlas.schemas.ticker import TickerCreate

    payload = TickerCreate(ticker="NVDA", company_name="NVIDIA Corp", shares=Decimal("25"))
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    position = await service.create_ticker(payload)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()
    assert isinstance(position, Position)
    assert position.ticker == "NVDA"


# ── update_shares ─────────────────────────────────────────────────────────────


async def test_update_shares_mutates_and_returns_position(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """update_shares changes the shares field and flushes."""
    from atlas.models.ticker import Ticker

    existing = Ticker(id=1, ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100"))
    mock_session.get = AsyncMock(return_value=existing)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    updated = await service.update_shares(1, Decimal("200"))

    assert updated is not None
    assert updated.shares == Decimal("200")


async def test_update_shares_returns_none_for_missing_id(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """update_shares returns None when the position id does not exist."""
    mock_session.get = AsyncMock(return_value=None)

    result = await service.update_shares(999, Decimal("50"))
    assert result is None


# ── delete_ticker ───────────────────────────────────────────────────────────


async def test_delete_ticker_removes_record(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """delete_ticker deletes the row and returns True."""
    from atlas.models.ticker import Ticker

    existing = Ticker(id=1, ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100"))
    mock_session.get = AsyncMock(return_value=existing)
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()

    deleted = await service.delete_ticker(1)

    assert deleted is True
    mock_session.delete.assert_awaited_once_with(existing)


async def test_delete_ticker_returns_false_for_missing_id(
    service: TickerService, mock_session: AsyncMock
) -> None:
    """delete_ticker returns False when the position id does not exist."""
    mock_session.get = AsyncMock(return_value=None)

    assert await service.delete_ticker(999) is False
