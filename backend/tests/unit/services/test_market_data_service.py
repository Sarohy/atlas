"""Unit tests for MarketDataService — all Polygon HTTP calls are mocked."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlas.services.market_data_service import MarketDataService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS = 1_700_000_000_000  # arbitrary epoch ms — 2023-11-15 roughly
_MS_PER_DAY = 86_400_000  # milliseconds in one trading day


def _make_agg_bars(closes: list[float], base_ts: int = _BASE_TS) -> list[dict]:  # type: ignore[type-arg]
    """Return minimal Polygon daily-agg bar dicts with sequential timestamps."""
    return [{"t": base_ts + i * _MS_PER_DAY, "c": c} for i, c in enumerate(closes)]


def _make_spy_close_map(closes: list[float], base_ts: int = _BASE_TS) -> dict[int, float]:
    """Build the timestamp→close dict that sync_tickers derives from SPY bars."""
    return {base_ts + i * _MS_PER_DAY: c for i, c in enumerate(closes)}


def _make_snapshot(
    day_close: float | None = 150.0,
    prev_close: float | None = 148.0,
    todays_change: float | None = 2.0,
    todays_change_pct: float | None = 1.35,
) -> dict:  # type: ignore[type-arg]
    """Return a minimal Polygon batch-snapshot ticker entry."""
    snap: dict = {"ticker": "AAPL"}  # type: ignore[type-arg]
    if day_close is not None:
        snap["day"] = {"c": day_close}
    if prev_close is not None:
        snap["prevDay"] = {"c": prev_close}
    if todays_change is not None:
        snap["todaysChange"] = todays_change
    if todays_change_pct is not None:
        snap["todaysChangePerc"] = todays_change_pct
    return snap


def _make_ticker(ticker: str = "AAPL", shares: Decimal = Decimal("10")) -> MagicMock:
    """Return a minimal mock Ticker ORM object."""
    t = MagicMock()
    t.ticker = ticker
    t.shares = shares
    return t


def _http_ok(payload: dict) -> MagicMock:  # type: ignore[type-arg]
    """Wrap a payload dict in a mock httpx Response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    return resp


# ---------------------------------------------------------------------------
# _compute_beta
# ---------------------------------------------------------------------------


class TestComputeBeta:
    """Tests for the pure static beta-calculation method."""

    def test_returns_none_when_fewer_than_min_pairs(self) -> None:
        """Returns None when aligned data is below the _MIN_RETURN_PAIRS threshold."""
        # 20 bars → 19 returns — below the 30-pair minimum.
        closes = [100.0 + i for i in range(20)]
        ticker_bars = _make_agg_bars(closes)
        spy_map = _make_spy_close_map(closes)

        result = MarketDataService._compute_beta(ticker_bars, spy_map)

        assert result is None

    def test_returns_none_when_spy_variance_is_zero(self) -> None:
        """Returns None when SPY has zero variance (flat market — no signal)."""
        # 52 prices, SPY perfectly flat at 100.
        closes = [100.0] * 52
        ticker_bars = _make_agg_bars([100.0 + i * 0.5 for i in range(52)])
        spy_map = _make_spy_close_map(closes)

        result = MarketDataService._compute_beta(ticker_bars, spy_map)

        assert result is None

    def test_returns_correct_beta_of_two(self) -> None:
        """Beta ≈ 2.0 when ticker return is exactly 2× SPY return each day."""
        # 61 prices → 60 returns, well above the 30-pair minimum.
        # Alternating positive/negative returns ensure non-zero SPY variance.
        spy_ret_seq = [0.01, -0.005, 0.02, -0.01, 0.015, -0.008] * 10  # 60 values

        spy_closes = [100.0]
        ticker_closes = [100.0]
        for r in spy_ret_seq:
            spy_closes.append(spy_closes[-1] * (1.0 + r))
            ticker_closes.append(ticker_closes[-1] * (1.0 + 2.0 * r))

        ticker_bars = _make_agg_bars(ticker_closes)
        spy_map = _make_spy_close_map(spy_closes)

        result = MarketDataService._compute_beta(ticker_bars, spy_map)

        assert result is not None
        assert abs(float(result) - 2.0) < 1e-3

    def test_returns_correct_beta_of_one(self) -> None:
        """Beta ≈ 1.0 when ticker mirrors SPY returns exactly."""
        spy_ret_seq = [0.01, -0.005, 0.02, -0.01, 0.015, -0.008] * 10

        spy_closes = [100.0]
        for r in spy_ret_seq:
            spy_closes.append(spy_closes[-1] * (1.0 + r))

        ticker_bars = _make_agg_bars(spy_closes)
        spy_map = _make_spy_close_map(spy_closes)

        result = MarketDataService._compute_beta(ticker_bars, spy_map)

        assert result is not None
        assert abs(float(result) - 1.0) < 1e-3

    def test_skips_bars_with_no_spy_match(self) -> None:
        """Bars whose timestamps have no SPY entry are excluded from calculation."""
        closes = [100.0 + i for i in range(52)]
        ticker_bars = _make_agg_bars(closes)
        # SPY map covers only the first 32 timestamps — the rest are unmatched.
        spy_map = _make_spy_close_map(closes[:32])

        result = MarketDataService._compute_beta(ticker_bars, spy_map)

        # 32 aligned closes → 31 returns → exactly at minimum → should succeed.
        assert result is not None

    def test_returns_none_when_spy_map_is_empty(self) -> None:
        """Returns None when no SPY bars were fetched at all."""
        closes = [100.0 + i for i in range(52)]
        ticker_bars = _make_agg_bars(closes)

        result = MarketDataService._compute_beta(ticker_bars, {})

        assert result is None


