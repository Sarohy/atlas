"""Unit tests for the Framework 6 (v8) conviction-action service pure helpers.

New tier structure (no GREY_ZONE):
  >= 85   T1_ELITE    — Highest-conviction. Full allocation, LEAPs eligible. 5-10%+ NAV
  80-84   T1          — Strong direct beneficiaries. Core / meaningful satellite. 2-4%
  70-79   T2          — Secondary / complementary. Small satellite. 0.5-1.5%
  50-69   T3          — Indirect / lower-quality. Rare, ≤ 0.5%
   < 50   BELOW_GATE  — Avoid entirely. 0%

Exit threshold dropped from 55 → 50.
GREY_ZONE and 3-AI consensus removed entirely.
"""

from __future__ import annotations

import pytest

from atlas.schemas.conviction_action import ConsensusStatus, PositionSizeStatus, Tier
from atlas.services.conviction_action_service import (
    _compute_adds_permitted,
    _compute_size_status,
    _score_band,
    assign_tier,
    get_exit_cycle_count,
    get_tier_details,
    reset_exit_cycle,
    update_exit_cycle,
)

# ---------------------------------------------------------------------------
# assign_tier — boundary conditions
# ---------------------------------------------------------------------------


class TestAssignTier:
    # ── T1 Elite (≥ 85) ────────────────────────────────────────────────────
    def test_score_85_is_t1_elite(self) -> None:
        assert assign_tier(85) == Tier.T1_ELITE

    def test_score_100_is_t1_elite(self) -> None:
        assert assign_tier(100) == Tier.T1_ELITE

    def test_score_91_is_t1_elite(self) -> None:
        assert assign_tier(91) == Tier.T1_ELITE

    # ── T1 (80-84) ─────────────────────────────────────────────────────────
    def test_score_84_is_t1_not_elite(self) -> None:
        assert assign_tier(84) == Tier.T1

    def test_score_80_is_t1(self) -> None:
        assert assign_tier(80) == Tier.T1

    def test_score_83_is_t1(self) -> None:
        assert assign_tier(83) == Tier.T1

    # Boundary: 79 must NOT be T1
    def test_score_79_is_t2_not_t1(self) -> None:
        assert assign_tier(79) == Tier.T2

    # ── T2 (70-79) ─────────────────────────────────────────────────────────
    def test_score_79_is_t2(self) -> None:
        assert assign_tier(79) == Tier.T2

    def test_score_70_is_t2(self) -> None:
        assert assign_tier(70) == Tier.T2

    # Boundary: 69 must NOT be T2
    def test_score_69_is_t3_not_t2(self) -> None:
        assert assign_tier(69) == Tier.T3

    # ── T3 (50-69) ─────────────────────────────────────────────────────────
    def test_score_69_is_t3(self) -> None:
        assert assign_tier(69) == Tier.T3

    def test_score_66_is_t3(self) -> None:
        assert assign_tier(66) == Tier.T3

    def test_score_50_is_t3(self) -> None:
        assert assign_tier(50) == Tier.T3

    # Boundary: 49 must NOT be T3
    def test_score_49_is_below_gate_not_t3(self) -> None:
        assert assign_tier(49) == Tier.BELOW_GATE

    # ── Below Gate (< 50) ──────────────────────────────────────────────────
    def test_score_48_is_below_gate(self) -> None:
        assert assign_tier(48) == Tier.BELOW_GATE

    def test_score_0_is_below_gate(self) -> None:
        assert assign_tier(0) == Tier.BELOW_GATE

    # ── GREY_ZONE must no longer exist ─────────────────────────────────────
    def test_no_grey_zone_tier_at_78(self) -> None:
        # 78 used to be GREY_ZONE; now it must be T2
        assert assign_tier(78) == Tier.T2

    def test_no_grey_zone_tier_at_82(self) -> None:
        # 82 used to be GREY_ZONE; now it must be T1
        assert assign_tier(82) == Tier.T1

    # ── Old exit threshold (55) is gone — 54 is now T3 ─────────────────────
    def test_score_55_is_t3_not_below_gate(self) -> None:
        assert assign_tier(55) == Tier.T3

    def test_score_54_is_t3(self) -> None:
        assert assign_tier(54) == Tier.T3


