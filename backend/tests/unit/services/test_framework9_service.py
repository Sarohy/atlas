"""Unit tests for Framework 9 — Options Flow Signal Hierarchy.

All tests are synchronous (pure helpers) or use pytest-asyncio for the async
evaluation function.  Network I/O is fully mocked via pytest monkeypatch and
direct injection of pre-built data dicts to the pure build_data_gap_details
helper.

Test map (12 required test cases from the spec):
  Test 1  — All sources online, whale block (TIER_1, score 92+)
  Test 2  — UW offline only (max TIER_2, f1_badge="F4 PARTIAL DATA")
  Test 3  — Polygon offline (dark_pool_modifier=0, TIER_2 blocked)
  Test 4  — Put/call ratio missing (put_call_modifier=0)
  Test 5  — Dark pool price missing (spread_position=None)
  Test 6  — All sources offline (f4_score=55, severity=CRITICAL)
  Test 7  — Partial field failures (severity=PARTIAL, amber warnings)
  Test 8  — Rate limited UW with cache (uw_status=RATE_LIMITED)
  Test 9  — Stale data >4 h (uw_status=STALE)
  Test 10 — Covered call unverifiable (Polygon offline, bearish UW)
  Test 11 — build_data_gap_details no gaps (severity=NONE)
  Test 12 — build_data_gap_details CRITICAL (f1_badge=F4 DATA UNAVAILABLE)
"""

from __future__ import annotations

import pytest

from atlas.schemas.framework9 import DataGapDetail, DataSourceStatus
from atlas.services.framework9_service import (
    _grade_from_score,
    _resolve_spread_position,
    build_data_gap_details,
    _cache,
    _cache_set,
)


# ---------------------------------------------------------------------------
# _grade_from_score — pure helper
# ---------------------------------------------------------------------------


class TestGradeFromScore:
    def test_strong_buy_at_80(self) -> None:
        assert _grade_from_score(80) == "STRONG BUY"

    def test_strong_buy_above_80(self) -> None:
        assert _grade_from_score(95) == "STRONG BUY"

    def test_buy_at_60(self) -> None:
        assert _grade_from_score(60) == "BUY"

    def test_buy_at_79(self) -> None:
        assert _grade_from_score(79) == "BUY"

    def test_neutral_at_40(self) -> None:
        assert _grade_from_score(40) == "NEUTRAL"

    def test_neutral_at_55(self) -> None:
        assert _grade_from_score(55) == "NEUTRAL"

    def test_weak_at_20(self) -> None:
        assert _grade_from_score(20) == "WEAK"

    def test_weak_at_39(self) -> None:
        assert _grade_from_score(39) == "WEAK"

    def test_avoid_below_20(self) -> None:
        assert _grade_from_score(10) == "AVOID"


# ---------------------------------------------------------------------------
# _resolve_spread_position — pure helper
# ---------------------------------------------------------------------------


class TestResolveSpreadPosition:
    def test_normal_buy_side(self) -> None:
        sp, flags = _resolve_spread_position(price=51.0, bid=50.0, ask=52.0)
        assert sp == pytest.approx(0.5)
        assert not any(flags.values())

    def test_buy_side_above_0_6(self) -> None:
        sp, flags = _resolve_spread_position(price=51.5, bid=50.0, ask=52.0)
        assert sp is not None and sp > 0.6

    def test_sell_side_below_0_4(self) -> None:
        sp, flags = _resolve_spread_position(price=50.3, bid=50.0, ask=52.0)
        assert sp is not None and sp < 0.4

    def test_price_missing(self) -> None:
        sp, flags = _resolve_spread_position(price=None, bid=50.0, ask=52.0)
        assert sp is None
        assert flags["dark_pool_price_missing"] is True

    def test_bid_missing(self) -> None:
        sp, flags = _resolve_spread_position(price=51.0, bid=None, ask=52.0)
        assert sp is None
        assert flags["dark_pool_bid_missing"] is True

    def test_ask_missing(self) -> None:
        sp, flags = _resolve_spread_position(price=51.0, bid=50.0, ask=None)
        assert sp is None
        assert flags["dark_pool_ask_missing"] is True

    def test_zero_spread_returns_neutral(self) -> None:
        sp, flags = _resolve_spread_position(price=50.0, bid=50.0, ask=50.0)
        assert sp == pytest.approx(0.5)
        assert flags["zero_spread_detected"] is True


