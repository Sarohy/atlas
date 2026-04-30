"""Unit tests for Framework 3 — Score Action Map v7.3.4.

Score bands:
  >= 85       TIER_1         — Core position, LEAPS eligible
  78 – 84     TIER_2_GREY    — Grey zone, 3-model consensus required
  70 – 77     TIER_2         — GTC adds permitted
  55 – 69     TIER_3         — Small position only
  < 55        WATCHLIST      — Exit rules active (see Framework 16)
"""

from __future__ import annotations

from atlas.services.position_sizing_service import (
    ScoreAction,
    _set_consensus,
    compute_position_sizing,
    score_to_action,
)


# ---------------------------------------------------------------------------
# score_to_action — pure (score, cap) → ScoreAction
# ---------------------------------------------------------------------------


class TestScoreToAction:
    # --- TIER 1 (>= 85) ---

    def test_score_87_is_tier_1(self) -> None:
        result = score_to_action(87.0)
        assert result.tier == "TIER_1"
        assert result.action == "CORE — LEAPS ELIGIBLE"
        assert result.leaps_eligible is True
        assert result.adds_permitted is True
        assert result.grey_zone is False
        assert result.trigger_exit_rules is False

    def test_score_100_is_tier_1(self) -> None:
        result = score_to_action(100.0)
        assert result.tier == "TIER_1"

    def test_score_85_boundary_is_tier_1(self) -> None:
        result = score_to_action(85.0)
        assert result.tier == "TIER_1"

    def test_score_84_boundary_is_not_tier_1(self) -> None:
        result = score_to_action(84.0)
        assert result.tier != "TIER_1"

    # --- TIER 2 GREY (78-84) ---

    def test_score_81_is_tier_2_grey(self) -> None:
        result = score_to_action(81.0)
        assert result.tier == "TIER_2_GREY"
        assert result.grey_zone is True
        assert result.consensus_required is True
        assert result.adds_permitted is False
        assert result.leaps_eligible is False
        assert result.trigger_exit_rules is False

    def test_score_84_boundary_is_tier_2_grey(self) -> None:
        result = score_to_action(84.0)
        assert result.tier == "TIER_2_GREY"

    def test_score_78_boundary_is_tier_2_grey(self) -> None:
        result = score_to_action(78.0)
        assert result.tier == "TIER_2_GREY"

    def test_score_77_boundary_is_not_tier_2_grey(self) -> None:
        result = score_to_action(77.0)
        assert result.tier != "TIER_2_GREY"

    # --- TIER 2 (70-77) ---

    def test_score_73_is_tier_2(self) -> None:
        result = score_to_action(73.0)
        assert result.tier == "TIER_2"
        assert result.action == "GTC ADDS PERMITTED"
        assert result.adds_permitted is True
        assert result.grey_zone is False
        assert result.leaps_eligible is False
        assert result.consensus_required is False

    def test_score_77_boundary_is_tier_2(self) -> None:
        result = score_to_action(77.0)
        assert result.tier == "TIER_2"

    def test_score_70_boundary_is_tier_2(self) -> None:
        result = score_to_action(70.0)
        assert result.tier == "TIER_2"

    def test_score_69_boundary_is_not_tier_2(self) -> None:
        result = score_to_action(69.0)
        assert result.tier != "TIER_2"

    # --- TIER 3 (55-69) ---

    def test_score_62_is_tier_3(self) -> None:
        result = score_to_action(62.0)
        assert result.tier == "TIER_3"
        assert result.action == "SMALL POSITION ONLY"
        assert result.adds_permitted is False
        assert result.trigger_exit_rules is False
        assert result.grey_zone is False

    def test_score_69_boundary_is_tier_3(self) -> None:
        result = score_to_action(69.0)
        assert result.tier == "TIER_3"

    def test_score_55_boundary_is_tier_3(self) -> None:
        result = score_to_action(55.0)
        assert result.tier == "TIER_3"

    def test_score_54_boundary_is_not_tier_3(self) -> None:
        result = score_to_action(54.0)
        assert result.tier != "TIER_3"

    # --- WATCHLIST (< 55) ---

    def test_score_48_is_watchlist(self) -> None:
        result = score_to_action(48.0)
        assert result.tier == "WATCHLIST"
        assert result.trigger_exit_rules is True
        assert result.adds_permitted is False
        assert result.grey_zone is False

    def test_score_54_boundary_is_watchlist(self) -> None:
        result = score_to_action(54.0)
        assert result.tier == "WATCHLIST"

    def test_score_0_is_watchlist(self) -> None:
        result = score_to_action(0.0)
        assert result.tier == "WATCHLIST"

    # --- Watchlist display message includes Framework 16 reference ---

    def test_watchlist_display_message_references_framework_16(self) -> None:
        result = score_to_action(48.0)
        assert "Framework 16" in result.display_message

    # --- Concentration cap (Tier 1 only) ---

    def test_score_87_with_cap_blocks_adds(self) -> None:
        result = score_to_action(87.0, concentration_cap_active=True)
        assert result.tier == "TIER_1"
        assert result.adds_permitted is False
        assert "concentration cap" in result.display_message.lower()

    def test_score_85_with_cap_blocks_adds(self) -> None:
        result = score_to_action(85.0, concentration_cap_active=True)
        assert result.adds_permitted is False

    def test_cap_does_not_affect_tier_2(self) -> None:
        # Concentration cap only applies to Tier 1
        result = score_to_action(73.0, concentration_cap_active=True)
        assert result.adds_permitted is True

    def test_cap_does_not_affect_tier_3(self) -> None:
        result = score_to_action(62.0, concentration_cap_active=True)
        assert result.tier == "TIER_3"

    # --- ScoreAction is a dataclass (structural check) ---

    def test_score_action_has_required_fields(self) -> None:
        result = score_to_action(87.0)
        assert isinstance(result, ScoreAction)
        for field in (
            "tier",
            "action",
            "grey_zone",
            "consensus_required",
            "trigger_exit_rules",
            "adds_permitted",
            "leaps_eligible",
            "display_message",
        ):
            assert hasattr(result, field)