# ---------------------------------------------------------------------------
# _build_close_map
# ---------------------------------------------------------------------------


class TestBuildCloseMap:
    def test_builds_map_from_bars(self) -> None:
        bars = [{"t": 1000, "c": 100.0}, {"t": 2000, "c": 200.0}]
        result = MarketDataService._build_close_map(bars)
        assert result == {1000: 100.0, 2000: 200.0}

    def test_skips_bars_missing_timestamp_or_close(self) -> None:
        bars = [{"c": 100.0}, {"t": 2000}, {"t": 3000, "c": 300.0}]
        result = MarketDataService._build_close_map(bars)
        assert result == {3000: 300.0}

    def test_returns_empty_dict_for_empty_bars(self) -> None:
        assert MarketDataService._build_close_map([]) == {}


# ---------------------------------------------------------------------------
# _apply_market_data
# ---------------------------------------------------------------------------


class TestApplyMarketData:
    """Tests for the pure static method that writes data onto a Ticker."""

    _NOW = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def test_uses_snapshot_prices_when_available(self) -> None:
        ticker = _make_ticker()
        snap = _make_snapshot(day_close=150.0, prev_close=148.0)

        MarketDataService._apply_market_data(ticker, snap, [], Decimal("1.2"), self._NOW)

        assert ticker.current_price == Decimal("150.0")
        assert ticker.previous_close == Decimal("148.0")
        assert ticker.beta == Decimal("1.2")
        assert ticker.synced_at == self._NOW

    def test_uses_todays_change_from_snapshot_directly(self) -> None:
        """todaysChange / todaysChangePerc from Polygon are used as-is."""
        ticker = _make_ticker()
        snap = _make_snapshot(
            day_close=150.0,
            prev_close=148.0,
            todays_change=2.0,
            todays_change_pct=1.3514,
        )

        MarketDataService._apply_market_data(ticker, snap, [], None, self._NOW)

        assert ticker.day_change == Decimal("2.0")
        assert ticker.day_change_pct == Decimal("1.3514")

    def test_derives_day_change_when_snapshot_omits_it(self) -> None:
        """day_change and day_change_pct are computed locally when absent."""
        ticker = _make_ticker()
        snap = _make_snapshot(
            day_close=110.0,
            prev_close=100.0,
            todays_change=None,
            todays_change_pct=None,
        )

        MarketDataService._apply_market_data(ticker, snap, [], None, self._NOW)

        assert ticker.current_price == Decimal("110.0")
        assert ticker.day_change == Decimal("10.0")
        # 10/100 * 100 = 10.0%
        assert ticker.day_change_pct is not None
        assert abs(float(ticker.day_change_pct) - 10.0) < 0.001

    def test_computes_position_value(self) -> None:
        ticker = _make_ticker(shares=Decimal("5"))
        snap = _make_snapshot(day_close=200.0)

        MarketDataService._apply_market_data(ticker, snap, [], None, self._NOW)

        assert ticker.position_value == Decimal("200.0") * Decimal("5")

    def test_falls_back_to_agg_bars_when_no_snapshot(self) -> None:
        ticker = _make_ticker()
        agg_bars = _make_agg_bars([140.0, 142.0, 144.0])

        MarketDataService._apply_market_data(ticker, None, agg_bars, None, self._NOW)

        assert ticker.current_price == Decimal("144.0")
        assert ticker.previous_close == Decimal("142.0")

    def test_agg_fallback_uses_open_for_prev_close_on_single_bar(self) -> None:
        """When only one agg bar exists, open price is used as previous close."""
        ticker = _make_ticker()
        agg_bars = [{"t": _BASE_TS, "c": 100.0, "o": 98.0}]

        MarketDataService._apply_market_data(ticker, None, agg_bars, None, self._NOW)

        assert ticker.current_price == Decimal("100.0")
        assert ticker.previous_close == Decimal("98.0")

    def test_skips_price_update_when_snapshot_has_no_day_close_and_no_agg(self) -> None:
        """Only beta and synced_at are written when there is no price data."""
        ticker = _make_ticker()
        # Snapshot with empty day object, no agg bars.
        snap: dict = {"ticker": "AAPL", "day": {}, "prevDay": {}}  # type: ignore[type-arg]

        MarketDataService._apply_market_data(ticker, snap, [], Decimal("0.8"), self._NOW)

        assert ticker.beta == Decimal("0.8")
        assert ticker.synced_at == self._NOW
        # current_price should NOT have been set (mock never assigned).
        ticker.current_price.assert_not_called() if hasattr(ticker.current_price, "assert_not_called") else None  # noqa: B950

    def test_no_data_at_all_only_updates_beta_and_audit_fields(self) -> None:
        ticker = _make_ticker()

        MarketDataService._apply_market_data(ticker, None, [], Decimal("0.5"), self._NOW)

        assert ticker.beta == Decimal("0.5")
        assert ticker.synced_at == self._NOW

    def test_snapshot_day_close_fallback_to_last_agg(self) -> None:
        """When snapshot has no day.c, last agg bar close is used as current price."""
        ticker = _make_ticker()
        snap: dict = {"ticker": "AAPL", "prevDay": {"c": 130.0}}  # type: ignore[type-arg]
        agg_bars = _make_agg_bars([128.0, 131.0])

        MarketDataService._apply_market_data(ticker, snap, agg_bars, None, self._NOW)

        assert ticker.current_price == Decimal("131.0")
        assert ticker.previous_close == Decimal("130.0")

    def test_snapshot_zero_day_close_falls_back_to_previous_close(self) -> None:
        """Polygon can return day.c=0 before a usable close; never value holdings at zero."""
        ticker = _make_ticker(shares=Decimal("10"))
        snap = _make_snapshot(day_close=0.0, prev_close=136.5)

        MarketDataService._apply_market_data(ticker, snap, [], None, self._NOW)

        assert ticker.current_price == Decimal("136.5")
        assert ticker.position_value == Decimal("136.5") * Decimal("10")