# ---------------------------------------------------------------------------
# get_tier_details — labels, sizes, flags
# ---------------------------------------------------------------------------


class TestGetTierDetails:
    # ── T1 Elite ───────────────────────────────────────────────────────────
    def test_t1_elite_label(self) -> None:
        assert get_tier_details(Tier.T1_ELITE)["label"] == "T1 ELITE"

    def test_t1_elite_leaps_eligible(self) -> None:
        assert get_tier_details(Tier.T1_ELITE)["leaps"] is True

    def test_t1_elite_no_consensus_required(self) -> None:
        assert get_tier_details(Tier.T1_ELITE)["consensus"] is False

    def test_t1_elite_size_range(self) -> None:
        d = get_tier_details(Tier.T1_ELITE)
        assert d["size_min"] == pytest.approx(0.05)
        assert d["size_max"] == pytest.approx(0.10)

    # ── T1 ─────────────────────────────────────────────────────────────────
    def test_t1_label(self) -> None:
        assert get_tier_details(Tier.T1)["label"] == "T1"

    def test_t1_no_leaps(self) -> None:
        assert get_tier_details(Tier.T1)["leaps"] is False

    def test_t1_no_consensus(self) -> None:
        assert get_tier_details(Tier.T1)["consensus"] is False

    def test_t1_size_range(self) -> None:
        d = get_tier_details(Tier.T1)
        assert d["size_min"] == pytest.approx(0.02)
        assert d["size_max"] == pytest.approx(0.04)

    # ── T2 ─────────────────────────────────────────────────────────────────
    def test_t2_label(self) -> None:
        assert get_tier_details(Tier.T2)["label"] == "T2"

    def test_t2_action(self) -> None:
        assert get_tier_details(Tier.T2)["action"] == "Small satellites only"

    def test_t2_size_range(self) -> None:
        d = get_tier_details(Tier.T2)
        assert d["size_min"] == pytest.approx(0.005)
        assert d["size_max"] == pytest.approx(0.015)

    # ── T3 ─────────────────────────────────────────────────────────────────
    def test_t3_size_range(self) -> None:
        d = get_tier_details(Tier.T3)
        assert d["size_min"] == pytest.approx(0.0)
        assert d["size_max"] == pytest.approx(0.005)

    # ── Below Gate ─────────────────────────────────────────────────────────
    def test_below_gate_zero_size(self) -> None:
        d = get_tier_details(Tier.BELOW_GATE)
        assert d["size_min"] == 0.0
        assert d["size_max"] == 0.0

    def test_below_gate_label(self) -> None:
        assert get_tier_details(Tier.BELOW_GATE)["label"] == "BELOW GATE"

    # ── GREY_ZONE must not appear in details ───────────────────────────────
    def test_grey_zone_not_in_tier_enum(self) -> None:
        with pytest.raises(Exception):
            Tier("GREY_ZONE")


# ---------------------------------------------------------------------------
# _compute_size_status
# ---------------------------------------------------------------------------


class TestComputeSizeStatus:
    def test_below_gate_no_position_status(self) -> None:
        status, room, trim = _compute_size_status(Tier.BELOW_GATE, 0.0, 0.0, 0.0)
        assert status == PositionSizeStatus.NO_POSITION
        assert room == pytest.approx(0.0)
        assert trim is False

    def test_below_gate_trim_suggested_when_holding(self) -> None:
        _, _, trim = _compute_size_status(Tier.BELOW_GATE, 0.002, 0.0, 0.0)
        assert trim is True

    def test_underweight(self) -> None:
        status, room, trim = _compute_size_status(Tier.T2, 0.003, 0.005, 0.015)
        assert status == PositionSizeStatus.UNDERWEIGHT
        assert room == pytest.approx(0.012)
        assert trim is False

    def test_in_range(self) -> None:
        status, room, trim = _compute_size_status(Tier.T2, 0.010, 0.005, 0.015)
        assert status == PositionSizeStatus.IN_RANGE
        assert room == pytest.approx(0.005)
        assert trim is False

    def test_overweight(self) -> None:
        status, room, trim = _compute_size_status(Tier.T2, 0.020, 0.005, 0.015)
        assert status == PositionSizeStatus.OVERWEIGHT
        assert room == pytest.approx(0.0)
        assert trim is True

    def test_t3_at_max(self) -> None:
        # T3 max is 0.005; holding exactly at max → IN_RANGE, room=0
        status, room, trim = _compute_size_status(Tier.T3, 0.005, 0.0, 0.005)
        assert status == PositionSizeStatus.IN_RANGE
        assert room == pytest.approx(0.0)
        assert trim is False


