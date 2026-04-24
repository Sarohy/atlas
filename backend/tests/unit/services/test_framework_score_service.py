"""Unit tests for FrameworkScoreService pure helpers and classify_tier SSOT.

TDD — covers deterministic pure functions (no I/O).

Pure functions under test:
  classify_tier      — score → TierResult (ATLAS v7.3.3 Section 13.3 SSOT)
  _map_action        — final_score → (action, action_tone) via classify_tier
  _compute_raw_total — (f1,f2,f3,f4,f5) → weighted sum (max 100)
  _compute_final_score — raw_total → clamped int [0,100]
"""

from __future__ import annotations

import pytest

from atlas.core.scoring import classify_tier
from atlas.services.framework_score_service import (
    _compute_final_score,
    _compute_raw_total,
    _map_action,
)

# ---------------------------------------------------------------------------
# classify_tier — ATLAS v7.3.3 Section 13.3
# ---------------------------------------------------------------------------


class TestClassifyTier:
    """Boundary-exact tests for classify_tier() per v7.3.3 Section 13.3."""

    # ── Tier 1 Core (>= 85) ────────────────────────────────────────────────

    @pytest.mark.parametrize("score", [85, 90, 100])
    def test_tier1_core(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "TIER_1_CORE"
        assert result["action"] == "LEAPS ELIGIBLE"
        assert result["leaps_eligible"] is True
        assert result["adds_permitted"] is True

    def test_tier1_lower_boundary(self) -> None:
        """Score 85 is Tier 1 Core (not Grey Zone)."""
        assert classify_tier(85)["tier"] == "TIER_1_CORE"

    def test_grey_zone_upper_boundary(self) -> None:
        """Score 84 is Grey Zone (not Tier 1 Core)."""
        assert classify_tier(84)["tier"] == "GREY_ZONE"

    # ── Grey Zone (78-84) ──────────────────────────────────────────────────

    @pytest.mark.parametrize("score", [78, 80, 84])
    def test_grey_zone(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "GREY_ZONE"
        assert result["action"] == "3-AI CONSENSUS REQUIRED"
        assert result["leaps_eligible"] is False

    def test_grey_zone_lower_boundary(self) -> None:
        """Score 78 is Grey Zone (not Tier 2)."""
        assert classify_tier(78)["tier"] == "GREY_ZONE"

    def test_tier2_upper_boundary(self) -> None:
        """Score 77 is Tier 2 GTC ADDS (not Grey Zone)."""
        assert classify_tier(77)["tier"] == "TIER_2"

    # ── Tier 2 GTC ADDS (70-77) ───────────────────────────────────────────

    @pytest.mark.parametrize("score", [70, 73, 77])
    def test_tier2(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "TIER_2"
        assert result["action"] == "GTC ADDS PERMITTED"

    def test_tier2_lower_boundary(self) -> None:
        """Score 70 is Tier 2 (not Tier 3). This is the boundary fixed in v7.3.3."""
        assert classify_tier(70)["tier"] == "TIER_2"

    def test_tier3_upper_boundary(self) -> None:
        """Score 69 is Tier 3 SMALL POSITION (not Tier 2). THE BUG FIX."""
        assert classify_tier(69)["tier"] == "TIER_3"

    # ── Tier 3 Small Position (55-69) ─────────────────────────────────────

    @pytest.mark.parametrize("score", [55, 62, 69])
    def test_tier3(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "TIER_3"
        assert result["action"] == "SMALL POSITION ONLY"
        assert result["leaps_eligible"] is False

    def test_tier3_lower_boundary(self) -> None:
        """Score 55 is Tier 3 (not Watchlist)."""
        assert classify_tier(55)["tier"] == "TIER_3"

    def test_watchlist_upper_boundary(self) -> None:
        """Score 54 is Watchlist (not Tier 3)."""
        assert classify_tier(54)["tier"] == "WATCHLIST"

    # ── Watchlist (< 55) ──────────────────────────────────────────────────

    @pytest.mark.parametrize("score", [0, 30, 54])
    def test_watchlist(self, score: int) -> None:
        result = classify_tier(score)
        assert result["tier"] == "WATCHLIST"
        assert result["action"] == "NO NEW CAPITAL"
        assert result["adds_permitted"] is False

    # ── Integer conversion (Rule 4) ───────────────────────────────────────

    def test_float_69_9_is_tier3(self) -> None:
        """int(69.9) = 69 → Tier 3, NOT Tier 2."""
        assert classify_tier(69.9)["tier"] == "TIER_3"

    def test_float_69_0_is_tier3(self) -> None:
        """int(69.0) = 69 → Tier 3."""
        assert classify_tier(69.0)["tier"] == "TIER_3"

    def test_float_70_0_is_tier2(self) -> None:
        """int(70.0) = 70 → Tier 2."""
        assert classify_tier(70.0)["tier"] == "TIER_2"


# ---------------------------------------------------------------------------
# _map_action — thin wrapper over classify_tier
# ---------------------------------------------------------------------------


class TestMapAction:
    """_map_action → (action, tone) per v7.3.3 Section 13.3."""

    @pytest.mark.parametrize("score", [85, 90, 100])
    def test_leaps_eligible(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "LEAPS ELIGIBLE"
        assert tone == "tone-green"

    @pytest.mark.parametrize("score", [78, 80, 84])
    def test_grey_zone(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "3-AI CONSENSUS REQUIRED"
        assert tone == "tone-purple"

    @pytest.mark.parametrize("score", [70, 73, 77])
    def test_gtc_adds(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "GTC ADDS PERMITTED"
        assert tone == "tone-blue"

    @pytest.mark.parametrize("score", [55, 62, 69])
    def test_small_position(self, score: int) -> None:
        action, tone = _map_action(score)
        assert action == "SMALL POSITION ONLY"
        assert tone == "tone-yellow"

    @pytest.mark.parametrize("score", [0, 30, 54])
    def test_watchlist(self, score: int) -> None:
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
      F1 x 0.15  F2 x 0.25  F3 x 0.15  F4 x 0.15  F5 x 0.30  -> max = 100
    """

    def test_all_perfect_scores_give_100(self) -> None:
        assert _compute_raw_total(100, 100, 100, 100, 100) == pytest.approx(100.0)

    def test_all_zero_scores_give_0(self) -> None:
        assert _compute_raw_total(0, 0, 0, 0, 0) == pytest.approx(0.0)

    def test_only_f1_contributes(self) -> None:
        # 100 x 0.15 = 15.0
        assert _compute_raw_total(100, 0, 0, 0, 0) == pytest.approx(15.0)

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
        # 100 x 0.30 = 30.0
        assert _compute_raw_total(0, 0, 0, 0, 100) == pytest.approx(30.0)

    def test_lite_worked_example(self) -> None:
        """LITE example from Factor_Mapping_Guide (before regime modifier).

        F1=86, F2=94, F3=100, F4=82, F5=78 (using guide sample scores)
          86 x 0.15 = 12.90
          94 x 0.25 = 23.50
         100 x 0.15 = 15.00
          82 x 0.15 = 12.30
          78 x 0.30 = 23.40
          Total     = 87.10
        """
        result = _compute_raw_total(86, 94, 100, 82, 78)
        assert result == pytest.approx(87.10, abs=0.01)


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
