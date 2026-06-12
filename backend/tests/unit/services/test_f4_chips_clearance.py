"""Tests for the F4 redesign: options-only decay score, stock-tape chips, clearance."""

from __future__ import annotations

from atlas.services.options_flow_service import (
    _dark_pool_daily_nets,
    _decay_weighted_options,
    classify_dark_pool_state,
    clearance_state,
)


def _opt(day: str, opt_type: str, ask: float) -> dict:
    return {
        "created_at": f"{day}T15:00:00Z",
        "type": opt_type,
        "total_ask_side_prem": ask,
        "total_premium": ask,
    }


def _dp(day: str, buy: bool, prem: float = 2_000_000.0) -> dict:
    # price at/above ask => BUY ; at/below bid => SELL
    return {
        "executed_at": f"{day}T20:00:00Z",
        "price": 250.0 if buy else 248.0,
        "nbbo_bid": 249.0,
        "nbbo_ask": 249.5,
        "premium": prem,
        "sale_cond_codes": [],
    }


# ---------------------------------------------------------------------------
# Layer 1 — options-only, time-decay ("fading memory")
# ---------------------------------------------------------------------------


class TestDecayWeighting:
    def test_recent_session_dominates(self) -> None:
        # Today strongly bullish, four days ago strongly bearish (same magnitude).
        recent_bull = [_opt("2026-06-12", "call", 10_000_000)]
        old_bear = [_opt("2026-06-08", "put", 10_000_000)]
        net, _ = _decay_weighted_options(recent_bull + old_bear)
        # today weight (40) >> 4-days-ago weight (10) -> net is positive (bullish).
        assert net > 0

    def test_single_session_preserves_magnitude(self) -> None:
        # One session: weighted net equals the raw net (weight normalises to 1.0).
        alerts = [_opt("2026-06-12", "call", 5_000_000), _opt("2026-06-12", "put", 2_000_000)]
        net, _ = _decay_weighted_options(alerts)
        assert net == 3_000_000.0

    def test_empty_is_zero(self) -> None:
        assert _decay_weighted_options([]) == (0.0, None)


# ---------------------------------------------------------------------------
# Layer 2 — stock-tape chips
# ---------------------------------------------------------------------------


class TestChips:
    def test_persistent_accumulation(self) -> None:
        nets = [5.0, 4.0, 3.0, 2.0, 1.0]  # 5 sessions all buying
        state, _ = classify_dark_pool_state(nets)
        assert state == "PERSISTENT_ACCUMULATION"

    def test_fresh_accumulation(self) -> None:
        # Buying only in the last 2 sessions, accelerating; earlier flat/negative.
        nets = [6.0, 3.0, -1.0, -1.0, 0.0]  # newest first
        state, _ = classify_dark_pool_state(nets)
        assert state == "FRESH_ACCUMULATION"

    def test_active_distribution(self) -> None:
        nets = [-5.0, -4.0, 1.0, 1.0, 1.0]  # two recent sell sessions, net negative
        state, _ = classify_dark_pool_state(nets)
        assert state == "ACTIVE_DISTRIBUTION"

    def test_fading(self) -> None:
        # Earlier accumulation, latest session flips to selling (not full distribution).
        nets = [-2.0, 5.0, 4.0, 3.0, 2.0]
        state, _ = classify_dark_pool_state(nets)
        assert state == "FADING"

    def test_neutral_mixed(self) -> None:
        assert classify_dark_pool_state([1.0, -1.0, 1.0])[0] == "NEUTRAL_MIXED"

    def test_unknown_when_empty(self) -> None:
        assert classify_dark_pool_state([])[0] == "UNKNOWN"

    def test_daily_nets_from_prints_newest_first(self) -> None:
        prints = [_dp("2026-06-12", buy=True), _dp("2026-06-11", buy=False)]
        nets = _dark_pool_daily_nets(prints)
        assert len(nets) == 2
        assert nets[0] > 0 > nets[1]  # newest (buy) first, then sell


# ---------------------------------------------------------------------------
# Layer 3 — clearance
# ---------------------------------------------------------------------------


class TestClearance:
    def test_active_distribution_revokes(self) -> None:
        assert clearance_state("ACTIVE_DISTRIBUTION", 90)[0] == "REVOKED"

    def test_fading_is_watch(self) -> None:
        assert clearance_state("FADING", 90)[0] == "WATCH"

    def test_accumulation_plus_strong_flow_clears(self) -> None:
        assert clearance_state("PERSISTENT_ACCUMULATION", 70)[0] == "CLEARED"
        assert clearance_state("FRESH_ACCUMULATION", 60)[0] == "CLEARED"

    def test_accumulation_but_weak_flow_does_not_clear(self) -> None:
        assert clearance_state("PERSISTENT_ACCUMULATION", 55)[0] == "WATCH"

    def test_weak_flow_is_watch(self) -> None:
        assert clearance_state("NEUTRAL_MIXED", 30)[0] == "WATCH"
