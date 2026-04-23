"""Unit tests for the Framework 6 (v7.3.4) conviction-action service pure helpers.

Tests cover assign_tier, get_tier_details, _compute_size_status,
_compute_adds_permitted, _score_band, update_exit_cycle, get_exit_cycle_count,
set_consensus_status, and get_consensus_status_for_tier.

All 13 spec test cases are covered by the classes below.
"""

from __future__ import annotations

import pytest

from atlas.schemas.conviction_action import ConsensusStatus, PositionSizeStatus, Tier
from atlas.services.conviction_action_service import (
    _compute_adds_permitted,
    _compute_size_status,
    _score_band,
    assign_tier,
    get_consensus_status_for_tier,
    get_exit_cycle_count,
    get_tier_details,
    reset_exit_cycle,
    set_consensus_status,
    update_exit_cycle,
)

# ---------------------------------------------------------------------------
# Spec test cases 7-10 - assign_tier boundary conditions
# ---------------------------------------------------------------------------


class TestAssignTier:
    """Tests 7-10 from spec: verify tier boundary conditions exactly."""

    # Test 9: score 85 → TIER_1_CORE (not GREY_ZONE)
    def test_score_85_is_tier1_core(self) -> None:
        assert assign_tier(85) == Tier.TIER_1_CORE

    # Test 9 inverse: score 84 → GREY_ZONE (not TIER_1_CORE)
    def test_score_84_is_grey_zone_not_tier1(self) -> None:
        assert assign_tier(84) == Tier.GREY_ZONE

    # Test 10: score 84 → GREY_ZONE
    def test_score_84_is_grey_zone(self) -> None:
        assert assign_tier(84) == Tier.GREY_ZONE

    # Test 8: score 78 → GREY_ZONE (not TIER_2)
    def test_score_78_is_grey_zone_not_tier2(self) -> None:
        assert assign_tier(78) == Tier.GREY_ZONE

    # Test 7: score 77 → TIER_2 (not GREY_ZONE)
    def test_score_77_is_tier2_not_grey_zone(self) -> None:
        assert assign_tier(77) == Tier.TIER_2

    def test_score_70_is_tier2(self) -> None:
        assert assign_tier(70) == Tier.TIER_2

    def test_score_69_is_tier3(self) -> None:
        assert assign_tier(69) == Tier.TIER_3

    def test_score_55_is_tier3(self) -> None:
        assert assign_tier(55) == Tier.TIER_3

    def test_score_54_is_watchlist(self) -> None:
        assert assign_tier(54) == Tier.WATCHLIST

    # Test 2: AVGO score 91 → TIER_1_CORE
    def test_score_91_is_tier1_core(self) -> None:
        assert assign_tier(91) == Tier.TIER_1_CORE

    # Tests 5 & 6: MRVL score 83 → GREY_ZONE
    def test_score_83_is_grey_zone(self) -> None:
        assert assign_tier(83) == Tier.GREY_ZONE

    # Test 3: TSEM score 66 → TIER_3
    def test_score_66_is_tier3(self) -> None:
        assert assign_tier(66) == Tier.TIER_3

    # Test 4: NEM score 48 → WATCHLIST
    def test_score_48_is_watchlist(self) -> None:
        assert assign_tier(48) == Tier.WATCHLIST

    def test_score_100_is_tier1(self) -> None:
        assert assign_tier(100) == Tier.TIER_1_CORE

    def test_score_0_is_watchlist(self) -> None:
        assert assign_tier(0) == Tier.WATCHLIST


# ---------------------------------------------------------------------------
# get_tier_details — labels, sizes, flags
# ---------------------------------------------------------------------------


class TestGetTierDetails:
    def test_tier1_core_label(self) -> None:
        d = get_tier_details(Tier.TIER_1_CORE)
        assert d["label"] == "TIER 1 — CORE"

    def test_tier1_core_leaps_eligible(self) -> None:
        d = get_tier_details(Tier.TIER_1_CORE)
        assert d["leaps"] is True

    def test_tier1_core_consensus_not_required(self) -> None:
        d = get_tier_details(Tier.TIER_1_CORE)
        assert d["consensus"] is False

    def test_tier1_core_size_range(self) -> None:
        d = get_tier_details(Tier.TIER_1_CORE)
        assert d["size_min"] == pytest.approx(0.030)
        assert d["size_max"] == pytest.approx(0.050)

    def test_tier1_core_color(self) -> None:
        assert get_tier_details(Tier.TIER_1_CORE)["color"] == "#39d353"

    def test_grey_zone_consensus_required(self) -> None:
        assert get_tier_details(Tier.GREY_ZONE)["consensus"] is True

    def test_grey_zone_no_leaps(self) -> None:
        assert get_tier_details(Tier.GREY_ZONE)["leaps"] is False

    def test_grey_zone_label(self) -> None:
        assert get_tier_details(Tier.GREY_ZONE)["label"] == "GREY ZONE"

    def test_grey_zone_color(self) -> None:
        assert get_tier_details(Tier.GREY_ZONE)["color"] == "#a371f7"

    def test_tier2_action(self) -> None:
        assert get_tier_details(Tier.TIER_2)["action"] == "GTC adds permitted"

    def test_tier2_size_range(self) -> None:
        d = get_tier_details(Tier.TIER_2)
        assert d["size_min"] == pytest.approx(0.005)
        assert d["size_max"] == pytest.approx(0.015)

    def test_tier3_size_range(self) -> None:
        d = get_tier_details(Tier.TIER_3)
        assert d["size_min"] == pytest.approx(0.0025)
        assert d["size_max"] == pytest.approx(0.005)

    def test_watchlist_zero_size(self) -> None:
        d = get_tier_details(Tier.WATCHLIST)
        assert d["size_min"] == 0.0
        assert d["size_max"] == 0.0

    def test_watchlist_label(self) -> None:
        assert get_tier_details(Tier.WATCHLIST)["label"] == "WATCHLIST"

    def test_watchlist_color(self) -> None:
        assert get_tier_details(Tier.WATCHLIST)["color"] == "#f85149"