# ---------------------------------------------------------------------------
# compute_position_sizing — applies consensus gate on top of score_to_action
# ---------------------------------------------------------------------------


class TestComputePositionSizingConsensusGate:
    def test_grey_zone_without_consensus_blocks_adds(self) -> None:
        _set_consensus("CGTESTOFF", False)
        result = compute_position_sizing("CGTESTOFF", 81)
        assert result.consensus_confirmed is False
        assert result.adds_permitted is False

    def test_grey_zone_with_consensus_allows_adds(self) -> None:
        _set_consensus("CGTESTON", True)
        result = compute_position_sizing("CGTESTON", 81)
        assert result.consensus_confirmed is True
        assert result.adds_permitted is True

    def test_consensus_does_not_affect_tier_1(self) -> None:
        # Tier 1 never needs consensus — adds should stay True
        _set_consensus("TIER1CONS", True)
        result = compute_position_sizing("TIER1CONS", 87)
        assert result.tier == "TIER_1"
        assert result.adds_permitted is True

    def test_consensus_confirmed_false_by_default(self) -> None:
        # Unknown ticker key → consensus defaults to False
        result = compute_position_sizing("UNKNOWN_TICKER_XYZ", 81)
        assert result.consensus_confirmed is False


class TestComputePositionSizingGeneral:
    def test_ticker_normalised_to_uppercase(self) -> None:
        result = compute_position_sizing("aapl", 87)
        assert result.ticker == "AAPL"

    def test_tier_1_full_response(self) -> None:
        result = compute_position_sizing("NBIS", 87)
        assert result.tier == "TIER_1"
        assert result.leaps_eligible is True
        assert result.adds_permitted is True
        assert result.grey_zone is False
        assert result.trigger_exit_rules is False

    def test_watchlist_triggers_exit_rules(self) -> None:
        result = compute_position_sizing("POOR", 48)
        assert result.tier == "WATCHLIST"
        assert result.trigger_exit_rules is True
        assert "Framework 16" in result.display_message

    def test_concentration_cap_blocks_tier_1_adds(self) -> None:
        result = compute_position_sizing("CAPPED", 87, concentration_cap_active=True)
        assert result.tier == "TIER_1"
        assert result.adds_permitted is False

    def test_score_clamped_above_100(self) -> None:
        result = compute_position_sizing("AAPL", 150)
        assert result.conviction_score == 100
        assert result.tier == "TIER_1"

    def test_score_clamped_below_0(self) -> None:
        result = compute_position_sizing("AAPL", -10)
        assert result.conviction_score == 0
        assert result.tier == "WATCHLIST"
