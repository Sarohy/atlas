"""Unit tests for the ATLAS Overbought / Extension Overlay engine + service."""

from __future__ import annotations

import math

from atlas.core import extension as ext
from atlas.core.extension import ExtensionFlag, OverlayAction
from atlas.services.extension_overlay_service import ExtensionOverlayService

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


class TestMetricHelpers:
    def test_rsi_all_up_series_is_100(self) -> None:
        closes = [float(i) for i in range(1, 30)]
        assert ext.compute_rsi(closes, 14) == 100.0

    def test_rsi_flat_series_is_50(self) -> None:
        closes = [100.0] * 30
        assert ext.compute_rsi(closes, 14) == 50.0

    def test_rsi_none_when_insufficient(self) -> None:
        assert ext.compute_rsi([1.0, 2.0], 14) is None

    def test_pct_move(self) -> None:
        closes = [100.0] * 10 + [110.0]  # +10% over 1 session
        assert ext.pct_move(closes, 1) == 10.0

    def test_pct_move_none_when_insufficient(self) -> None:
        assert ext.pct_move([100.0], 14) is None

    def test_simple_ma(self) -> None:
        assert ext.simple_ma([10.0, 20.0, 30.0], 3) == 20.0

    def test_pct_above_ma(self) -> None:
        assert ext.pct_above_ma(110.0, 100.0) == 10.0

    def test_pct_above_ma_none_safe(self) -> None:
        assert ext.pct_above_ma(110.0, None) is None
        assert ext.pct_above_ma(110.0, 0.0) is None

    def test_gap_pct(self) -> None:
        assert ext.gap_pct(105.0, 100.0) == 5.0
        assert ext.gap_pct(None, 100.0) is None
        assert ext.gap_pct(105.0, 0) is None


# ---------------------------------------------------------------------------
# Extension Risk Score points table
# ---------------------------------------------------------------------------


class TestExtensionRiskScore:
    def test_all_calm_is_zero(self) -> None:
        assert (
            ext.extension_risk_score(
                rsi14=50,
                rsi7=50,
                move14_pct=2,
                move21_pct=3,
                pct_above_20dma=1,
                pct_above_50dma=2,
                pct_above_200dma=5,
                gap_today_pct=0,
                iv_rank=10,
            )
            == 0
        )

    def test_missing_metrics_score_zero_not_penalty(self) -> None:
        assert (
            ext.extension_risk_score(
                rsi14=None,
                rsi7=None,
                move14_pct=None,
                move21_pct=None,
                pct_above_20dma=None,
                pct_above_50dma=None,
                pct_above_200dma=None,
                gap_today_pct=None,
                iv_rank=None,
            )
            == 0
        )

    def test_rsi14_overbought_vs_extreme_do_not_stack(self) -> None:
        base = {
            "rsi7": 50,
            "move14_pct": 0,
            "move21_pct": 0,
            "pct_above_20dma": 0,
            "pct_above_50dma": 0,
            "pct_above_200dma": 0,
            "gap_today_pct": 0,
            "iv_rank": 0,
        }
        assert ext.extension_risk_score(rsi14=75, **base) == 2  # overbought
        assert ext.extension_risk_score(rsi14=85, **base) == 3  # extreme replaces, not +5

    def test_move14_extreme_replaces_vertical(self) -> None:
        base = {
            "rsi14": 50,
            "rsi7": 50,
            "move21_pct": 0,
            "pct_above_20dma": 0,
            "pct_above_50dma": 0,
            "pct_above_200dma": 0,
            "gap_today_pct": 0,
            "iv_rank": 0,
        }
        assert ext.extension_risk_score(move14_pct=25, **base) == 2
        assert ext.extension_risk_score(move14_pct=40, **base) == 3

    def test_fully_extended_sums_all_triggers(self) -> None:
        # RSI14>80 (3) + RSI7>75 (2) + move14>35 (3) + move21>30 (2)
        # + 20dma>15 (2) + 50dma>25 (2) + 200dma>50 (1) + gap>5 (2) + iv>70 (1) = 18
        assert (
            ext.extension_risk_score(
                rsi14=85,
                rsi7=80,
                move14_pct=40,
                move21_pct=35,
                pct_above_20dma=20,
                pct_above_50dma=30,
                pct_above_200dma=60,
                gap_today_pct=6,
                iv_rank=80,
            )
            == 18
        )