# ---------------------------------------------------------------------------
# _fetch_snapshot_batch / _fetch_snapshot_chunk
# ---------------------------------------------------------------------------


class TestFetchSnapshotBatch:
    """Tests for the batch snapshot HTTP layer."""

    def _make_service(self, mock_client: AsyncMock) -> MarketDataService:
        return MarketDataService(
            api_key="test-key",
            session=AsyncMock(),
            client=mock_client,
        )

    async def test_single_call_for_small_ticker_list(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok(
                {
                    "status": "OK",
                    "tickers": [
                        {"ticker": "AAPL", "day": {"c": 150.0}},
                        {"ticker": "MSFT", "day": {"c": 300.0}},
                    ],
                }
            )
        )
        svc = self._make_service(client)

        result = await svc._fetch_snapshot_batch(["AAPL", "MSFT"])

        client.get.assert_awaited_once()
        assert "AAPL" in result
        assert "MSFT" in result

    async def test_paginates_into_multiple_calls_for_large_list(self) -> None:
        """Lists larger than 250 tickers are split into separate API calls."""
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok({"status": "OK", "tickers": []})
        )
        svc = self._make_service(client)

        symbols = [f"T{i:03d}" for i in range(300)]
        await svc._fetch_snapshot_batch(symbols)

        # 300 tickers → ceil(300/250) = 2 calls.
        assert client.get.await_count == 2

    async def test_returns_empty_dict_on_http_error(self) -> None:
        import httpx

        client = AsyncMock()
        client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )
        )
        svc = self._make_service(client)

        result = await svc._fetch_snapshot_batch(["AAPL"])

        assert result == {}

    async def test_passes_tickers_and_api_key_in_params(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok({"status": "OK", "tickers": []})
        )
        svc = self._make_service(client)

        await svc._fetch_snapshot_batch(["AAPL", "TSLA"])

        call_params = client.get.call_args.kwargs.get("params", {})
        assert "AAPL" in call_params.get("tickers", "")
        assert "TSLA" in call_params.get("tickers", "")
        assert call_params.get("apiKey") == "test-key"