# ---------------------------------------------------------------------------
# _compute_size_status — test cases 3 (TSEM) and OVERWEIGHT/UNDERWEIGHT
# ---------------------------------------------------------------------------


class TestComputeSizeStatus:
    def test_watchlist_no_position_status(self) -> None:
        status, room, trim = _compute_size_status(Tier.WATCHLIST, 0.0, 0.0, 0.0)
        assert status == PositionSizeStatus.NO_POSITION
        assert room == pytest.approx(0.0)
        assert trim is False

    def test_watchlist_trim_suggested_when_holding(self) -> None:
        _, _, trim = _compute_size_status(Tier.WATCHLIST, 0.002, 0.0, 0.0)
        assert trim is True

    def test_underweight(self) -> None:
        status, room, trim = _compute_size_status(Tier.TIER_2, 0.003, 0.005, 0.015)
        assert status == PositionSizeStatus.UNDERWEIGHT
        assert room == pytest.approx(0.012)
        assert trim is False

    def test_in_range(self) -> None:
        status, room, trim = _compute_size_status(Tier.TIER_2, 0.010, 0.005, 0.015)
        assert status == PositionSizeStatus.IN_RANGE
        assert room == pytest.approx(0.005)
        assert trim is False

    # Test 3: TSEM score=66, weight=0.005, tier_max=0.005 → IN_RANGE, room=0%
    def test_tsem_at_max_of_tier3(self) -> None:
        status, room, trim = _compute_size_status(Tier.TIER_3, 0.005, 0.0025, 0.005)
        assert status == PositionSizeStatus.IN_RANGE
        assert room == pytest.approx(0.0)
        assert trim is False

    def test_overweight(self) -> None:
        status, room, trim = _compute_size_status(Tier.TIER_2, 0.020, 0.005, 0.015)
        assert status == PositionSizeStatus.OVERWEIGHT
        assert room == pytest.approx(0.0)
        assert trim is True

    def test_in_range_at_min(self) -> None:
        status, _, _ = _compute_size_status(Tier.TIER_3, 0.0025, 0.0025, 0.005)
        assert status == PositionSizeStatus.IN_RANGE


# ---------------------------------------------------------------------------
# _compute_adds_permitted — test cases 1, 2, 5, 6
# ---------------------------------------------------------------------------


