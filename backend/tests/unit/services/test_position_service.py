"""Unit tests for PositionService — all DB interactions are mocked."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.services.position_service import PositionService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return a fully mocked AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def service(mock_session: AsyncMock) -> PositionService:
    return PositionService(mock_session)


# ── list_positions ────────────────────────────────────────────────────────────


async def test_list_positions_returns_all_records(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """list_positions returns every Position row ordered by ticker."""
    from atlas.models.position import Position

    fake = [
        Position(id=1, ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100")),
        Position(id=2, ticker="MSFT", company_name="Microsoft", shares=Decimal("50")),
    ]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = fake
    mock_session.execute = AsyncMock(return_value=result_mock)

    positions = await service.list_positions()
    assert len(positions) == 2
    assert positions[0].ticker == "AAPL"


async def test_list_positions_returns_empty_list_when_none(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """list_positions returns an empty list when no positions are saved."""
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result_mock)

    assert await service.list_positions() == []


# ── get_by_ticker ─────────────────────────────────────────────────────────────


async def test_get_by_ticker_returns_position_when_found(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """get_by_ticker returns the matching Position row."""
    from atlas.models.position import Position

    existing = Position(id=1, ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100"))
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    mock_session.execute = AsyncMock(return_value=result_mock)

    found = await service.get_by_ticker("AAPL")
    assert found is not None
    assert found.ticker == "AAPL"


async def test_get_by_ticker_returns_none_when_missing(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """get_by_ticker returns None if the ticker is not in the portfolio."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result_mock)

    assert await service.get_by_ticker("ZZZZ") is None


# ── create_position ───────────────────────────────────────────────────────────


async def test_create_position_adds_and_refreshes(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """create_position adds the model to the session and flushes."""
    from atlas.models.position import Position
    from atlas.schemas.position import PositionCreate

    payload = PositionCreate(ticker="NVDA", company_name="NVIDIA Corp", shares=Decimal("25"))
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    position = await service.create_position(payload)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited_once()
    assert isinstance(position, Position)
    assert position.ticker == "NVDA"


# ── update_shares ─────────────────────────────────────────────────────────────


async def test_update_shares_mutates_and_returns_position(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """update_shares changes the shares field and flushes."""
    from atlas.models.position import Position

    existing = Position(id=1, ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100"))
    mock_session.get = AsyncMock(return_value=existing)
    mock_session.flush = AsyncMock()
    mock_session.refresh = AsyncMock()

    updated = await service.update_shares(1, Decimal("200"))

    assert updated is not None
    assert updated.shares == Decimal("200")


async def test_update_shares_returns_none_for_missing_id(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """update_shares returns None when the position id does not exist."""
    mock_session.get = AsyncMock(return_value=None)

    result = await service.update_shares(999, Decimal("50"))
    assert result is None


# ── delete_position ───────────────────────────────────────────────────────────


async def test_delete_position_removes_record(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """delete_position deletes the row and returns True."""
    from atlas.models.position import Position

    existing = Position(id=1, ticker="AAPL", company_name="Apple Inc.", shares=Decimal("100"))
    mock_session.get = AsyncMock(return_value=existing)
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()

    deleted = await service.delete_position(1)

    assert deleted is True
    mock_session.delete.assert_awaited_once_with(existing)


async def test_delete_position_returns_false_for_missing_id(
    service: PositionService, mock_session: AsyncMock
) -> None:
    """delete_position returns False when the position id does not exist."""
    mock_session.get = AsyncMock(return_value=None)

    assert await service.delete_position(999) is False