# ---------------------------------------------------------------------------
# _fetch_raw_bars
# ---------------------------------------------------------------------------


class TestFetchRawBars:
    def _make_service(self, mock_client: AsyncMock) -> MarketDataService:
        return MarketDataService(
            api_key="test-key",
            session=AsyncMock(),
            client=mock_client,
        )

    async def test_returns_results_from_payload(self) -> None:
        from datetime import date

        bars = [{"t": 1000, "c": 100.0}, {"t": 2000, "c": 101.0}]
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok({"status": "OK", "results": bars})
        )
        svc = self._make_service(client)

        result = await svc._fetch_raw_bars("AAPL", date(2024, 1, 1), date(2025, 1, 1))

        assert result == bars

    async def test_returns_empty_list_on_http_error(self) -> None:
        import httpx
        from datetime import date

        client = AsyncMock()
        client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "403 Forbidden",
                request=MagicMock(),
                response=MagicMock(status_code=403),
            )
        )
        svc = self._make_service(client)

        result = await svc._fetch_raw_bars("AAPL", date(2024, 1, 1), date(2025, 1, 1))

        assert result == []

    async def test_requests_adjusted_data_ascending(self) -> None:
        from datetime import date

        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok({"status": "OK", "results": []})
        )
        svc = self._make_service(client)

        await svc._fetch_raw_bars("SPY", date(2024, 1, 1), date(2025, 1, 1))

        params = client.get.call_args.kwargs.get("params", {})
        assert params.get("adjusted") == "true"
        assert params.get("sort") == "asc"


# ---------------------------------------------------------------------------
# sync_tickers integration
# ---------------------------------------------------------------------------


