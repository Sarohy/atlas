"""Tests for the F4 redesign: options-only decay score, stock-tape chips, clearance."""

from __future__ import annotations

from atlas.services.options_flow_service import (
    _bullish_share,
    _bullish_share_to_score,
    _dark_pool_daily_nets,
    _directional_premium,
    classify_dark_pool_state,
    clearance_state,
)


def _opt(day: str, opt_type: str, ask: float = 0.0, bid: float = 0.0) -> dict:
    return {
        "created_at": f"{day}T15:00:00Z",
        "type": opt_type,
        "total_ask_side_prem": ask,
        "total_bid_side_prem": bid,
        "total_premium": max(ask, bid),
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
# Layer 1 — classified net-directional flow (bullish_share)
# ---------------------------------------------------------------------------


class TestDirectionalShare:
    def test_call_buying_is_bullish(self) -> None:
        # call ASK buying dominates put ASK buying → bullish_share > 0.5 → score > 50.
        bull, bear, _ = _directional_premium(
            [_opt("2026-06-12", "call", ask=10_000_000), _opt("2026-06-12", "put", ask=4_000_000)]
        )
        share = _bullish_share(bull, bear)
        assert share is not None and share > 0.6
        assert _bullish_share_to_score(share) >= 60

    def test_put_buying_is_bearish(self) -> None:
        # ask-side put buying dominates → bearish; shows through, not neutralized to 50.
        bull, bear, _ = _directional_premium(
            [_opt("2026-06-12", "put", ask=10_000_000), _opt("2026-06-12", "call", ask=2_000_000)]
        )
        share = _bullish_share(bull, bear)
        assert share is not None and share < 0.4
        assert _bullish_share_to_score(share) <= 45

    def test_put_selling_is_bullish(self) -> None:
        # puts SOLD on the bid = bullish (downside sold).
        bull, bear, _ = _directional_premium([_opt("2026-06-12", "put", bid=10_000_000)])
        share = _bullish_share(bull, bear)
        assert share == 1.0
        assert _bullish_share_to_score(share) >= 80

    def test_call_selling_is_bearish(self) -> None:
        # calls SOLD on the bid = bearish (upside sold).
        bull, bear, _ = _directional_premium([_opt("2026-06-12", "call", bid=10_000_000)])
        share = _bullish_share(bull, bear)
        assert share == 0.0
        assert _bullish_share_to_score(share) <= 30

    def test_no_flow_is_neutral(self) -> None:
        assert _bullish_share(0.0, 0.0) is None
        assert _bullish_share_to_score(None) == 50

    def test_far_otm_put_is_down_weighted_vs_atm(self) -> None:
        # A far-OTM put (crash hedge) contributes less bearishness than an ATM put.
        atm = _directional_premium(
            [{"type": "put", "total_ask_side_prem": 10e6, "total_premium": 10e6,
              "strike": 100, "underlying_price": 100, "expiry": "2026-09-19"}]
        )
        far = _directional_premium(
            [{"type": "put", "total_ask_side_prem": 10e6, "total_premium": 10e6,
              "strike": 60, "underlying_price": 100, "expiry": "2026-09-19"}]
        )
        assert far[1] < atm[1]  # weighted bearish premium smaller for the far-OTM hedge


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
