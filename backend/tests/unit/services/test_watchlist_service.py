"""Unit tests for WatchlistService and MarketDataService.sync_watchlist_items."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.schemas.watchlist import WatchlistItemCreate
from atlas.services.watchlist_service import WatchlistService
from atlas.services.market_data_service import MarketDataService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS = 1_700_000_000_000
_MS_PER_DAY = 86_400_000


def _make_agg_bars(closes: list[float]) -> list[dict]:  # type: ignore[type-arg]
    return [{"t": _BASE_TS + i * _MS_PER_DAY, "c": c} for i, c in enumerate(closes)]


def _make_spy_close_map(closes: list[float]) -> dict[int, float]:
    return {_BASE_TS + i * _MS_PER_DAY: c for i, c in enumerate(closes)}


def _make_watchlist_item(ticker: str = "NVDA") -> MagicMock:
    item = MagicMock()
    item.ticker = ticker
    return item


def _http_ok(payload: dict) -> MagicMock:  # type: ignore[type-arg]
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    return resp


# ---------------------------------------------------------------------------
# WatchlistService — CRUD
# ---------------------------------------------------------------------------


class TestWatchlistService:
    def _make_service(self) -> tuple[WatchlistService, AsyncMock]:
        session = AsyncMock()
        return WatchlistService(session), session

    async def test_list_items_returns_ordered_results(self) -> None:
        service, session = self._make_service()
        item_a = MagicMock()
        item_a.ticker = "AAPL"
        item_b = MagicMock()
        item_b.ticker = "TSLA"
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [item_a, item_b]
        session.execute = AsyncMock(return_value=mock_result)

        result = await service.list_items()

        assert len(result) == 2
        assert result[0].ticker == "AAPL"

    async def test_get_by_ticker_returns_none_when_missing(self) -> None:
        service, session = self._make_service()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await service.get_by_ticker("AAPL")

        assert result is None

    async def test_create_item_adds_and_refreshes(self) -> None:
        service, session = self._make_service()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        data = WatchlistItemCreate(ticker="nvda", company_name="NVIDIA Corporation")
        item = await service.create_item(data)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once()
        # Ticker is normalised to upper-case by the schema validator.
        assert item.ticker == "NVDA"

    async def test_delete_item_returns_true_on_success(self) -> None:
        service, session = self._make_service()
        mock_item = MagicMock()
        session.get = AsyncMock(return_value=mock_item)
        session.delete = AsyncMock()
        session.flush = AsyncMock()

        result = await service.delete_item(1)

        assert result is True
        session.delete.assert_awaited_once_with(mock_item)

    async def test_delete_item_returns_false_when_not_found(self) -> None:
        service, session = self._make_service()
        session.get = AsyncMock(return_value=None)

        result = await service.delete_item(999)

        assert result is False


# ---------------------------------------------------------------------------
# MarketDataService._apply_watchlist_market_data
# ---------------------------------------------------------------------------


class TestApplyWatchlistMarketData:
    _NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_writes_snapshot_price_and_beta(self) -> None:
        item = _make_watchlist_item()
        snap = {
            "ticker": "NVDA",
            "day": {"c": 875.0},
            "prevDay": {"c": 850.0},
            "todaysChange": 25.0,
            "todaysChangePerc": 2.94,
        }

        MarketDataService._apply_watchlist_market_data(
            item, snap, [], Decimal("1.8"), self._NOW
        )

        assert item.current_price == Decimal("875.0")
        assert item.previous_close == Decimal("850.0")
        assert item.day_change == Decimal("25.0")
        assert item.day_change_pct == Decimal("2.94")
        assert item.beta == Decimal("1.8")
        assert item.synced_at == self._NOW

    def test_no_position_value_field_written(self) -> None:
        """WatchlistItem has no position_value — ensure the method never sets it."""
        from atlas.models.watchlist import WatchlistItem as RealItem

        item = RealItem(ticker="NVDA", company_name="NVIDIA Corporation")
        snap = {"ticker": "NVDA", "day": {"c": 875.0}, "prevDay": {"c": 850.0}}

        MarketDataService._apply_watchlist_market_data(item, snap, [], None, self._NOW)

        # Real WatchlistItem has no position_value column — attribute should not exist.
        assert not hasattr(item, "position_value")

    def test_fallback_to_agg_bars_when_no_snapshot(self) -> None:
        item = _make_watchlist_item()
        agg_bars = _make_agg_bars([100.0, 105.0, 107.0])

        MarketDataService._apply_watchlist_market_data(item, None, agg_bars, None, self._NOW)

        assert item.current_price == Decimal("107.0")
        assert item.previous_close == Decimal("105.0")

    def test_only_beta_and_synced_at_when_no_price_data(self) -> None:
        item = _make_watchlist_item()

        MarketDataService._apply_watchlist_market_data(
            item, None, [], Decimal("0.7"), self._NOW
        )

        assert item.beta == Decimal("0.7")
        assert item.synced_at == self._NOW

    def test_derives_day_change_when_snapshot_omits_it(self) -> None:
        item = _make_watchlist_item()
        snap = {"ticker": "NVDA", "day": {"c": 110.0}, "prevDay": {"c": 100.0}}

        MarketDataService._apply_watchlist_market_data(item, snap, [], None, self._NOW)

        assert item.day_change == Decimal("10.0")
        assert item.day_change_pct is not None
        assert abs(float(item.day_change_pct) - 10.0) < 0.001


# ---------------------------------------------------------------------------
# MarketDataService.sync_watchlist_items — integration
# ---------------------------------------------------------------------------


class TestSyncWatchlistItems:
    async def test_returns_empty_list_when_no_items_in_db(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        svc = MarketDataService(api_key="key", session=session, client=AsyncMock())
        result = await svc.sync_watchlist_items()

        assert result == []

    async def test_applies_snapshot_and_beta_to_item(self) -> None:
        item = _make_watchlist_item(ticker="NVDA")

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [item]
        session.execute = AsyncMock(return_value=mock_result)

        # Build 61-point agg series where ticker = 1.5× SPY return.
        spy_ret_seq = [0.01, -0.005, 0.02, -0.01, 0.015, -0.008] * 10
        spy_closes = [100.0]
        ticker_closes = [100.0]
        for r in spy_ret_seq:
            spy_closes.append(spy_closes[-1] * (1.0 + r))
            ticker_closes.append(ticker_closes[-1] * (1.0 + 1.5 * r))

        spy_bars = _make_agg_bars(spy_closes)
        ticker_agg_bars = _make_agg_bars(ticker_closes)

        snap_payload = {
            "status": "OK",
            "tickers": [
                {
                    "ticker": "NVDA",
                    "day": {"c": 875.0},
                    "prevDay": {"c": 850.0},
                    "todaysChange": 25.0,
                    "todaysChangePerc": 2.94,
                }
            ],
        }

        client = AsyncMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:  # type: ignore[return]
            if "snapshot" in url:
                return _http_ok(snap_payload)
            if "SPY" in url:
                return _http_ok({"status": "OK", "results": spy_bars})
            return _http_ok({"status": "OK", "results": ticker_agg_bars})

        client.get = mock_get

        svc = MarketDataService(api_key="key", session=session, client=client)
        result = await svc.sync_watchlist_items()

        assert len(result) == 1
        i = result[0]
        assert i.current_price == Decimal("875.0")
        assert i.beta is not None
        assert abs(float(i.beta) - 1.5) < 0.05