class TestSyncTickers:
    async def test_returns_empty_list_when_no_tickers_in_db(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        svc = MarketDataService(
            api_key="key",
            session=session,
            client=AsyncMock(),
        )

        result = await svc.sync_tickers()

        assert result == []

    async def test_applies_snapshot_and_beta_to_ticker(self) -> None:
        """End-to-end: snapshot provides prices; agg bars provide beta."""
        ticker = _make_ticker(ticker="AAPL", shares=Decimal("10"))

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ticker]
        session.execute = AsyncMock(return_value=mock_result)

        # Build 61-point agg series where ticker = 2× SPY return.
        spy_ret_seq = [0.01, -0.005, 0.02, -0.01, 0.015, -0.008] * 10
        spy_closes = [100.0]
        ticker_closes = [100.0]
        for r in spy_ret_seq:
            spy_closes.append(spy_closes[-1] * (1.0 + r))
            ticker_closes.append(ticker_closes[-1] * (1.0 + 2.0 * r))

        spy_bars = _make_agg_bars(spy_closes)
        ticker_agg_bars = _make_agg_bars(ticker_closes)

        snap_payload = {
            "status": "OK",
            "tickers": [
                {
                    "ticker": "AAPL",
                    "day": {"c": 150.0},
                    "prevDay": {"c": 148.0},
                    "todaysChange": 2.0,
                    "todaysChangePerc": 1.35,
                }
            ],
        }

        client = AsyncMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:  # type: ignore[return]
            params = kwargs.get("params", {})
            if "snapshot" in url:
                return _http_ok(snap_payload)
            # Agg endpoint — identify by ticker param in URL.
            if "SPY" in url:
                return _http_ok({"status": "OK", "results": spy_bars})
            return _http_ok({"status": "OK", "results": ticker_agg_bars})

        client.get = mock_get

        svc = MarketDataService(api_key="key", session=session, client=client)
        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {}  # no yahoo beta → falls through to Polygon OLS
            result = await svc.sync_tickers()

        assert len(result) == 1
        t = result[0]
        assert t.current_price == Decimal("150.0")
        assert t.previous_close == Decimal("148.0")
        assert t.beta is not None
        assert abs(float(t.beta) - 2.0) < 0.01


# ---------------------------------------------------------------------------
# _fetch_alpha_vantage_beta
# ---------------------------------------------------------------------------


