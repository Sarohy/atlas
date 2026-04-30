"""Unit tests for Framework 9 — Options Flow Signal Hierarchy.

All tests are synchronous (pure helpers) or use pytest-asyncio for the async
evaluation function.  Network I/O is fully mocked via pytest monkeypatch and
direct injection of pre-built data dicts to the pure build_data_gap_details
helper.

Test map (12 original + new spec-compliance tests):
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
  Test 13 — Score constants are within spec-defined ranges
  Test 14 — evaluate_exceptional_conviction zero criteria → not active
  Test 15 — evaluate_exceptional_conviction 3-of-5 → active
  Test 16 — evaluate_exceptional_conviction 2-of-5 → not active
  Test 17 — evaluate_exceptional_conviction None criteria count as False
  Test 18 — Pre-earnings 25% reduction applied within 0-7 day window
  Test 19 — No reduction when earnings > 7 days away
  Test 20 — Exceptional Conviction blocks reduction; +10% premium applied
"""

from __future__ import annotations

import pytest

from atlas.schemas.framework9 import DataGapDetail, DataSourceStatus
from atlas.services.framework9_service import (
    _grade_from_score,
    _resolve_spread_position,
    build_data_gap_details,
    evaluate_exceptional_conviction,
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
# evaluate_framework9 — async integration with mocked OptionsFlowService
# ---------------------------------------------------------------------------


def _build_mock_f4(
    uw_data: dict,
    uw_status: DataSourceStatus,
    dp_data: dict,
    polygon_status: DataSourceStatus,
    vol_data: dict,
) -> object:
    """Build a synthetic OptionsFlowResponse from legacy test input dicts.

    Mirrors the F4 data structure that evaluate_framework9 now consumes.
    """
    from atlas.schemas.options_flow import (
        CallPutRatioIndicator,
        DarkPoolIndicator,
        OptionsFlowResponse,
        SweepTypeIndicator,
        VolumeOiIndicator,
        WhaleBlockIndicator,
    )

    # --- Whale block ---
    largest_premium: float | None = (
        float(uw_data.get("largest_print_usd") or 0.0) or None
    )
    if uw_status in (DataSourceStatus.PARTIAL,):
        # Partial UW — respect missing_fields from test data
        if "largest_print_usd" in uw_data.get("missing_fields", []):
            largest_premium = None

    # --- Dark pool ---
    if polygon_status == DataSourceStatus.OFFLINE:
        dp_total: float | None = None
        dp_count = 0
    else:
        dp_total = float(dp_data.get("total_usd") or 0.0) or None
        dp_count = int(dp_data.get("num_prints", 0))

    # --- Call/put ratio (prefer call_volume/put_volume over inverted pc_ratio) ---
    cp_ratio: float | None
    call_v = vol_data.get("call_volume")
    put_v = vol_data.get("put_volume")
    pc_ratio = vol_data.get("put_call_ratio")
    if call_v and put_v and float(put_v) > 0:
        cp_ratio = float(call_v) / float(put_v)
    elif pc_ratio is not None and float(pc_ratio) > 0:
        cp_ratio = 1.0 / float(pc_ratio)
    else:
        cp_ratio = None

    # --- Signal tier → spec-aligned midpoint score ---
    whale_val = float(largest_premium or 0.0)
    if (
        whale_val >= 10_000_000
        and uw_status not in (DataSourceStatus.RATE_LIMITED, DataSourceStatus.STALE)
    ):
        tier_str = "GOLD"
        # Score 92 (TIER_1 midpoint per spec)
        f4_score_raw = 92
    elif whale_val >= 1_000_000:
        tier_str = "BLUE"
        f4_score_raw = 86
    elif dp_total is not None and dp_total >= 500_000:
        tier_str = "GREEN"
        f4_score_raw = 82
    elif whale_val >= 100_000:
        tier_str = "GREY"
        f4_score_raw = 74
    else:
        tier_str = "WHITE"
        f4_score_raw = 66

    # Rate-limited/stale caps at GREY (no whale confirmation).
    if uw_status in (DataSourceStatus.RATE_LIMITED, DataSourceStatus.STALE):
        if tier_str in ("GOLD", "BLUE"):
            tier_str = "GREY"
            f4_score_raw = 74

    f4_grade = (
        "STRONG BUY" if f4_score_raw >= 80 else "BUY" if f4_score_raw >= 60 else "NEUTRAL"
    )

    return OptionsFlowResponse(
        ticker="TEST",
        whale_block=WhaleBlockIndicator(
            largest_premium=largest_premium,
            score=100 if tier_str in ("GOLD",) else 85 if tier_str == "BLUE" else 30,
        ),
        call_put_ratio=CallPutRatioIndicator(
            call_premium=None,
            put_premium=None,
            ratio=cp_ratio,
            score=70,
        ),
        volume_oi=VolumeOiIndicator(
            call_volume=None, call_open_interest=None, vol_oi_ratio=None, score=70
        ),
        dark_pool=DarkPoolIndicator(
            total_dark_pool_premium=dp_total,
            largest_print=dp_total,
            print_count=dp_count,
            score=80 if dp_total and dp_total >= 1_000_000 else 50 if dp_total else 30,
        ),
        sweep_type=SweepTypeIndicator(
            has_golden_sweep=tier_str == "GOLD",
            has_single_sweep=False,
            has_repeated_hits=False,
            sweep_premium=None,
            score=40,
        ),
        signal_tier=tier_str,
        collar_flag=False,
        f4_score=f4_score_raw,
        f4_grade=f4_grade,
    )


@pytest.mark.asyncio
class TestEvaluateFramework9:
    """Tests 1-10 via evaluate_framework9 with mocked OptionsFlowService + F7."""

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
        """Patch OptionsFlowService and earnings date, then call evaluate_framework9."""
        import atlas.services.framework9_service as svc
        import atlas.services.framework7_service as f7svc
        from atlas.services.options_flow_service import OptionsFlowService
        from atlas.config import Settings

        if uw_status == DataSourceStatus.OFFLINE and polygon_status == DataSourceStatus.OFFLINE:
            # Both primary sources offline → F4 service fails → degraded path.
            async def _mock_f4_fn(self_: OptionsFlowService, ticker: str) -> None:
                raise RuntimeError("All sources offline")

            monkeypatch.setattr(OptionsFlowService, "compute_options_flow", _mock_f4_fn)
        elif uw_status == DataSourceStatus.OFFLINE:
            # UW offline but polygon available → F4 returns limited (no whale data).
            mock_f4 = _build_mock_f4(
                uw_data={},  # no UW data
                uw_status=uw_status,
                dp_data=dp_data,
                polygon_status=polygon_status,
                vol_data=vol_data,
            )

            async def _mock_f4_fn(self_: OptionsFlowService, ticker: str):  # type: ignore[misc]
                return mock_f4

            monkeypatch.setattr(OptionsFlowService, "compute_options_flow", _mock_f4_fn)
        else:
            mock_f4 = _build_mock_f4(
                uw_data=uw_data,
                uw_status=uw_status,
                dp_data=dp_data,
                polygon_status=polygon_status,
                vol_data=vol_data,
            )

            async def _mock_f4_fn(self_: OptionsFlowService, ticker: str):  # type: ignore[misc]
                return mock_f4

            monkeypatch.setattr(OptionsFlowService, "compute_options_flow", _mock_f4_fn)

        # No earnings date by default.
        async def _mock_earnings(ticker: str, api_key: str) -> None:
            return None

        monkeypatch.setattr(f7svc, "get_earnings_date", _mock_earnings)

        import atlas.config as atlas_config
        from atlas.config import Settings
        monkeypatch.setattr(
            atlas_config,
            "get_settings",
            lambda: Settings(
                database_url="postgresql+asyncpg://localhost/test",
                alphavantage_api_key="test",
            ),
        )

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

    # Test 2 — UW offline only (polygon available → limited F4, not total failure)
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
        # UW offline → no whale data → whale tier blocked
        assert result.signal_tier != SignalTier.TIER_1_WHALE
        # F4 still returned (polygon available) but whale data missing → MAJOR gap
        assert result.f1_propagation_badge == "F4 MAJOR DATA GAP"
        assert result.data_gap_severity == "MAJOR"

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

    # Test 6 — All sources offline → OptionsFlowService raises → degraded baseline
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

    # Test 7 — Partial field failures (UW PARTIAL → whale data missing from F4)
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
        # largest_print_usd missing from F4 → PARTIAL gap detected
        assert result.data_gap_severity in ("PARTIAL", "MAJOR")
        assert result.warning_level in ("AMBER", "RED")
        assert len(result.data_gaps) >= 1

    # Test 8 — Rate limited UW (whale tier blocked — unconfirmed without fresh data)
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
        # Rate-limited UW → mock caps signal tier below TIER_1_WHALE
        from atlas.schemas.framework9 import SignalTier
        assert result.signal_tier != SignalTier.TIER_1_WHALE
        # Result is valid (F4 returned a response)
        assert result.f4_score > 0

    # Test 9 — Stale data (evaluation proceeds but no whale tier confirmation)
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
        # Stale UW → mock caps tier; result is still returned
        assert result.f4_score > 0
        from atlas.schemas.framework9 import SignalTier
        assert result.signal_tier != SignalTier.TIER_1_WHALE

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


# ---------------------------------------------------------------------------
# Test 13 — Score constants within spec-defined ranges
# ---------------------------------------------------------------------------


class TestScoreConstants:
    """Verify all score constants are within the ranges defined by the spec."""

    def test_tier1_bullish_in_spec_range(self) -> None:
        # Spec: $10M+ whale block confirmed → 88-92
        from atlas.services.framework9_service import _SCORE_TIER1_BULLISH
        assert 88.0 <= _SCORE_TIER1_BULLISH <= 92.0

    def test_tier2_base_in_spec_range(self) -> None:
        # Spec: dark pool accumulation $500K+ → 80-85
        from atlas.services.framework9_service import _SCORE_TIER2_BASE
        assert 80.0 <= _SCORE_TIER2_BASE <= 85.0

    def test_tier3_base_in_spec_range(self) -> None:
        # Spec: 150%+ above normal call volume → 78-82
        from atlas.services.framework9_service import _SCORE_TIER3_BASE
        assert 78.0 <= _SCORE_TIER3_BASE <= 82.0

    def test_tier4_base_in_spec_range(self) -> None:
        # Spec: moderate unusual call activity → 72-76
        from atlas.services.framework9_service import _SCORE_TIER4_BASE
        assert 72.0 <= _SCORE_TIER4_BASE <= 76.0

    def test_tier5_baseline_in_spec_range(self) -> None:
        # Spec: normal baseline activity → 65-68
        from atlas.services.framework9_service import _SCORE_TIER5_BASELINE
        assert 65.0 <= _SCORE_TIER5_BASELINE <= 68.0

    def test_tier1_bearish_in_spec_range(self) -> None:
        # Spec: bearish put flow (genuine, not covered calls) → 55-65
        from atlas.services.framework9_service import _SCORE_TIER1_BEARISH
        assert 55.0 <= _SCORE_TIER1_BEARISH <= 65.0

    def test_pre_earnings_reduction_pct_is_25(self) -> None:
        # Spec: normal pre-earnings 0-7 days → 25% reduction
        from atlas.services.framework9_service import _PRE_EARNINGS_REDUCTION_PCT
        assert _PRE_EARNINGS_REDUCTION_PCT == pytest.approx(0.25)

    def test_pre_earnings_window_is_7_days(self) -> None:
        # Spec: reduction window is 0-7 days before earnings
        from atlas.services.framework9_service import _PRE_EARNINGS_WINDOW_DAYS
        assert _PRE_EARNINGS_WINDOW_DAYS == 7


# ---------------------------------------------------------------------------
# Tests 14-17 — evaluate_exceptional_conviction pure helper
# ---------------------------------------------------------------------------


class TestEvaluateExceptionalConviction:
    """Spec: 3-of-5 Exceptional Conviction criteria → override pre-earnings reduction."""

    def test_14_zero_criteria_not_active(self) -> None:
        result = evaluate_exceptional_conviction(
            dark_pool_blocks_gt_1m_count=0,
            transcript_conviction_language=False,
            guidance_raised_above_high=False,
            transcript_cross_references_ge5=False,
            bullish_skew_despite_elevated_iv=False,
        )
        assert result.count == 0
        assert result.active is False

    def test_15_three_criteria_active(self) -> None:
        # Criteria 1, 2, 5 met
        result = evaluate_exceptional_conviction(
            dark_pool_blocks_gt_1m_count=2,  # criterion 1: multiple blocks >$1M
            transcript_conviction_language=True,  # criterion 2
            guidance_raised_above_high=False,
            transcript_cross_references_ge5=False,
            bullish_skew_despite_elevated_iv=True,  # criterion 5
        )
        assert result.count == 3
        assert result.active is True
        assert result.dark_pool_multiple_blocks_gt_1m is True
        assert result.transcript_conviction_language is True
        assert result.bullish_skew_despite_elevated_iv is True

    def test_16_two_criteria_not_active(self) -> None:
        result = evaluate_exceptional_conviction(
            dark_pool_blocks_gt_1m_count=2,  # criterion 1 met
            transcript_conviction_language=True,  # criterion 2 met
            guidance_raised_above_high=False,
            transcript_cross_references_ge5=False,
            bullish_skew_despite_elevated_iv=False,
        )
        assert result.count == 2
        assert result.active is False

    def test_17_none_criteria_count_as_false(self) -> None:
        # None means "not evaluated" — does not contribute to count
        result = evaluate_exceptional_conviction(
            dark_pool_blocks_gt_1m_count=2,  # criterion 1 met
            transcript_conviction_language=None,  # not evaluated
            guidance_raised_above_high=None,  # not evaluated
            transcript_cross_references_ge5=None,  # not evaluated
            bullish_skew_despite_elevated_iv=True,  # criterion 5 met
        )
        assert result.count == 2  # only criteria 1 and 5
        assert result.active is False

    def test_all_five_criteria_active(self) -> None:
        result = evaluate_exceptional_conviction(
            dark_pool_blocks_gt_1m_count=3,
            transcript_conviction_language=True,
            guidance_raised_above_high=True,
            transcript_cross_references_ge5=True,
            bullish_skew_despite_elevated_iv=True,
        )
        assert result.count == 5
        assert result.active is True

    def test_single_dark_pool_block_not_criterion_1(self) -> None:
        # Spec: "multiple blocks" — single block does not meet criterion 1
        result = evaluate_exceptional_conviction(
            dark_pool_blocks_gt_1m_count=1,  # only 1 block, need >= 2
            transcript_conviction_language=False,
            guidance_raised_above_high=False,
            transcript_cross_references_ge5=False,
            bullish_skew_despite_elevated_iv=False,
        )
        assert result.dark_pool_multiple_blocks_gt_1m is False
        assert result.count == 0


# ---------------------------------------------------------------------------
# Tests 18-20 — pre-earnings reduction via evaluate_framework9
# ---------------------------------------------------------------------------


def _make_f4_response(
    *,
    f4_score: int = 80,
    signal_tier: str = "BLUE",
    largest_premium: float | None = 2_000_000,
    cp_ratio: float | None = 1.5,
    dp_total: float | None = 300_000,
    dp_count: int = 5,
) -> "object":
    """Build a minimal mock OptionsFlowResponse for pre-earnings and EC tests."""
    from atlas.schemas.options_flow import (
        CallPutRatioIndicator,
        DarkPoolIndicator,
        OptionsFlowResponse,
        SweepTypeIndicator,
        VolumeOiIndicator,
        WhaleBlockIndicator,
    )

    return OptionsFlowResponse(
        ticker="TEST",
        whale_block=WhaleBlockIndicator(largest_premium=largest_premium, score=85),
        call_put_ratio=CallPutRatioIndicator(
            call_premium=(cp_ratio or 1.0) * 100_000,
            put_premium=100_000,
            ratio=cp_ratio,
            score=70,
        ),
        volume_oi=VolumeOiIndicator(
            call_volume=100_000, call_open_interest=50_000, vol_oi_ratio=2.0, score=70
        ),
        dark_pool=DarkPoolIndicator(
            total_dark_pool_premium=dp_total,
            largest_print=dp_total,
            print_count=dp_count,
            score=50,
        ),
        sweep_type=SweepTypeIndicator(
            has_golden_sweep=False,
            has_single_sweep=False,
            has_repeated_hits=False,
            sweep_premium=None,
            score=40,
        ),
        signal_tier=signal_tier,
        collar_flag=False,
        f4_score=f4_score,
        f4_grade="BUY",
    )


@pytest.mark.asyncio
class TestPreEarningsReduction:
    """Tests 18-20 — spec: 25% reduction for 0-7 days; EC overrides."""

    async def _run_with_earnings(
        self,
        monkeypatch: pytest.MonkeyPatch,
        days_to_earnings: int | None,
        base_f4_score: int = 80,
        transcript_conviction_language: bool | None = None,
        guidance_raised_above_high: bool | None = None,
        transcript_cross_references_ge5: bool | None = None,
        dp_count: int = 1,
        cp_ratio: float | None = 1.5,
    ):
        import atlas.services.framework9_service as svc
        from atlas.services.options_flow_service import OptionsFlowService
        from atlas.config import Settings
        from datetime import date

        mock_f4 = _make_f4_response(
            f4_score=base_f4_score,
            dp_count=dp_count,
            cp_ratio=cp_ratio,
        )

        async def _mock_f4(self_: OptionsFlowService, ticker: str):
            return mock_f4

        monkeypatch.setattr(OptionsFlowService, "compute_options_flow", _mock_f4)

        if days_to_earnings is not None:
            earnings_date = date.today().replace(
                year=date.today().year + (1 if (date.today().toordinal() + days_to_earnings) > 365 else 0)
            )
            from datetime import timedelta
            earnings_date_str = (date.today() + timedelta(days=days_to_earnings)).isoformat()

            async def _mock_earnings(ticker, api_key):
                return earnings_date_str
        else:
            async def _mock_earnings(ticker, api_key):
                return None

        import atlas.services.framework7_service as f7svc
        monkeypatch.setattr(f7svc, "get_earnings_date", _mock_earnings)

        import atlas.config as atlas_config
        monkeypatch.setattr(
            atlas_config,
            "get_settings",
            lambda: Settings(
                database_url="postgresql+asyncpg://localhost/test",
                alphavantage_api_key="test",
            ),
        )

        return await svc.evaluate_framework9(
            ticker="TEST",
            uw_api_key="uw-test",
            polygon_api_key="poly-test",
            av_api_key="av-test",
            transcript_conviction_language=transcript_conviction_language,
            guidance_raised_above_high=guidance_raised_above_high,
            transcript_cross_references_ge5=transcript_cross_references_ge5,
        )

    async def test_18_25pct_reduction_within_7_days(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 5 days to earnings → 25% reduction
        result = await self._run_with_earnings(
            monkeypatch=monkeypatch,
            days_to_earnings=5,
            base_f4_score=80,
        )
        assert result.pre_earnings_reduction is True
        # 25% of 80 = 20 points reduction
        assert result.pre_earnings_modifier == -20
        assert result.f4_score == pytest.approx(60.0)

    async def test_19_no_reduction_8_days_out(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 8 days to earnings → outside window, no reduction
        result = await self._run_with_earnings(
            monkeypatch=monkeypatch,
            days_to_earnings=8,
            base_f4_score=80,
        )
        assert result.pre_earnings_reduction is False
        assert result.pre_earnings_modifier == 0
        assert result.f4_score == pytest.approx(80.0)

    async def test_20_exceptional_conviction_blocks_reduction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 3 days to earnings + 3-of-5 EC criteria → +10% premium instead of reduction
        result = await self._run_with_earnings(
            monkeypatch=monkeypatch,
            days_to_earnings=3,
            base_f4_score=80,
            # EC criterion 2 and 3 via manual inputs
            transcript_conviction_language=True,
            guidance_raised_above_high=True,
            # EC criterion 1: need dp_count >= 2 AND dp > $1M
            # Use default dp_count=1 so criterion 1 is NOT met;
            # criterion 5 requires bullish skew → cp_ratio > 2.0 + BULLISH
            # With cp_ratio=2.5 we get criterion 5 too (3-of-5: 2+3+5)
            cp_ratio=2.5,
        )
        # Exceptional Conviction should be active (criteria 2+3+5)
        assert result.pre_earnings_reduction is True  # window is active
        assert result.exceptional_conviction is not None
        assert result.exceptional_conviction.active is True
        # +10% premium: 10% of 80 = 8 → modifier is +8
        assert result.pre_earnings_modifier == 8
        assert result.f4_score == pytest.approx(88.0)

    async def test_no_reduction_when_no_earnings_date(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = await self._run_with_earnings(
            monkeypatch=monkeypatch,
            days_to_earnings=None,
            base_f4_score=80,
        )
        assert result.pre_earnings_reduction is False
        assert result.pre_earnings_modifier == 0