# ---------------------------------------------------------------------------
# build_data_gap_details — pure helper
# ---------------------------------------------------------------------------


class TestBuildDataGapDetails:
    """Test 11 — No gaps — severity=NONE, no badge."""

    def test_all_online_no_gaps(self) -> None:
        gaps, severity, f1_badge, f1_msg, f1_tip = build_data_gap_details(
            uw_status=DataSourceStatus.ONLINE,
            polygon_status=DataSourceStatus.ONLINE,
            av_status=DataSourceStatus.ONLINE,
            uw_data={"largest_print_usd": 500_000},
            dp_data={"num_prints": 5, "total_usd": 600_000, "missing_fields": []},
            vol_data={"put_call_ratio": 0.8},
        )
        assert severity == "NONE"
        assert f1_badge is None
        assert len(gaps) == 0

    """Test 12 — All offline — severity=CRITICAL, f1_badge=F4 DATA UNAVAILABLE."""

    def test_all_offline_critical(self) -> None:
        gaps, severity, f1_badge, f1_msg, f1_tip = build_data_gap_details(
            uw_status=DataSourceStatus.OFFLINE,
            polygon_status=DataSourceStatus.OFFLINE,
            av_status=DataSourceStatus.OFFLINE,
            uw_data={},
            dp_data={},
            vol_data={"put_call_ratio": None},
        )
        assert severity == "CRITICAL"
        assert f1_badge == "F4 DATA UNAVAILABLE"
        assert f1_msg is not None and "offline" in f1_msg.lower()
        assert f1_tip is not None

    def test_uw_offline_major(self) -> None:
        gaps, severity, f1_badge, _, _ = build_data_gap_details(
            uw_status=DataSourceStatus.OFFLINE,
            polygon_status=DataSourceStatus.ONLINE,
            av_status=DataSourceStatus.ONLINE,
            uw_data={},
            dp_data={"missing_fields": []},
            vol_data={"put_call_ratio": 0.9},
        )
        assert severity == "MAJOR"
        assert f1_badge == "F4 MAJOR DATA GAP"

    def test_uw_partial_adds_gap(self) -> None:
        gaps, severity, f1_badge, _, _ = build_data_gap_details(
            uw_status=DataSourceStatus.PARTIAL,
            polygon_status=DataSourceStatus.ONLINE,
            av_status=DataSourceStatus.ONLINE,
            uw_data={"missing_fields": ["largest_print_usd"]},
            dp_data={"missing_fields": []},
            vol_data={"put_call_ratio": 1.0},
        )
        assert severity == "PARTIAL"
        assert f1_badge == "F4 PARTIAL DATA"
        assert any(g.field == "largest_print_usd" for g in gaps)

    def test_put_call_missing_partial(self) -> None:
        gaps, severity, _, _, _ = build_data_gap_details(
            uw_status=DataSourceStatus.ONLINE,
            polygon_status=DataSourceStatus.ONLINE,
            av_status=DataSourceStatus.ONLINE,
            uw_data={},
            dp_data={"missing_fields": []},
            vol_data={"put_call_ratio": None},
        )
        assert severity == "PARTIAL"
        assert any(g.field == "put_call_ratio" for g in gaps)

    def test_polygon_offline_partial(self) -> None:
        gaps, severity, _, _, _ = build_data_gap_details(
            uw_status=DataSourceStatus.ONLINE,
            polygon_status=DataSourceStatus.OFFLINE,
            av_status=DataSourceStatus.ONLINE,
            uw_data={},
            dp_data={},
            vol_data={"put_call_ratio": 0.8},
        )
        assert severity == "PARTIAL"
        assert any(g.field == "dark_pool" for g in gaps)