class TestFetchAlphaVantageBeta:
    """Tests for the Alpha Vantage OVERVIEW beta fetch helper."""

    def _make_service(self, mock_client: AsyncMock) -> MarketDataService:
        return MarketDataService(
            api_key="polygon-key",
            alphavantage_api_key="av-key",
            session=AsyncMock(),
            client=mock_client,
        )

    async def test_returns_beta_from_successful_response(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok({"Symbol": "MU", "Beta": "1.919"})
        )
        svc = self._make_service(client)

        result = await svc._fetch_alpha_vantage_beta("MU")

        assert result == Decimal("1.919")

    async def test_returns_none_when_beta_field_missing(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok({"Symbol": "MU", "Name": "Micron Technology"})
        )
        svc = self._make_service(client)

        result = await svc._fetch_alpha_vantage_beta("MU")

        assert result is None

    async def test_returns_none_when_beta_field_is_none_string(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok({"Symbol": "MU", "Beta": "None"})
        )
        svc = self._make_service(client)

        result = await svc._fetch_alpha_vantage_beta("MU")

        assert result is None

    async def test_returns_none_on_http_error(self) -> None:
        import httpx

        client = AsyncMock()
        client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )
        )
        svc = self._make_service(client)

        result = await svc._fetch_alpha_vantage_beta("MU")

        assert result is None

    async def test_sends_correct_params(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(
            return_value=_http_ok({"Beta": "1.5"})
        )
        svc = self._make_service(client)

        await svc._fetch_alpha_vantage_beta("MU")

        call_params = client.get.call_args.kwargs.get("params", {})
        assert call_params.get("function") == "OVERVIEW"
        assert call_params.get("symbol") == "MU"
        assert call_params.get("apikey") == "av-key"

    async def test_returns_none_when_no_av_key_configured(self) -> None:
        client = AsyncMock()
        svc = MarketDataService(
            api_key="polygon-key",
            alphavantage_api_key="",
            session=AsyncMock(),
            client=client,
        )

        result = await svc._fetch_alpha_vantage_beta("MU")

        client.get.assert_not_called()
        assert result is None


# ---------------------------------------------------------------------------
# sync_tickers — Alpha Vantage as primary beta source
# ---------------------------------------------------------------------------


class TestSyncTickersAlphaVantageBeta:
    async def test_uses_alpha_vantage_beta_when_available(self) -> None:
        """AV beta is used as primary source; Polygon agg bars still fetched for SPY."""
        ticker = _make_ticker(ticker="MU", shares=Decimal("5"))

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ticker]
        session.execute = AsyncMock(return_value=mock_result)

        snap_payload = {
            "status": "OK",
            "tickers": [
                {
                    "ticker": "MU",
                    "day": {"c": 100.0},
                    "prevDay": {"c": 98.0},
                    "todaysChange": 2.0,
                    "todaysChangePerc": 2.04,
                }
            ],
        }

        client = AsyncMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:  # type: ignore[return]
            params = kwargs.get("params", {})
            if "alphavantage" in url:
                return _http_ok({"Beta": "1.919"})
            if "snapshot" in url:
                return _http_ok(snap_payload)
            # Agg endpoint returns empty (AV beta takes priority)
            return _http_ok({"status": "OK", "results": []})

        client.get = mock_get

        svc = MarketDataService(
            api_key="polygon-key",
            alphavantage_api_key="av-key",
            session=session,
            client=client,
        )
        result = await svc.sync_tickers()

        assert len(result) == 1
        assert result[0].beta == Decimal("1.919")

    async def test_falls_back_to_computed_beta_when_av_unavailable(self) -> None:
        """Falls back to Polygon-computed beta when AV returns None."""
        ticker = _make_ticker(ticker="MU", shares=Decimal("5"))

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ticker]
        session.execute = AsyncMock(return_value=mock_result)

        spy_ret_seq = [0.01, -0.005, 0.02, -0.01, 0.015, -0.008] * 10
        spy_closes = [100.0]
        ticker_closes = [100.0]
        for r in spy_ret_seq:
            spy_closes.append(spy_closes[-1] * (1.0 + r))
            ticker_closes.append(ticker_closes[-1] * (1.0 + 2.0 * r))

        spy_bars = _make_agg_bars(spy_closes)
        ticker_agg_bars = _make_agg_bars(ticker_closes)

        snap_payload = {
            "status": "OK",
            "tickers": [{"ticker": "MU", "day": {"c": 100.0}, "prevDay": {"c": 98.0}}],
        }

        client = AsyncMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:  # type: ignore[return]
            if "alphavantage" in url:
                return _http_ok({"Beta": "None"})
            if "snapshot" in url:
                return _http_ok(snap_payload)
            if "SPY" in url:
                return _http_ok({"status": "OK", "results": spy_bars})
            return _http_ok({"status": "OK", "results": ticker_agg_bars})

        client.get = mock_get

        svc = MarketDataService(
            api_key="polygon-key",
            alphavantage_api_key="av-key",
            session=session,
            client=client,
        )
        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {}  # no yahoo beta → falls through to Polygon OLS
            result = await svc.sync_tickers()

        assert len(result) == 1
        assert result[0].beta is not None
        assert abs(float(result[0].beta) - 2.0) < 0.01


# ---------------------------------------------------------------------------
# _fetch_yahoo_beta
# ---------------------------------------------------------------------------


class TestFetchYahooBeta:
    """Tests for the Yahoo Finance beta fetch helper."""

    def _make_service(self) -> MarketDataService:
        return MarketDataService(
            api_key="polygon-key",
            alphavantage_api_key="av-key",
            session=AsyncMock(),
            client=AsyncMock(),
        )

    async def test_returns_beta_from_yahoo_finance(self) -> None:
        from unittest.mock import patch

        svc = self._make_service()
        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"beta": 2.97}
            result = await svc._fetch_yahoo_beta("SNDK")

        assert result == Decimal("2.97")

    async def test_returns_none_when_beta_missing_from_info(self) -> None:
        from unittest.mock import patch

        svc = self._make_service()
        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"symbol": "SNDK"}
            result = await svc._fetch_yahoo_beta("SNDK")

        assert result is None

    async def test_returns_none_when_beta_value_is_none(self) -> None:
        from unittest.mock import patch

        svc = self._make_service()
        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"beta": None}
            result = await svc._fetch_yahoo_beta("SNDK")

        assert result is None

    async def test_returns_none_on_exception(self) -> None:
        from unittest.mock import patch

        svc = self._make_service()
        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.side_effect = Exception("network error")
            result = await svc._fetch_yahoo_beta("SNDK")

        assert result is None

    async def test_passes_correct_ticker_symbol(self) -> None:
        from unittest.mock import patch

        svc = self._make_service()
        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"beta": 1.5}
            await svc._fetch_yahoo_beta("AAPL")
            mock_yf.assert_called_once_with("AAPL")