# ---------------------------------------------------------------------------
# Flag classification
# ---------------------------------------------------------------------------


class TestFlag:
    def test_buckets(self) -> None:
        assert ext.classify_extension_flag(0) == ExtensionFlag.GREEN
        assert ext.classify_extension_flag(2) == ExtensionFlag.GREEN
        assert ext.classify_extension_flag(3) == ExtensionFlag.YELLOW
        assert ext.classify_extension_flag(5) == ExtensionFlag.YELLOW
        assert ext.classify_extension_flag(6) == ExtensionFlag.RED
        assert ext.classify_extension_flag(8) == ExtensionFlag.RED
        assert ext.classify_extension_flag(9) == ExtensionFlag.EXTREME_RED
        assert ext.classify_extension_flag(18) == ExtensionFlag.EXTREME_RED


# ---------------------------------------------------------------------------
# Action matrix
# ---------------------------------------------------------------------------


class TestActionMatrix:
    def test_high_conviction_matrix(self) -> None:
        assert ext.recommend_action(90, ExtensionFlag.GREEN)[0] == OverlayAction.ADD
        assert ext.recommend_action(90, ExtensionFlag.YELLOW)[0] == OverlayAction.BUY_ON_PULLBACK
        assert ext.recommend_action(89, ExtensionFlag.RED)[0] == OverlayAction.HOLD_TRIM
        assert ext.recommend_action(89, ExtensionFlag.EXTREME_RED)[0] == OverlayAction.TRIM_HEDGE

    def test_low_conviction_never_buys(self) -> None:
        assert ext.recommend_action(45, ExtensionFlag.GREEN)[0] == OverlayAction.AVOID
        assert ext.recommend_action(45, ExtensionFlag.RED)[0] == OverlayAction.AVOID

    def test_threshold_boundary_70_is_high(self) -> None:
        assert ext.recommend_action(70, ExtensionFlag.GREEN)[0] == OverlayAction.ADD
        assert ext.recommend_action(69, ExtensionFlag.GREEN)[0] == OverlayAction.AVOID

    def test_no_atlas_score_omits_action(self) -> None:
        assert ext.recommend_action(None, ExtensionFlag.GREEN) == (None, None)


# ---------------------------------------------------------------------------
# F1 overbought cap (returned on the 0-100 raw scale)
# ---------------------------------------------------------------------------


class TestF1OverboughtCap:
    def test_multi_metric_extreme_caps_at_75(self) -> None:
        assert (
            ext.f1_overbought_cap(rsi14=85, move14_pct=40, pct_above_50dma=5, gap_today_pct=6)
            == 75
        )

    def test_single_metric_caps_at_85(self) -> None:
        cap = ext.f1_overbought_cap
        assert cap(rsi14=85, move14_pct=0, pct_above_50dma=0, gap_today_pct=0) == 85
        assert cap(rsi14=50, move14_pct=40, pct_above_50dma=0, gap_today_pct=0) == 85
        assert cap(rsi14=50, move14_pct=0, pct_above_50dma=30, gap_today_pct=0) == 85

    def test_no_cap_when_not_overbought(self) -> None:
        assert (
            ext.f1_overbought_cap(rsi14=60, move14_pct=10, pct_above_50dma=10, gap_today_pct=0)
            is None
        )

    def test_none_inputs_do_not_trip(self) -> None:
        assert (
            ext.f1_overbought_cap(
                rsi14=None, move14_pct=None, pct_above_50dma=None, gap_today_pct=None
            )
            is None
        )


# ---------------------------------------------------------------------------
# Service response assembly (no network — uses synthetic bars)
# ---------------------------------------------------------------------------


def _bars(closes: list[float]) -> list[dict]:
    """Build minimal ascending OHLC(V+VWAP) bars from a close series."""
    bars = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i > 0 else c
        bars.append({"o": prev, "h": c, "l": c, "c": c, "vw": c, "t": i})
    return bars