class TestComputeAddsPermitted:
    # Test 4 / WATCHLIST: blocked regardless of caps
    def test_watchlist_blocked(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.WATCHLIST, False, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is False
        assert reason == "Watchlist — no capital permitted"

    # Test 1: beta_cap wins over consensus (checked before consensus)
    def test_beta_cap_blocks_adds(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.GREY_ZONE, True, False, ConsensusStatus.PENDING
        )
        assert permitted is False
        assert reason == "Beta cap (F13) blocking adds"

    def test_concentration_cap_blocks_adds(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.TIER_2, False, True, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is False
        assert reason == "Concentration cap (F14) blocking adds"

    # Test 6: grey zone + PENDING consensus → blocked
    def test_grey_zone_pending_blocks(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.GREY_ZONE, False, False, ConsensusStatus.PENDING
        )
        assert permitted is False
        assert reason == "3-AI consensus required"

    def test_grey_zone_failed_blocks(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.GREY_ZONE, False, False, ConsensusStatus.FAILED
        )
        assert permitted is False
        assert reason == "3-AI consensus required"

    # Test 5: grey zone + CONFIRMED → permitted
    def test_grey_zone_confirmed_permits(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.GREY_ZONE, False, False, ConsensusStatus.CONFIRMED
        )
        assert permitted is True
        assert reason is None

    # Test 2: AVGO tier1 + no caps → permitted
    def test_tier1_no_caps_permits(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.TIER_1_CORE, False, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is True
        assert reason is None

    # Test 7: tier2 + no caps → permitted
    def test_tier2_no_caps_permits(self) -> None:
        permitted, reason = _compute_adds_permitted(
            Tier.TIER_2, False, False, ConsensusStatus.NOT_REQUIRED
        )
        assert permitted is True
        assert reason is None

    # beta_cap takes priority over concentration_cap
    def test_beta_cap_priority_over_concentration(self) -> None:
        _, reason = _compute_adds_permitted(Tier.TIER_2, True, True, ConsensusStatus.NOT_REQUIRED)
        assert reason == "Beta cap (F13) blocking adds"


# ---------------------------------------------------------------------------
# _score_band — verify band boundaries
# ---------------------------------------------------------------------------


class TestScoreBand:
    def test_tier1_core_band(self) -> None:
        lo, hi = _score_band(Tier.TIER_1_CORE)
        assert lo == 85
        assert hi is None

    def test_grey_zone_band(self) -> None:
        lo, hi = _score_band(Tier.GREY_ZONE)
        assert lo == 78
        assert hi == 84

    def test_tier2_band(self) -> None:
        lo, hi = _score_band(Tier.TIER_2)
        assert lo == 70
        assert hi == 77

    def test_tier3_band(self) -> None:
        lo, hi = _score_band(Tier.TIER_3)
        assert lo == 55
        assert hi == 69

    def test_watchlist_band(self) -> None:
        lo, hi = _score_band(Tier.WATCHLIST)
        assert lo == 0
        assert hi == 54


# ---------------------------------------------------------------------------
# Exit cycle tracking — test case 11
# ---------------------------------------------------------------------------


class TestExitCycle:
    def setup_method(self) -> None:
        # Reset store before each test so tests are independent.
        reset_exit_cycle("NEM")
        reset_exit_cycle("TSEM")

    # Test 4: starts at 0, not triggered
    def test_initial_count_is_zero(self) -> None:
        assert get_exit_cycle_count("NEM") == 0

    # Test 11: week 1 → count=1, not triggered
    def test_count_increments_on_sub55_score(self) -> None:
        count = update_exit_cycle("NEM", 52.0)
        assert count == 1

    # Test 11: week 2 → count=2, exit triggered
    def test_count_reaches_two(self) -> None:
        update_exit_cycle("NEM", 52.0)
        count = update_exit_cycle("NEM", 48.0)
        assert count == 2

    # Test 11 reset: score recovers above 55 → reset to 0
    def test_count_resets_on_score_above_55(self) -> None:
        update_exit_cycle("NEM", 52.0)
        count = update_exit_cycle("NEM", 58.0)
        assert count == 0

    def test_reset_function_clears_count(self) -> None:
        update_exit_cycle("NEM", 52.0)
        reset_exit_cycle("NEM")
        assert get_exit_cycle_count("NEM") == 0

    def test_ticker_uppercase_normalised(self) -> None:
        update_exit_cycle("nem", 52.0)
        assert get_exit_cycle_count("NEM") == 1


# ---------------------------------------------------------------------------
# Consensus status tracking — test cases 5, 6, 12
# ---------------------------------------------------------------------------


class TestConsensusStatus:
    def setup_method(self) -> None:
        reset_exit_cycle("MRVL")  # reuse to clear any state
        set_consensus_status("MRVL", ConsensusStatus.PENDING)

    # Test 6: PENDING → adds blocked
    def test_consensus_pending_returned(self) -> None:
        status = get_consensus_status_for_tier("MRVL", Tier.GREY_ZONE)
        assert status == ConsensusStatus.PENDING

    # Test 5: CONFIRMED → adds permitted
    def test_consensus_confirmed_returned(self) -> None:
        set_consensus_status("MRVL", ConsensusStatus.CONFIRMED)
        status = get_consensus_status_for_tier("MRVL", Tier.GREY_ZONE)
        assert status == ConsensusStatus.CONFIRMED

    # Non-grey-zone tiers always return NOT_REQUIRED
    def test_non_grey_zone_returns_not_required(self) -> None:
        status = get_consensus_status_for_tier("MRVL", Tier.TIER_2)
        assert status == ConsensusStatus.NOT_REQUIRED

    # Test 12: regime change should reset consensus
    def test_set_pending_acts_as_reset(self) -> None:
        set_consensus_status("MRVL", ConsensusStatus.CONFIRMED)
        set_consensus_status("MRVL", ConsensusStatus.PENDING)
        assert get_consensus_status_for_tier("MRVL", Tier.GREY_ZONE) == ConsensusStatus.PENDING

    def test_ticker_uppercase_normalised(self) -> None:
        set_consensus_status("mrvl", ConsensusStatus.CONFIRMED)
        assert get_consensus_status_for_tier("MRVL", Tier.GREY_ZONE) == ConsensusStatus.CONFIRMED