# ---------------------------------------------------------------------------
# _compute_adds_permitted — no consensus branch
# ---------------------------------------------------------------------------


class TestComputeAddsPermitted:
    def test_below_gate_blocked(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.BELOW_GATE, False, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is False
        assert reason is not None

    def test_beta_cap_blocks_t1_elite(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.T1_ELITE, True, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is False
        assert "Beta cap" in (reason or "")

    def test_concentration_cap_blocks_t1(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.T1, False, True, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is False
        assert "Concentration cap" in (reason or "")

    def test_t1_elite_no_caps_permitted(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.T1_ELITE, False, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is True
        assert reason is None

    def test_t1_no_caps_permitted(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.T1, False, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is True
        assert reason is None

    def test_t2_no_caps_permitted(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.T2, False, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is True
        assert reason is None

    def test_t3_no_caps_permitted(self) -> None:
        # T3 allows small satellite sizing — no cap means permitted
        permitted, _ = _compute_adds_permitted(
            Tier.T3, False, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is True

    def test_beta_cap_priority_over_concentration(self) -> None:
        _, reason = _compute_adds_permitted(Tier.T2, True, True, ConsensusStatus.NOT_REQUIRED)
        assert "Beta cap" in (reason or "")


# ---------------------------------------------------------------------------
# _score_band — new boundaries
# ---------------------------------------------------------------------------


class TestScoreBand:
    def test_t1_elite_band(self) -> None:
        lo, hi = _score_band(Tier.T1_ELITE)
        assert lo == 85
        assert hi is None

    def test_t1_band(self) -> None:
        lo, hi = _score_band(Tier.T1)
        assert lo == 80
        assert hi == 84

    def test_t2_band(self) -> None:
        lo, hi = _score_band(Tier.T2)
        assert lo == 70
        assert hi == 79

    def test_t3_band(self) -> None:
        lo, hi = _score_band(Tier.T3)
        assert lo == 50
        assert hi == 69

    def test_below_gate_band(self) -> None:
        lo, hi = _score_band(Tier.BELOW_GATE)
        assert lo == 0
        assert hi == 49


# ---------------------------------------------------------------------------
# Exit cycle — threshold now 50 (not 55)
# ---------------------------------------------------------------------------


class TestExitCycle:
    def setup_method(self) -> None:
        reset_exit_cycle("NEM")

    def test_initial_count_is_zero(self) -> None:
        assert get_exit_cycle_count("NEM") == 0

    def test_count_increments_on_sub50_score(self) -> None:
        count = update_exit_cycle("NEM", 49.0)
        assert count == 1

    def test_count_reaches_two(self) -> None:
        update_exit_cycle("NEM", 49.0)
        count = update_exit_cycle("NEM", 45.0)
        assert count == 2

    def test_score_50_does_not_increment(self) -> None:
        # 50 is T3 now — should NOT trigger exit counter
        count = update_exit_cycle("NEM", 50.0)
        assert count == 0

    def test_score_55_does_not_increment(self) -> None:
        # 55 used to trigger exit; now it's T3 — no exit
        count = update_exit_cycle("NEM", 55.0)
        assert count == 0

    def test_count_resets_on_score_at_threshold(self) -> None:
        update_exit_cycle("NEM", 49.0)
        count = update_exit_cycle("NEM", 50.0)
        assert count == 0

    def test_reset_function_clears_count(self) -> None:
        update_exit_cycle("NEM", 49.0)
        reset_exit_cycle("NEM")
        assert get_exit_cycle_count("NEM") == 0

    def test_ticker_uppercase_normalised(self) -> None:
        update_exit_cycle("nem", 49.0)
        assert get_exit_cycle_count("NEM") == 1


