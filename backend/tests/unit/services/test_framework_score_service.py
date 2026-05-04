"""Unit tests for FrameworkScoreService pure helpers and classify_tier SSOT.

TDD — covers deterministic pure functions (no I/O).

Pure functions under test:
  classify_tier      — score → TierResult (ATLAS v7.3.5 Section 13.3 SSOT)
  _map_action        — final_score → (action, action_tone) via classify_tier
  _compute_raw_total — (f1,f2,f3,f4,f5) → weighted sum (max 100)
  _compute_final_score — raw_total → clamped int [0,100]

Integration contracts:
  TestFetchF4UsesFramework9 — _fetch_f4 must delegate to evaluate_framework9
                              (not raw OptionsFlowService) so that pre-earnings
                              modifiers are applied before F1 consumes the score.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from atlas.core.scoring import classify_tier
from atlas.schemas.framework9 import (
    DataSourceStatus,
    FlowDirection,
    Framework9Result,
    SignalTier,
)
from atlas.services.framework_score_service import (
    FrameworkScoreService,
    _compute_final_score,
    _compute_raw_total,
    _map_action,
)

# ---------------------------------------------------------------------------
# classify_tier — ATLAS v7.3.3 Section 13.3
# ---------------------------------------------------------------------------


class TestClassifyTier:
    """Boundary-exact tests for classify_tier() per v7.3.5 Section 13.3."""

    # ── T1 Elite (>= 85) ────────────────────────────────────────────────

    @pytest.mark.parametrize("score", [85, 90, 100])
    def test_t1_elite(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "T1_ELITE"
        assert result["action"] == "LEAPS ELIGIBLE"
        assert result["leaps_eligible"] is True
        assert result["adds_permitted"] is True

    def test_t1_elite_lower_boundary(self) -> None:
        """Score 85 is T1 Elite (not T1)."""
        assert classify_tier(85)["tier"] == "T1_ELITE"

    def test_t1_upper_boundary(self) -> None:
        """Score 84 is T1 (not T1 Elite)."""
        assert classify_tier(84)["tier"] == "T1"

    # ── T1 (80-84) ──────────────────────────────────────────────────────

    @pytest.mark.parametrize("score", [80, 82, 84])
    def test_t1(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "T1"
        assert result["leaps_eligible"] is False

    def test_t1_lower_boundary(self) -> None:
        """Score 80 is T1 (not T2)."""
        assert classify_tier(80)["tier"] == "T1"

    def test_t2_upper_boundary(self) -> None:
        """Score 79 is T2 (not T1)."""
        assert classify_tier(79)["tier"] == "T2"

    # ── T2 (70-79) ────────────────────────────────────────────────────

    @pytest.mark.parametrize("score", [70, 73, 79])
    def test_t2(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "T2"
        assert result["action"] == "GTC ADDS PERMITTED"

    def test_t2_lower_boundary(self) -> None:
        """Score 70 is T2 (not T3)."""
        assert classify_tier(70)["tier"] == "T2"

    def test_t3_upper_boundary(self) -> None:
        """Score 69 is T3 (not T2)."""
        assert classify_tier(69)["tier"] == "T3"

    # ── T3 (50-69) ────────────────────────────────────────────────────

    @pytest.mark.parametrize("score", [50, 62, 69])
    def test_t3(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "T3"
        assert result["action"] == "SMALL POSITION ONLY"
        assert result["leaps_eligible"] is False

    def test_t3_lower_boundary(self) -> None:
        """Score 50 is T3 (not Below Gate)."""
        assert classify_tier(50)["tier"] == "T3"

    def test_below_gate_upper_boundary(self) -> None:
        """Score 49 is Below Gate (not T3)."""
        assert classify_tier(49)["tier"] == "BELOW_GATE"

    # ── Below Gate (< 50) ────────────────────────────────────────────

    @pytest.mark.parametrize("score", [0, 30, 49])
    def test_below_gate(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "BELOW_GATE"
        assert result["action"] == "NO NEW CAPITAL"
        assert result["adds_permitted"] is False

    # ── Integer conversion (Rule 4) ───────────────────────────────────

    def test_float_69_9_is_t3(self) -> None:
        """int(69.9) = 69 → T3, NOT T2."""
        assert classify_tier(69.9)["tier"] == "T3"

    def test_float_69_0_is_t3(self) -> None:
        """int(69.0) = 69 → T3."""
        assert classify_tier(69.0)["tier"] == "T3"

    def test_float_70_0_is_t2(self) -> None:
        """int(70.0) = 70 → T2."""
        assert classify_tier(70.0)["tier"] == "T2"


# ---------------------------------------------------------------------------
# _map_action — thin wrapper over classify_tier
# ---------------------------------------------------------------------------


class TestMapAction:
    """_map_action → (action, tone) per v7.3.5 Section 13.3."""

    @pytest.mark.parametrize("score", [85, 90, 100])
    def test_leaps_eligible(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "LEAPS ELIGIBLE"
        assert tone == "tone-green"

    @pytest.mark.parametrize("score", [80, 82, 84])
    def test_t1_core_position(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "CORE POSITION"
        assert tone == "tone-teal"

    @pytest.mark.parametrize("score", [70, 73, 79])
    def test_gtc_adds(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "GTC ADDS PERMITTED"
        assert tone == "tone-blue"

    @pytest.mark.parametrize("score", [50, 62, 69])
    def test_small_position(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "SMALL POSITION ONLY"
        assert tone == "tone-yellow"

    @pytest.mark.parametrize("score", [0, 30, 49])
    def test_below_gate(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "NO NEW CAPITAL"
        assert tone == "tone-red"

    def test_score_69_is_small_position_not_gtc(self) -> None:
        """Regression: score 69 must NOT return GTC ADDS PERMITTED."""
        action, _ = _map_action(69)
        assert action == "SMALL POSITION ONLY"




# ---------------------------------------------------------------------------
# _compute_raw_total
# ---------------------------------------------------------------------------


class TestComputeRawTotal:
    """Verifies that factor weights are applied correctly.

    Weights per Factor_Mapping_Guide:
      F1 x 0.20  F2 x 0.25  F3 x 0.15  F4 x 0.15  F5 x 0.25  -> max = 100
    """

    def test_all_perfect_scores_give_100(self) -> None:
        assert _compute_raw_total(100, 100, 100, 100, 100) == pytest.approx(100.0)

    def test_all_zero_scores_give_0(self) -> None:
        assert _compute_raw_total(0, 0, 0, 0, 0) == pytest.approx(0.0)

    def test_only_f1_contributes(self) -> None:
        # 100 x 0.20 = 20.0
        assert _compute_raw_total(100, 0, 0, 0, 0) == pytest.approx(20.0)

    def test_only_f2_contributes(self) -> None:
        # 100 x 0.25 = 25.0
        assert _compute_raw_total(0, 100, 0, 0, 0) == pytest.approx(25.0)

    def test_only_f3_contributes(self) -> None:
        # 100 x 0.15 = 15.0
        assert _compute_raw_total(0, 0, 100, 0, 0) == pytest.approx(15.0)

    def test_only_f4_contributes(self) -> None:
        # 100 x 0.15 = 15.0
        assert _compute_raw_total(0, 0, 0, 100, 0) == pytest.approx(15.0)

    def test_only_f5_contributes(self) -> None:
        # 100 x 0.25 = 25.0
        assert _compute_raw_total(0, 0, 0, 0, 100) == pytest.approx(25.0)

    def test_lite_worked_example(self) -> None:
        """LITE example from Factor_Mapping_Guide (before regime modifier).

        F1=86, F2=94, F3=100, F4=82, F5=78 (using guide sample scores)
          86 x 0.20 = 17.20
          94 x 0.25 = 23.50
         100 x 0.15 = 15.00
          82 x 0.15 = 12.30
          78 x 0.25 = 19.50
          Total     = 87.50
        """
        result = _compute_raw_total(86, 94, 100, 82, 78)
        assert result == pytest.approx(87.50, abs=0.01)


# ---------------------------------------------------------------------------
# _compute_final_score
# ---------------------------------------------------------------------------


class TestComputeFinalScore:
    """raw_total → clamped int [0, 100]."""

    def test_typical_score(self) -> None:
        # 83.6 → rounds to 84
        assert _compute_final_score(83.60) == 84

    def test_clamp_at_100(self) -> None:
        assert _compute_final_score(100.0) == 100

    def test_clamp_at_0(self) -> None:
        assert _compute_final_score(0.0) == 0

    def test_max_possible_score_is_100(self) -> None:
        """Perfect score on all factors gives 100 (weights sum to 1.00)."""
        raw = _compute_raw_total(100, 100, 100, 100, 100)  # 100.0
        final = _compute_final_score(raw)  # 100
        assert final == 100

    def test_rounding(self) -> None:
        # 82.6 → rounds to 83
        assert _compute_final_score(82.6) == 83


# ---------------------------------------------------------------------------
# _fetch_f4 must delegate to evaluate_framework9
# ---------------------------------------------------------------------------


def _make_f9_result(ticker: str = "TEST", f4_score: float = 41.0) -> Framework9Result:
    """Return a minimal Framework9Result for mocking purposes."""
    return Framework9Result(
        ticker=ticker,
        f4_score=f4_score,
        f4_grade="NEUTRAL",
        f4_contribution=round(f4_score * 0.15, 2),
        signal_tier=SignalTier.TIER_4_WEAK,
        flow_direction=FlowDirection.NEUTRAL,
        put_call_modifier=0,
        dark_pool_modifier=0,
        pre_earnings_modifier=-13,
        index_modifier=0,
        signal_valid=False,
        minimum_threshold_met=False,
        uw_status=DataSourceStatus.ONLINE,
        polygon_status=DataSourceStatus.ONLINE,
        av_status=DataSourceStatus.ONLINE,
        data_gap_severity="NONE",
        warning_level="AMBER",
    )


class TestFetchF4UsesFramework9:
    """_fetch_f4 must delegate to evaluate_framework9, not raw OptionsFlowService.

    Framework 9 applies the pre-earnings modifier (e.g. −25%) on top of the
    raw F4 base score.  Framework 1 must consume the *adjusted* score so the
    final conviction score reflects the timing-risk adjustment.
    """

    @pytest.mark.asyncio
    async def test_fetch_f4_returns_framework9_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_fetch_f4 must return Framework9Result (pre-earnings modifier baked in)."""
        import atlas.services.framework_score_service as fss_module

        expected = _make_f9_result(ticker="TEST", f4_score=41.0)

        async def _mock_evaluate_framework9(
            ticker: str,
            uw_api_key: str,
            polygon_api_key: str,
            av_api_key: str,
            **kwargs: object,
        ) -> Framework9Result:
            return expected

        monkeypatch.setattr(fss_module, "evaluate_framework9", _mock_evaluate_framework9)

        svc = FrameworkScoreService(
            polygon_api_key="poly",
            alphavantage_api_key="av",
            transcript_api_key="fmp",
            benzinga_api_key="benz",
            unusual_whales_api_key="uw",
            sec_api_key="sec",
        )
        result = await svc._fetch_f4("TEST")

        assert isinstance(result, Framework9Result)
        assert result.f4_score == 41.0
        assert result.pre_earnings_modifier == -13

    @pytest.mark.asyncio
    async def test_fetch_f4_passes_api_keys_to_framework9(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_fetch_f4 must forward uw, polygon, and av keys to evaluate_framework9."""
        import atlas.services.framework_score_service as fss_module

        captured: dict[str, str] = {}

        async def _capturing_f9(
            ticker: str,
            uw_api_key: str,
            polygon_api_key: str,
            av_api_key: str,
            **kwargs: object,
        ) -> Framework9Result:
            captured["ticker"] = ticker
            captured["uw"] = uw_api_key
            captured["polygon"] = polygon_api_key
            captured["av"] = av_api_key
            return _make_f9_result(ticker=ticker)

        monkeypatch.setattr(fss_module, "evaluate_framework9", _capturing_f9)

        svc = FrameworkScoreService(
            polygon_api_key="POLY_KEY",
            alphavantage_api_key="AV_KEY",
            transcript_api_key="FMP_KEY",
            benzinga_api_key="BENZ_KEY",
            unusual_whales_api_key="UW_KEY",
            sec_api_key="SEC_KEY",
        )
        await svc._fetch_f4("AAPL")

        assert captured["ticker"] == "AAPL"
        assert captured["uw"] == "UW_KEY"
        assert captured["polygon"] == "POLY_KEY"
        assert captured["av"] == "AV_KEY"
