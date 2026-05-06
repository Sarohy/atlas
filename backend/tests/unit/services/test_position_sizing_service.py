"""Unit tests for Framework 3 — Score Action Map v7.3.5.

Score bands:
  >= 85       T1_ELITE    — Core position, LEAPS eligible, 5-10% NAV
  80-84       T1          — Core position, 2-4% NAV
  70-79       T2          — GTC adds permitted, 0.5-1.5% NAV
  50-69       T3          — Small speculative position, 0-0.5% NAV
  < 50        BELOW_GATE  — Exit rules active (see Framework 16)
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
    # --- T1 Elite (>= 85) ---

    def test_score_87_is_t1_elite(self) -> None:
        result = score_to_action(87.0)
        assert result.tier == "T1_ELITE"
        assert result.action == "CORE — LEAPS ELIGIBLE"
        assert result.leaps_eligible is True
        assert result.adds_permitted is True
        assert result.grey_zone is False
        assert result.trigger_exit_rules is False

    def test_score_100_is_t1_elite(self) -> None:
        result = score_to_action(100.0)
        assert result.tier == "T1_ELITE"

    def test_score_85_boundary_is_t1_elite(self) -> None:
        result = score_to_action(85.0)
        assert result.tier == "T1_ELITE"

    def test_score_84_boundary_is_t1(self) -> None:
        result = score_to_action(84.0)
        assert result.tier == "T1"

    # --- T1 (80-84) ---

    def test_score_81_is_t1(self) -> None:
        result = score_to_action(81.0)
        assert result.tier == "T1"
        assert result.grey_zone is False
        assert result.consensus_required is False
        assert result.adds_permitted is True
        assert result.leaps_eligible is False
        assert result.trigger_exit_rules is False

    def test_score_84_boundary_is_t1(self) -> None:
        result = score_to_action(84.0)
        assert result.tier == "T1"

    def test_score_80_boundary_is_t1(self) -> None:
        result = score_to_action(80.0)
        assert result.tier == "T1"

    def test_score_79_boundary_is_t2(self) -> None:
        result = score_to_action(79.0)
        assert result.tier == "T2"

    # --- T2 (70-79) ---

    def test_score_73_is_t2(self) -> None:
        result = score_to_action(73.0)
        assert result.tier == "T2"
        assert result.action == "GTC ADDS PERMITTED"
        assert result.adds_permitted is True
        assert result.grey_zone is False
        assert result.leaps_eligible is False
        assert result.consensus_required is False

    def test_score_79_boundary_is_t2(self) -> None:
        result = score_to_action(79.0)
        assert result.tier == "T2"

    def test_score_70_boundary_is_t2(self) -> None:
        result = score_to_action(70.0)
        assert result.tier == "T2"

    def test_score_69_boundary_is_not_t2(self) -> None:
        result = score_to_action(69.0)
        assert result.tier != "T2"

    # --- T3 (50-69) ---

    def test_score_62_is_t3(self) -> None:
        result = score_to_action(62.0)
        assert result.tier == "T3"
        assert result.action == "SMALL POSITION ONLY"
        assert result.adds_permitted is False
        assert result.trigger_exit_rules is False
        assert result.grey_zone is False

    def test_score_69_boundary_is_t3(self) -> None:
        result = score_to_action(69.0)
        assert result.tier == "T3"

    def test_score_50_boundary_is_t3(self) -> None:
        result = score_to_action(50.0)
        assert result.tier == "T3"

    def test_score_49_boundary_is_not_t3(self) -> None:
        result = score_to_action(49.0)
        assert result.tier != "T3"

    # --- Below Gate (< 50) ---

    def test_score_48_is_below_gate(self) -> None:
        result = score_to_action(48.0)
        assert result.tier == "BELOW_GATE"
        assert result.trigger_exit_rules is True
        assert result.adds_permitted is False
        assert result.grey_zone is False

    def test_score_49_boundary_is_below_gate(self) -> None:
        result = score_to_action(49.0)
        assert result.tier == "BELOW_GATE"

    def test_score_0_is_below_gate(self) -> None:
        result = score_to_action(0.0)
        assert result.tier == "BELOW_GATE"

    # --- Below Gate display message includes Framework 16 reference ---

    def test_below_gate_display_message_references_framework_16(self) -> None:
        result = score_to_action(48.0)
        assert "Framework 16" in result.display_message

    # --- Concentration cap (T1 Elite only) ---

    def test_score_87_with_cap_blocks_adds(self) -> None:
        result = score_to_action(87.0, concentration_cap_active=True)
        assert result.tier == "T1_ELITE"
        assert result.adds_permitted is False
        assert "concentration cap" in result.display_message.lower()

    def test_score_85_with_cap_blocks_adds(self) -> None:
        result = score_to_action(85.0, concentration_cap_active=True)
        assert result.adds_permitted is False

    def test_cap_does_not_affect_t2(self) -> None:
        result = score_to_action(73.0, concentration_cap_active=True)
        assert result.adds_permitted is True

    def test_cap_does_not_affect_t3(self) -> None:
        result = score_to_action(62.0, concentration_cap_active=True)
        assert result.tier == "T3"

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
# compute_position_sizing
# ---------------------------------------------------------------------------


class TestComputePositionSizingConsensusGate:
    def test_t1_adds_permitted(self) -> None:
        result = compute_position_sizing("NBIS", 81)
        assert result.consensus_confirmed is False
        assert result.adds_permitted is True

    def test_below_gate_blocks_adds(self) -> None:
        result = compute_position_sizing("POOR", 48)
        assert result.adds_permitted is False

    def test_consensus_confirmed_always_false(self) -> None:
        result = compute_position_sizing("UNKNOWN_TICKER_XYZ", 81)
        assert result.consensus_confirmed is False


class TestComputePositionSizingGeneral:
    def test_ticker_normalised_to_uppercase(self) -> None:
        result = compute_position_sizing("aapl", 87)
        assert result.ticker == "AAPL"

    def test_t1_elite_full_response(self) -> None:
        result = compute_position_sizing("NBIS", 87)
        assert result.tier == "T1_ELITE"
        assert result.leaps_eligible is True
        assert result.adds_permitted is True
        assert result.grey_zone is False
        assert result.trigger_exit_rules is False

    def test_below_gate_triggers_exit_rules(self) -> None:
        result = compute_position_sizing("POOR", 48)
        assert result.tier == "BELOW_GATE"
        assert result.trigger_exit_rules is True
        assert "Framework 16" in result.display_message

    def test_concentration_cap_blocks_t1_elite_adds(self) -> None:
        result = compute_position_sizing("CAPPED", 87, concentration_cap_active=True)
        assert result.tier == "T1_ELITE"
        assert result.adds_permitted is False

    def test_score_clamped_above_100(self) -> None:
        result = compute_position_sizing("AAPL", 150)
        assert result.conviction_score == 100
        assert result.tier == "T1_ELITE"

    def test_score_clamped_below_0(self) -> None:
        result = compute_position_sizing("AAPL", -10)
        assert result.conviction_score == 0
        assert result.tier == "BELOW_GATE"