class TestServiceResponse:
    def test_calm_range_is_green_with_metrics(self) -> None:
        # Oscillating, trendless series → mid-range RSI, no extension → GREEN.
        closes = [100.0 + math.sin(i / 4) for i in range(260)]
        resp = ExtensionOverlayService._build_response("aapl", _bars(closes), atlas_score=90)
        assert resp.ticker == "AAPL"
        assert resp.rsi_14 is not None
        assert resp.pct_above_50dma is not None
        assert resp.extension_flag == ExtensionFlag.GREEN
        assert resp.action == OverlayAction.ADD
        assert "IV_RANK" in resp.data_gaps

    def test_parabolic_run_flags_and_blocks_chase(self) -> None:
        closes = [100.0] * 240 + [100.0 * (1.04 ** i) for i in range(1, 21)]  # vertical ramp
        resp = ExtensionOverlayService._build_response("xyz", _bars(closes), atlas_score=92)
        assert resp.extension_flag in (ExtensionFlag.RED, ExtensionFlag.EXTREME_RED)
        assert resp.action in (OverlayAction.HOLD_TRIM, OverlayAction.TRIM_HEDGE)

    def test_no_bars_yields_data_gap(self) -> None:
        resp = ExtensionOverlayService._build_response("aapl", [], atlas_score=None)
        assert "PRICE_BARS" in resp.data_gaps
        assert resp.rsi_14 is None
        assert resp.action is None

    def test_iv_rank_threaded_when_supplied(self) -> None:
        closes = [100.0 + math.sin(i / 4) for i in range(260)]
        # Without IV rank → DATA_GAP and no IV contribution.
        without = ExtensionOverlayService._build_response("aapl", _bars(closes), 90, None)
        assert without.iv_rank is None
        assert "IV_RANK" in without.data_gaps
        # With an expensive IV rank (>70) → surfaced, no gap, +1 to risk.
        with_iv = ExtensionOverlayService._build_response("aapl", _bars(closes), 90, 85.0)
        assert with_iv.iv_rank == 85.0
        assert "IV_RANK" not in with_iv.data_gaps
        assert with_iv.extension_risk_score == without.extension_risk_score + 1

    def test_daily_vwap_is_surfaced(self) -> None:
        closes = [100.0 + math.sin(i / 4) for i in range(260)]
        resp = ExtensionOverlayService._build_response("aapl", _bars(closes), None)
        assert resp.vwap is not None
        assert resp.pct_vs_vwap is not None
        assert "VWAP" not in resp.data_gaps


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - trivial
        return None

    def json(self) -> object:
        return self._payload


class _FakeClient:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    async def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
        return _FakeResponse(self._payload)


class TestIvRankFetch:
    """Locks the UW iv-rank response shape (data is a LIST of daily records)."""

    async def test_parses_latest_iv_rank_1y_on_0_100_scale(self) -> None:
        payload = {
            "data": [
                {"date": "2026-06-04", "iv_rank_1y": "61.40"},
                {"date": "2026-06-05", "iv_rank_1y": "75.18"},
            ]
        }
        svc = ExtensionOverlayService(api_key="poly", uw_api_key="uw")
        iv = await svc._fetch_iv_rank(_FakeClient(payload), "AAOI")  # type: ignore[arg-type]
        assert iv == 75.18

    async def test_empty_or_unexpected_shape_returns_none(self) -> None:
        svc = ExtensionOverlayService(api_key="poly", uw_api_key="uw")
        # Old (wrong) assumption: data as a dict → must degrade to None, not crash.
        assert await svc._fetch_iv_rank(_FakeClient({"data": {"iv": 0.3}}), "X") is None  # type: ignore[arg-type]
        assert await svc._fetch_iv_rank(_FakeClient({"data": []}), "X") is None  # type: ignore[arg-type]

    def test_metrics_are_finite(self) -> None:
        closes = [100.0 + math.sin(i / 5) * 5 for i in range(260)]
        resp = ExtensionOverlayService._build_response("aapl", _bars(closes), atlas_score=None)
        for value in (resp.rsi_14, resp.move_14d_pct, resp.pct_above_50dma):
            assert value is None or math.isfinite(value)