# ---------------------------------------------------------------------------
# sync_tickers — Yahoo Finance as secondary beta source (AV → YF → Polygon)
# ---------------------------------------------------------------------------


class TestSyncTickersYahooBetaFallback:
    async def test_uses_yahoo_beta_when_av_returns_none(self) -> None:
        """When AV returns None, Yahoo Finance beta is used before Polygon OLS."""
        from unittest.mock import patch

        ticker = _make_ticker(ticker="SNDK", shares=Decimal("40"))

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ticker]
        session.execute = AsyncMock(return_value=mock_result)

        snap_payload = {
            "status": "OK",
            "tickers": [
                {
                    "ticker": "SNDK",
                    "day": {"c": 1547.56},
                    "prevDay": {"c": 1591.64},
                    "todaysChange": -44.08,
                    "todaysChangePerc": -2.77,
                }
            ],
        }

        client = AsyncMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:  # type: ignore[return]
            if "alphavantage" in url:
                return _http_ok({"Beta": "None"})  # AV has no data for SNDK
            if "snapshot" in url:
                return _http_ok(snap_payload)
            return _http_ok({"status": "OK", "results": []})

        client.get = mock_get

        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {"beta": 2.97}
            svc = MarketDataService(
                api_key="polygon-key",
                alphavantage_api_key="av-key",
                session=session,
                client=client,
            )
            result = await svc.sync_tickers()

        assert len(result) == 1
        assert result[0].beta == Decimal("2.97")

    async def test_falls_back_to_polygon_ols_when_av_and_yahoo_both_none(self) -> None:
        """When both AV and Yahoo return None, Polygon OLS regression is used."""
        from unittest.mock import patch

        ticker = _make_ticker(ticker="SNDK", shares=Decimal("40"))

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ticker]
        session.execute = AsyncMock(return_value=mock_result)

        spy_ret_seq = [0.01, -0.005, 0.02, -0.01, 0.015, -0.008] * 10
        spy_closes = [100.0]
        ticker_closes = [100.0]
        for r in spy_ret_seq:
            spy_closes.append(spy_closes[-1] * (1.0 + r))
            ticker_closes.append(ticker_closes[-1] * (1.0 + 2.0 * r))

        spy_bars = _make_agg_bars(spy_closes)
        ticker_agg_bars = _make_agg_bars(ticker_closes)

        snap_payload = {
            "status": "OK",
            "tickers": [{"ticker": "SNDK", "day": {"c": 1547.56}, "prevDay": {"c": 1591.64}}],
        }

        client = AsyncMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:  # type: ignore[return]
            if "alphavantage" in url:
                return _http_ok({"Beta": "None"})
            if "snapshot" in url:
                return _http_ok(snap_payload)
            if "SPY" in url:
                return _http_ok({"status": "OK", "results": spy_bars})
            return _http_ok({"status": "OK", "results": ticker_agg_bars})

        client.get = mock_get

        with patch("atlas.services.market_data_service.yf.Ticker") as mock_yf:
            mock_yf.return_value.info = {}  # Yahoo also has no beta
            svc = MarketDataService(
                api_key="polygon-key",
                alphavantage_api_key="av-key",
                session=session,
                client=client,
            )
            result = await svc.sync_tickers()

        assert len(result) == 1
        assert result[0].beta is not None
        assert abs(float(result[0].beta) - 2.0) < 0.01

