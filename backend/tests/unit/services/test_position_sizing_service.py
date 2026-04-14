"""Unit tests for Framework 3 — Position Sizing service.

Framework 3 maps a Framework 1 conviction score to a human-readable position
action and a descriptive instruction string.

Score-to-action map (Factor_Mapping_Guide §Framework3):
  > 90        MAXIMUM POSITION  — "Add on every dip"
  80 – 90     HOLD FULL         — "Eligible for adds"
  70 – 79     HOLD              — "No new adds"
  60 – 69     REDUCE 25–50%     — "Reduce 25-50%"
  55 – 59     REDUCE AGGRESSIVELY — "Reduce aggressively"
  < 55        EXIT              — "Exit immediately"
"""

from __future__ import annotations

import pytest

from atlas.services.position_sizing_service import (
    PositionSizingResponse,
    _map_position_action,
    compute_position_sizing,
)


# ---------------------------------------------------------------------------
# _map_position_action — pure score → (action, instruction) helper
# ---------------------------------------------------------------------------


class TestMapPositionAction:
    """Every band boundary and interior value must map to the correct action."""

    # > 90  →  MAXIMUM POSITION
    def test_score_91_is_maximum_position(self) -> None:
        action, instruction = _map_position_action(91)
        assert action == "MAXIMUM POSITION"
        assert "dip" in instruction.lower()

    def test_score_100_is_maximum_position(self) -> None:
        action, _ = _map_position_action(100)
        assert action == "MAXIMUM POSITION"

    def test_score_90_is_not_maximum_position(self) -> None:
        # Boundary: 90 is NOT > 90
        action, _ = _map_position_action(90)
        assert action != "MAXIMUM POSITION"

    # 80 – 90  →  HOLD FULL
    def test_score_90_is_hold_full(self) -> None:
        action, instruction = _map_position_action(90)
        assert action == "HOLD FULL"
        assert "add" in instruction.lower()

    def test_score_85_is_hold_full(self) -> None:
        action, _ = _map_position_action(85)
        assert action == "HOLD FULL"

    def test_score_80_is_hold_full(self) -> None:
        action, _ = _map_position_action(80)
        assert action == "HOLD FULL"

    def test_score_79_is_not_hold_full(self) -> None:
        action, _ = _map_position_action(79)
        assert action != "HOLD FULL"

    # 70 – 79  →  HOLD
    def test_score_79_is_hold(self) -> None:
        action, instruction = _map_position_action(79)
        assert action == "HOLD"
        assert "add" in instruction.lower()

    def test_score_75_is_hold(self) -> None:
        action, _ = _map_position_action(75)
        assert action == "HOLD"

    def test_score_70_is_hold(self) -> None:
        action, _ = _map_position_action(70)
        assert action == "HOLD"

    def test_score_69_is_not_hold(self) -> None:
        action, _ = _map_position_action(69)
        assert action != "HOLD"

    # 60 – 69  →  REDUCE 25-50%
    def test_score_69_is_reduce(self) -> None:
        action, instruction = _map_position_action(69)
        assert action == "REDUCE 25-50%"
        assert "25" in instruction or "50" in instruction

    def test_score_65_is_reduce(self) -> None:
        action, _ = _map_position_action(65)
        assert action == "REDUCE 25-50%"

    def test_score_60_is_reduce(self) -> None:
        action, _ = _map_position_action(60)
        assert action == "REDUCE 25-50%"

    def test_score_59_is_not_reduce(self) -> None:
        action, _ = _map_position_action(59)
        assert action != "REDUCE 25-50%"

    # 55 – 59  →  REDUCE AGGRESSIVELY
    def test_score_59_is_reduce_aggressively(self) -> None:
        action, instruction = _map_position_action(59)
        assert action == "REDUCE AGGRESSIVELY"
        assert "aggressiv" in instruction.lower()

    def test_score_57_is_reduce_aggressively(self) -> None:
        action, _ = _map_position_action(57)
        assert action == "REDUCE AGGRESSIVELY"

    def test_score_55_is_reduce_aggressively(self) -> None:
        action, _ = _map_position_action(55)
        assert action == "REDUCE AGGRESSIVELY"

    def test_score_54_is_not_reduce_aggressively(self) -> None:
        action, _ = _map_position_action(54)
        assert action != "REDUCE AGGRESSIVELY"

    # < 55  →  EXIT
    def test_score_54_is_exit(self) -> None:
        action, instruction = _map_position_action(54)
        assert action == "EXIT"
        assert "exit" in instruction.lower() or "immediat" in instruction.lower()

    def test_score_0_is_exit(self) -> None:
        action, _ = _map_position_action(0)
        assert action == "EXIT"

    def test_score_1_is_exit(self) -> None:
        action, _ = _map_position_action(1)
        assert action == "EXIT"


# ---------------------------------------------------------------------------
# compute_position_sizing — assembles the PositionSizingResponse
# ---------------------------------------------------------------------------


class TestComputePositionSizing:
    """compute_position_sizing must delegate to _map_position_action and
    populate all fields of PositionSizingResponse correctly."""

    def test_returns_position_sizing_response(self) -> None:
        result = compute_position_sizing(ticker="AAOI", conviction_score=85)
        assert isinstance(result, PositionSizingResponse)

    def test_ticker_is_uppercased(self) -> None:
        result = compute_position_sizing(ticker="aaoi", conviction_score=85)
        assert result.ticker == "AAOI"

    def test_conviction_score_is_preserved(self) -> None:
        result = compute_position_sizing(ticker="AAOI", conviction_score=72)
        assert result.conviction_score == 72

    def test_action_matches_score_band(self) -> None:
        assert compute_position_sizing("T", 95).action == "MAXIMUM POSITION"
        assert compute_position_sizing("T", 85).action == "HOLD FULL"
        assert compute_position_sizing("T", 75).action == "HOLD"
        assert compute_position_sizing("T", 65).action == "REDUCE 25-50%"
        assert compute_position_sizing("T", 57).action == "REDUCE AGGRESSIVELY"
        assert compute_position_sizing("T", 40).action == "EXIT"

    def test_instruction_is_non_empty_string(self) -> None:
        result = compute_position_sizing(ticker="AAOI", conviction_score=65)
        assert isinstance(result.instruction, str)
        assert len(result.instruction) > 0