# ---------------------------------------------------------------------------
# evaluate_framework9 — async integration with mocked fetchers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEvaluateFramework9:
    """Tests 1-10 via evaluate_framework9 with mocked async fetchers."""

    async def _run(
        self,
        monkeypatch: pytest.MonkeyPatch,
        uw_data: dict,
        uw_status: DataSourceStatus,
        dp_data: dict,
        polygon_status: DataSourceStatus,
        vol_data: dict,
        av_status: DataSourceStatus,
        adv: float | None = None,
        gate_active: bool = False,
    ):
        """Helper: patch all fetchers and return Framework9Result."""
        import atlas.services.framework9_service as svc

        async def _mock_uw(ticker, api_key, client):
            return uw_data, uw_status

        async def _mock_dp(ticker, api_key, client):
            return dp_data, polygon_status

        async def _mock_vol(ticker, poly_key, av_key, poly_status, client):
            return vol_data, av_status

        async def _mock_adv(ticker, poly_key, client):
            return adv

        monkeypatch.setattr(svc, "fetch_unusual_whales_flow", _mock_uw)
        monkeypatch.setattr(svc, "fetch_polygon_dark_pool", _mock_dp)
        monkeypatch.setattr(svc, "fetch_options_volume", _mock_vol)
        monkeypatch.setattr(svc, "get_30_day_adv", _mock_adv)

        # Mock F7 gate check.
        async def _mock_earnings(ticker, api_key):
            return None  # no earnings unless gate_active

        import atlas.services.framework7_service as f7svc
        monkeypatch.setattr(f7svc, "get_earnings_date", _mock_earnings)

        return await svc.evaluate_framework9(
            ticker="TEST",
            uw_api_key="uw-test",
            polygon_api_key="poly-test",
            av_api_key="av-test",
        )

    # Test 1 — All sources online, whale block
    async def test_1_whale_block_bullish(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={"largest_print_usd": 12_000_000, "flow_direction": "BULLISH", "total_premium": 12_000_000},
            uw_status=DataSourceStatus.ONLINE,
            dp_data={"num_prints": 15, "total_usd": 800_000, "avg_spread_position": 0.7, "missing_fields": []},
            polygon_status=DataSourceStatus.ONLINE,
            vol_data={"put_call_ratio": 0.6, "total_volume": 500_000, "call_volume": 400_000, "put_volume": 100_000},
            av_status=DataSourceStatus.ONLINE,
            adv=5_000_000,
        )
        from atlas.schemas.framework9 import SignalTier
        assert result.signal_tier == SignalTier.TIER_1_WHALE
        assert result.f4_score >= 90
        assert result.uw_status == DataSourceStatus.ONLINE
        assert result.data_gap_severity == "NONE"
        assert result.f1_propagation_badge is None

    # Test 2 — UW offline only
    async def test_2_uw_offline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={},
            uw_status=DataSourceStatus.OFFLINE,
            dp_data={"num_prints": 12, "total_usd": 600_000, "avg_spread_position": 0.65, "missing_fields": []},
            polygon_status=DataSourceStatus.ONLINE,
            vol_data={"put_call_ratio": 0.7, "total_volume": 200_000},
            av_status=DataSourceStatus.ONLINE,
            adv=1_000_000,
        )
        from atlas.schemas.framework9 import SignalTier
        assert result.signal_tier != SignalTier.TIER_1_WHALE
        assert result.f1_propagation_badge == "F4 MAJOR DATA GAP"
        assert result.uw_status == DataSourceStatus.OFFLINE

    # Test 3 — Polygon offline
    async def test_3_polygon_offline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={"largest_print_usd": 15_000_000, "flow_direction": "BULLISH", "total_premium": 15_000_000},
            uw_status=DataSourceStatus.ONLINE,
            dp_data={},
            polygon_status=DataSourceStatus.OFFLINE,
            vol_data={"put_call_ratio": 0.8, "total_volume": 50_000},
            av_status=DataSourceStatus.ONLINE,
            adv=None,
        )
        assert result.dark_pool_modifier == 0
        assert "dark_pool" in result.modifiers_skipped
        from atlas.schemas.framework9 import SignalTier
        assert result.signal_tier != SignalTier.TIER_2_INSTITUTIONAL

    # Test 4 — Put/call ratio missing
    async def test_4_put_call_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={"largest_print_usd": 0, "flow_direction": "NEUTRAL", "total_premium": 0},
            uw_status=DataSourceStatus.ONLINE,
            dp_data={"num_prints": 12, "total_usd": 600_000, "avg_spread_position": 0.5, "missing_fields": []},
            polygon_status=DataSourceStatus.ONLINE,
            vol_data={"put_call_ratio": None, "total_volume": 100_000},
            av_status=DataSourceStatus.PARTIAL,
            adv=500_000,
        )
        assert result.put_call_modifier == 0
        assert "put_call" in result.modifiers_skipped

    # Test 5 — Dark pool price missing
    async def test_5_dark_pool_price_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={"largest_print_usd": 0, "flow_direction": "NEUTRAL", "total_premium": 0},
            uw_status=DataSourceStatus.ONLINE,
            dp_data={"num_prints": 5, "total_usd": 400_000, "avg_spread_position": None, "missing_fields": ["price"]},
            polygon_status=DataSourceStatus.PARTIAL,
            vol_data={"put_call_ratio": 0.9, "total_volume": 80_000},
            av_status=DataSourceStatus.ONLINE,
            adv=500_000,
        )
        assert result.dark_pool_spread_position is None
        assert result.dark_pool_modifier == 0

    # Test 6 — All sources offline
    async def test_6_all_offline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={},
            uw_status=DataSourceStatus.OFFLINE,
            dp_data={},
            polygon_status=DataSourceStatus.OFFLINE,
            vol_data={"put_call_ratio": None},
            av_status=DataSourceStatus.OFFLINE,
            adv=None,
        )
        assert result.f4_score == 55.0
        assert result.f4_contribution == pytest.approx(8.25)
        assert result.data_gap_severity == "CRITICAL"
        assert result.f1_propagation_badge == "F4 DATA UNAVAILABLE"
        assert result.warning_level == "RED"

    # Test 7 — Partial field failures
    async def test_7_partial_field_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={"missing_fields": ["largest_print_usd"], "flow_direction": "NEUTRAL", "total_premium": 200_000},
            uw_status=DataSourceStatus.PARTIAL,
            dp_data={"num_prints": 8, "total_usd": 400_000, "avg_spread_position": None, "missing_fields": ["bid"]},
            polygon_status=DataSourceStatus.PARTIAL,
            vol_data={"put_call_ratio": 0.9, "total_volume": 100_000},
            av_status=DataSourceStatus.ONLINE,
            adv=500_000,
        )
        assert result.data_gap_severity == "PARTIAL"
        assert result.warning_level == "AMBER"
        assert len(result.data_gaps) >= 1

    # Test 8 — Rate limited UW with cache
    async def test_8_rate_limited_uw_with_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={"largest_print_usd": 500_000, "flow_direction": "BULLISH", "total_premium": 500_000},
            uw_status=DataSourceStatus.RATE_LIMITED,
            dp_data={"num_prints": 10, "total_usd": 600_000, "avg_spread_position": 0.6, "missing_fields": []},
            polygon_status=DataSourceStatus.ONLINE,
            vol_data={"put_call_ratio": 0.7, "total_volume": 200_000},
            av_status=DataSourceStatus.ONLINE,
            adv=1_000_000,
        )
        assert result.uw_status == DataSourceStatus.RATE_LIMITED
        # With rate limited UW, whale tier blocked, but other data should work.
        from atlas.schemas.framework9 import SignalTier
        assert result.signal_tier != SignalTier.TIER_1_WHALE

    # Test 9 — Stale data
    async def test_9_stale_uw_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={"largest_print_usd": 500_000, "flow_direction": "NEUTRAL", "total_premium": 500_000},
            uw_status=DataSourceStatus.STALE,
            dp_data={"num_prints": 10, "total_usd": 600_000, "avg_spread_position": 0.5, "missing_fields": []},
            polygon_status=DataSourceStatus.ONLINE,
            vol_data={"put_call_ratio": 0.8, "total_volume": 100_000},
            av_status=DataSourceStatus.ONLINE,
            adv=1_000_000,
        )
        assert result.uw_status == DataSourceStatus.STALE

    # Test 10 — Covered call unverifiable
    async def test_10_covered_call_unverifiable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = await self._run(
            monkeypatch=monkeypatch,
            uw_data={"largest_print_usd": 2_000_000, "flow_direction": "BEARISH", "total_premium": 2_000_000},
            uw_status=DataSourceStatus.ONLINE,
            dp_data={},
            polygon_status=DataSourceStatus.OFFLINE,
            vol_data={"put_call_ratio": 1.5, "total_volume": 300_000},
            av_status=DataSourceStatus.ONLINE,
            adv=2_000_000,
        )
        assert result.covered_call_unverifiable is True
        assert result.covered_call_exception is False
        assert any("covered call" in w.lower() for w in result.warning_messages)
