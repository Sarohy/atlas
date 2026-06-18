"""Unit tests for strategy-aware adjustments in F4 options flow scoring."""

from __future__ import annotations

import pytest

from atlas.services.options_flow_service import (
    _alert_dte_days,
    _apply_dark_pool_quality_boost,
    _apply_strategy_aware_adjustment,
    _build_response_v2,
    _dark_pool_confidence,
    _dark_pool_settlement_ratio,
    _f4_add_impact,
    _f4_state_label,
    _live_tape_state,
    _multi_window_score,
    _window_score,
    clearance_state,
)


# ---------------------------------------------------------------------------
# F4 Implementation Audit — score-band labels, add-impact, DP confidence
# ---------------------------------------------------------------------------


def test_f4_state_label_audit_bands() -> None:
    assert _f4_state_label(90) == "Strong bullish"
    assert _f4_state_label(75) == "Bullish"
    assert _f4_state_label(65) == "Mild bullish"
    assert _f4_state_label(62) == "Constructive"
    assert _f4_state_label(57) == "Neutral-constructive"
    assert _f4_state_label(52) == "Neutral"
    assert _f4_state_label(46) == "Mild bearish"
    assert _f4_state_label(43) == "Bearish"
    assert _f4_state_label(20) == "Aggressive bearish"


def test_f4_never_labels_sub_45_as_neutral() -> None:
    # Audit rule: no NEUTRAL below 45.
    for score in range(0, 45):
        assert "neutral" not in _f4_state_label(score).lower()


def test_f4_add_impact_never_says_buy() -> None:
    for score in range(0, 101):
        assert "buy" not in _f4_add_impact(score).lower()


def test_f4_add_impact_bands() -> None:
    assert "no full add" in _f4_add_impact(65).lower()  # supportive, not a buy
    assert "add blocked" in _f4_add_impact(46).lower()
    assert "trim-watch" in _f4_add_impact(43).lower()
    assert "avoid" in _f4_add_impact(20).lower()


def test_f4_framework_row_label_bands_never_say_buy() -> None:
    from atlas.services.options_flow_service import f4_framework_row_label

    assert f4_framework_row_label(90) == "Strong Bullish Options"
    assert f4_framework_row_label(75) == "Bullish Options"
    assert f4_framework_row_label(65) == "Mild Bullish / Supportive"
    assert f4_framework_row_label(62) == "Constructive"
    assert f4_framework_row_label(57) == "Neutral-Constructive"
    assert f4_framework_row_label(52) == "Neutral"
    assert f4_framework_row_label(46) == "Mild Bearish"
    assert f4_framework_row_label(43) == "Bearish"
    assert f4_framework_row_label(20) == "Aggressive Bearish"
    for score in range(0, 101):
        assert "buy" not in f4_framework_row_label(score).lower()


def test_dark_pool_confidence_bands() -> None:
    assert _dark_pool_confidence(2, 2, False).startswith("High")
    assert _dark_pool_confidence(1, 2, False).startswith("Low")
    assert _dark_pool_confidence(3, 5, False).startswith("Medium")
    assert _dark_pool_confidence(5, 5, True).startswith("Low")  # truncation
    assert _dark_pool_confidence(None, 2, False).startswith("No")


def test_clearance_mixed_absorption_when_bearish_options_meet_accumulation() -> None:
    # F4b bearish + F4a accumulation chip → WATCH / mixed absorption (no full add).
    state, reason = clearance_state("FRESH_ACCUMULATION", 30)
    assert state == "WATCH"
    assert "mixed absorption" in reason.lower()


def test_build_response_v2_score_43_is_bearish_not_neutral() -> None:
    # Acceptance test: F4b=43-ish from put-heavy tape → Bearish state, add blocked.
    response = _build_response_v2(
        ticker="X",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[_atm("put", ask=10_000_000.0), _atm("call", ask=3_000_000.0)],
    )
    assert response.f4_state in ("Bearish", "Mild bearish", "Aggressive bearish")
    assert response.f4_state != "Neutral"
    assert "buy" not in response.f4_add_impact.lower()


def _atm(opt_type: str, *, ask: float = 0.0, bid: float = 0.0) -> dict:
    # ATM (strike == spot), ~60 DTE → moneyness x expiry weight = 1.0.
    return {
        "type": opt_type,
        "created_at": "2026-06-15T15:00:00Z",
        "expiry": "2026-08-15",
        "strike": 50,
        "underlying_price": 50,
        "total_ask_side_prem": ask,
        "total_bid_side_prem": bid,
        "total_premium": max(ask, bid),
    }


def test_multi_window_weights_current_session_heaviest() -> None:
    # Today bullish (calls bought), four prior sessions bearish (puts bought).
    today_bull = [_atm("call", ask=10_000_000.0)]
    old_bear = [_atm("put", ask=10_000_000.0)]
    sessions = [today_bull, old_bear, old_bear, old_bear, old_bear]
    blended = _multi_window_score(sessions)
    flat_5_session = _window_score(sessions, 0, 5)
    # The current-session weight (35%) lifts the blend well above the flat average.
    assert flat_5_session is not None and blended is not None
    assert blended > flat_5_session


def test_live_tape_state_transitions() -> None:
    assert _live_tape_state(95, 30) == "Bullish reversal"
    assert _live_tape_state(10, 80) == "Bearish reversal"
    assert _live_tape_state(70, 65) == "Bullish persistent"
    assert _live_tape_state(20, 25) == "Bearish persistent"
    assert _live_tape_state(60, 50) == "Improving"
    assert _live_tape_state(44, 52) == "Deteriorating"
    assert _live_tape_state(None, 50) == "Data gap"


def test_build_response_v2_directional_put_buying_reads_bearish() -> None:
    # ATLAS F4 Classification Key: ask-side put buying + call selling = bearish,
    # shown through (not neutralized). bullish = call_ask 2M ; bearish = put_ask
    # 10M + call_bid 4M = 14M → bullish_share = 2/16 = 0.125 → low-20s.
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            _atm("put", ask=10_000_000.0),
            _atm("call", ask=2_000_000.0, bid=4_000_000.0),
        ],
    )
    assert response.data_source == "OPTIONS_ONLY"
    assert response.bullish_share is not None and response.bullish_share < 0.2
    assert response.f4_score <= 30
    assert response.flow_direction == "BEARISH"
    assert response.hedge_structure == "DIRECTIONAL_BEARISH"


def test_build_response_v2_call_buying_and_put_selling_reads_bullish() -> None:
    # call buying ($10M) + put selling ($4M) = bullish; a little put buying ($2M)
    # underneath. bullish = call_ask 10M + put_bid 4M = 14M ; bearish = put_ask 2M
    # → bullish_share = 14/16 = 0.875 → high-80s.
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            _atm("call", ask=10_000_000.0),
            _atm("put", ask=2_000_000.0, bid=4_000_000.0),
        ],
    )
    assert response.bullish_share is not None and response.bullish_share > 0.8
    assert response.f4_score >= 80
    assert response.flow_direction == "BULLISH"
    assert response.hedge_structure in ("BULLISH", "HEDGED_BULLISH")


def test_build_response_v2_call_buying_with_puts_underneath_is_hedged_bullish() -> None:
    # Strong call buying with significant ask-side put buying alongside → net
    # bullish but flagged HEDGED_BULLISH. bullish = call_ask 20M ; bearish =
    # put_ask 8M → share = 20/28 = 0.71 → bullish, hedged context.
    response = _build_response_v2(
        ticker="MU",
        market_cap=1_200_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            _atm("call", ask=20_000_000.0),
            _atm("put", ask=8_000_000.0),
        ],
    )
    assert response.bullish_share is not None and response.bullish_share > 0.6
    assert response.f4_score >= 60
    assert response.hedge_structure == "HEDGED_BULLISH"


def _structure_legs(*, put_ask: float) -> list[dict[str, object]]:
    """Two protective put legs + a near-dated covered-call overwrite + a LEAP."""
    return [
        {"type": "put", "expiry": "2026-09-19", "total_ask_side_prem": put_ask / 2,
         "total_bid_side_prem": 1_000_000.0},
        {"type": "put", "expiry": "2026-09-19", "total_ask_side_prem": put_ask / 2,
         "total_bid_side_prem": 1_000_000.0},
        {"type": "call", "expiry": "2026-08-21", "total_ask_side_prem": 1_000_000.0,
         "total_bid_side_prem": 2_000_000.0},  # near-dated overwrite (bid-dominant)
        {"type": "call", "expiry": "2028-01-21", "total_ask_side_prem": 5_000_000.0,
         "total_bid_side_prem": 500_000.0},  # LEAP accumulation (ask-dominant)
    ]


def test_relief_fires_only_when_bullish_side_confirms() -> None:
    # call_ask = 1M + 5M = 6M.
    # Branch A — bullish confirms (call_ask 6M >= put_ask 4M): relief neutralizes.
    confirms = _structure_legs(put_ask=4_000_000.0)
    assert _apply_strategy_aware_adjustment(confirms, -4_000_000.0) == 0.0
    # Branch B — bullish does NOT confirm (call_ask 6M < put_ask 10M): the
    # directional bearish net shows through unchanged (the NBIS case).
    directional = _structure_legs(put_ask=10_000_000.0)
    assert _apply_strategy_aware_adjustment(directional, -4_000_000.0) == -4_000_000.0


def test_relief_never_touches_already_bullish_flow() -> None:
    assert _apply_strategy_aware_adjustment(_structure_legs(put_ask=4_000_000.0), 9.0) == 9.0


def test_build_response_v2_dark_pool_does_not_enter_f4_score() -> None:
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=[
            {
                "executed_at": "2026-06-03T20:01:00Z",
                "price": 250.0,
                "nbbo_bid": 249.4,
                "nbbo_ask": 249.8,
                "premium": 2_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:02:00Z",
                "price": 250.1,
                "nbbo_bid": 249.5,
                "nbbo_ask": 249.9,
                "premium": 2_100_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:03:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_200_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:04:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_300_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:05:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_400_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:06:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 1_000_000.0,
                "sale_cond_codes": ["average_price"],
            },
        ],
        opt_trades=[
            {
                "type": "call",
                "created_at": "2026-06-03T15:00:00Z",
                "total_ask_side_prem": 1_000_000.0,
                "total_premium": 1_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "total_ask_side_prem": 1_000_000.0,
                "total_premium": 1_000_000.0,
            },
        ],
    )

    assert response.dark_pool_net_flow_usd == 11_000_000.0
    assert response.dark_pool_large_buy_count == 5
    assert response.options_net_flow_usd == 0.0
    # DP net ($11M) is below the $50M confirmation threshold → no upgrade; balanced
    # options (share 0.5) → F4 stays 50, options-only.
    assert response.f4_score == 50
    assert response.data_source == "OPTIONS_ONLY"


def _dp_buy(prem: float) -> dict:
    return {
        "executed_at": "2026-06-15T20:00:00Z",
        "price": 250.2, "nbbo_bid": 249.6, "nbbo_ask": 250.0,
        "premium": prem, "sale_cond_codes": [],
    }


def _dp_sell(prem: float) -> dict:
    return {
        "executed_at": "2026-06-15T20:00:00Z",
        "price": 248.0, "nbbo_bid": 249.6, "nbbo_ask": 250.0,
        "premium": prem, "sale_cond_codes": [],
    }


def test_dark_pool_buy_lean_is_not_scored_into_f4b() -> None:
    # Final scoring rule: F4a equity/dark-pool is NOT scored. A huge DP buy-lean
    # does NOT lift a bearish options tape — F4b stays bearish, source OPTIONS_ONLY.
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=[_dp_buy(200_000_000.0)],  # strong buy-lean
        opt_trades=[_atm("put", ask=10_000_000.0), _atm("call", bid=4_000_000.0)],
    )
    assert response.bullish_share is not None and response.bullish_share < 0.42
    assert response.f4_score <= 30
    assert response.data_source == "OPTIONS_ONLY"  # dark pool did not enter the score


def test_dark_pool_sell_lean_is_not_scored_into_f4b() -> None:
    # Balanced options + strong DP sell-lean → F4b stays neutral (DP not scored);
    # the sell-lean shows in the dark_pool_state / clearance overlay instead.
    response = _build_response_v2(
        ticker="LITE",
        market_cap=70_000_000_000.0,
        dp_prints=[_dp_sell(200_000_000.0)],
        opt_trades=[_atm("call", ask=2_000_000.0), _atm("put", ask=2_000_000.0)],
    )
    assert response.options_flow_score == 50
    assert response.f4_score == 50  # unchanged — F4a not scored
    assert response.data_source == "OPTIONS_ONLY"


def test_build_response_v2_does_not_boost_when_settlement_is_too_high() -> None:
    response = _build_response_v2(
        ticker="NBIS",
        market_cap=60_000_000_000.0,
        dp_prints=[
            {
                "executed_at": "2026-06-03T20:01:00Z",
                "price": 250.0,
                "nbbo_bid": 249.4,
                "nbbo_ask": 249.8,
                "premium": 2_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:02:00Z",
                "price": 250.1,
                "nbbo_bid": 249.5,
                "nbbo_ask": 249.9,
                "premium": 2_100_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-03T20:03:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_200_000.0,
                "sale_cond_codes": ["average_price"],
            },
            {
                "executed_at": "2026-06-03T20:04:00Z",
                "price": 250.2,
                "nbbo_bid": 249.6,
                "nbbo_ask": 250.0,
                "premium": 2_300_000.0,
                "sale_cond_codes": ["average_price"],
            },
        ],
        opt_trades=[
            {
                "type": "call",
                "created_at": "2026-06-03T15:00:00Z",
                "total_ask_side_prem": 1_000_000.0,
                "total_premium": 1_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "total_ask_side_prem": 1_000_000.0,
                "total_premium": 1_000_000.0,
            },
        ],
    )

    assert response.dark_pool_net_flow_usd == 4_100_000.0
    assert response.dark_pool_large_buy_count == 2
    # $4.1M net on a $60B LARGE-tier name maps to 57. The builder does not apply
    # the +10 quality boost (it is informational only; F4 is options-only), so
    # the dark-pool score stays at the un-boosted base — never 67.
    assert response.dark_pool_score == 57


def test_alert_dte_days_handles_missing_and_invalid_expiry() -> None:
    assert _alert_dte_days({}) is None
    assert _alert_dte_days({"expiry": "not-a-date"}) is None


def test_apply_strategy_aware_adjustment_returns_raw_when_legs_missing() -> None:
    raw_net = -4_000_000.0
    alerts = [
        {
            "type": "put",
            "expiry": "2026-09-19",
            "total_ask_side_prem": 2_000_000.0,
            "total_bid_side_prem": 1_000_000.0,
        },
        {
            "type": "call",
            "expiry": "2099-01-21",
            "total_ask_side_prem": 3_000_000.0,
            "total_bid_side_prem": 100_000.0,
        },
    ]
    assert _apply_strategy_aware_adjustment(alerts, raw_net) == raw_net


def test_dark_pool_settlement_ratio_returns_expected_fraction() -> None:
    ratio = _dark_pool_settlement_ratio(
        [
            {
                "price": 100.0,
                "nbbo_bid": 99.5,
                "nbbo_ask": 100.5,
                "premium": 1_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "price": 100.0,
                "nbbo_bid": 99.5,
                "nbbo_ask": 100.5,
                "premium": 1_000_000.0,
                "sale_cond_codes": ["average_price"],
            },
        ]
    )
    assert ratio == 0.5


def test_apply_dark_pool_quality_boost_applies_only_when_all_gates_pass() -> None:
    dp_prints = [
        {
            "price": 100.0,
            "nbbo_bid": 99.5,
            "nbbo_ask": 100.5,
            "premium": 1_000_000.0,
            "sale_cond_codes": [],
        },
        {
            "price": 100.1,
            "nbbo_bid": 99.6,
            "nbbo_ask": 100.6,
            "premium": 1_000_000.0,
            "sale_cond_codes": [],
        },
        {
            "price": 100.2,
            "nbbo_bid": 99.7,
            "nbbo_ask": 100.7,
            "premium": 1_000_000.0,
            "sale_cond_codes": [],
        },
    ]

    boosted = _apply_dark_pool_quality_boost(
        dp_score=58,
        dp_net_flow=11_000_000.0,
        dp_large_buys=4,
        dp_prints=dp_prints,
        opt_net_flow=0.0,
    )
    not_boosted = _apply_dark_pool_quality_boost(
        dp_score=58,
        dp_net_flow=11_000_000.0,
        dp_large_buys=2,
        dp_prints=dp_prints,
        opt_net_flow=0.0,
    )

    assert boosted == 68
    assert not_boosted == 58


# ---------------------------------------------------------------------------
# Dark-pool fetch pagination (older_than cursor until 5 sessions covered)
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _PagedClient:
    """Returns a queued payload per GET, recording the params of each call."""

    def __init__(self, pages: list[object]) -> None:
        self._pages = pages
        self.calls: list[dict] = []

    async def get(self, _url: str, params: dict | None = None, headers: dict | None = None):
        self.calls.append(params or {})
        idx = len(self.calls) - 1
        return _FakeResp(self._pages[idx] if idx < len(self._pages) else {"data": []})


def _dp(day: str) -> dict:
    return {"executed_at": f"{day}T15:00:00Z", "price": 10.0, "premium": 1000.0}


async def test_dark_pool_fetch_paginates_until_two_sessions() -> None:
    from atlas.services.options_flow_service import _fetch_dark_pool_prints

    pages = [
        {"data": [_dp("2026-06-12")]},  # 1 distinct day
        {"data": [_dp("2026-06-11")]},  # 2 cumulative -> stop (2-session window)
    ]
    client = _PagedClient(pages)
    prints = await _fetch_dark_pool_prints(client, "MU", {})  # type: ignore[arg-type]

    assert prints is not None and len(prints) == 2
    assert len(client.calls) == 2  # paginated across two pages
    # Page 2 carries the older_than cursor from page 1's last record.
    assert client.calls[1]["older_than"] == "2026-06-12T15:00:00Z"


async def test_dark_pool_fetch_stops_after_one_page_when_window_covered() -> None:
    from atlas.services.options_flow_service import _fetch_dark_pool_prints

    one_page = {
        "data": [_dp(f"2026-06-{d:02d}") for d in (12, 11, 10, 9, 8)]  # 5 distinct days at once
    }
    client = _PagedClient([one_page])
    prints = await _fetch_dark_pool_prints(client, "MU", {})  # type: ignore[arg-type]

    assert prints is not None and len(prints) == 5
    assert len(client.calls) == 1  # no pagination needed
    assert "older_than" not in client.calls[0]


def _dp_print(day: str, price: float = 10.0) -> dict:
    return {
        "executed_at": f"{day}T15:00:00Z",
        "price": price,
        "nbbo_bid": 9.9,
        "nbbo_ask": 10.1,
        "premium": 1000.0,
        "size": 100,
    }


def test_build_response_v2_flags_dark_pool_truncation_on_high_volume() -> None:
    from atlas.services.options_flow_service import _UW_DARK_POOL_MAX_PAGES, _UW_FETCH_LIMIT

    # Full page-cap of prints all on a single session -> truncation.
    n = _UW_DARK_POOL_MAX_PAGES * _UW_FETCH_LIMIT
    dp_prints = [_dp_print("2026-06-11") for _ in range(n)]
    resp = _build_response_v2(
        ticker="NVDA", market_cap=3_000_000_000_000.0, dp_prints=dp_prints, opt_trades=None
    )
    assert resp.dark_pool_truncated is True
    assert resp.dark_pool_sessions_covered == 1
    assert resp.data_gap_reason is not None
    assert "high-volume truncation" in resp.data_gap_reason


def test_build_response_v2_no_truncation_when_window_fully_covered() -> None:
    dp_prints = [_dp_print(f"2026-06-{d:02d}") for d in (11, 10, 9, 8, 5)]  # 5 distinct days
    resp = _build_response_v2(
        ticker="ACME", market_cap=8_000_000_000.0, dp_prints=dp_prints, opt_trades=None
    )
    assert resp.dark_pool_truncated is False
    # Window is 2 sessions → only the 2 most recent distinct days are covered.
    assert resp.dark_pool_sessions_covered == 2


def _dp_keep_buy(day: str, premium: float, price: float = 100.0) -> dict[str, object]:
    return {
        "executed_at": f"{day}T15:00:00Z",
        "price": price,
        "nbbo_bid": 99.0,
        "nbbo_ask": 100.0,
        "premium": premium,
        "sale_cond_codes": [],
    }


def _dp_keep_sell(day: str, premium: float, price: float = 99.0) -> dict[str, object]:
    return {
        "executed_at": f"{day}T15:00:00Z",
        "price": price,
        "nbbo_bid": 99.0,
        "nbbo_ask": 100.0,
        "premium": premium,
        "sale_cond_codes": [],
    }


def test_f4a_reconciliation_fields_match_kept_vs_stripped_breakdown() -> None:
    response = _build_response_v2(
        ticker="ASML",
        market_cap=300_000_000_000.0,
        dp_prints=[
            _dp_keep_buy("2026-06-17", 20_000_000.0),
            _dp_keep_sell("2026-06-17", 5_000_000.0),
            {
                "executed_at": "2026-06-17T15:05:00Z",
                "price": 99.6,
                "nbbo_bid": 99.0,
                "nbbo_ask": 100.0,
                "premium": 3_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-17T15:06:00Z",
                "price": 99.4,
                "nbbo_bid": 99.0,
                "nbbo_ask": 100.0,
                "premium": 2_000_000.0,
                "sale_cond_codes": [],
            },
            {
                "executed_at": "2026-06-17T15:10:00Z",
                "price": 100.0,
                "nbbo_bid": 99.0,
                "nbbo_ask": 100.0,
                "premium": 50_000_000.0,
                "sale_cond_codes": ["average_price_trade"],
            },
            {
                "executed_at": "2026-06-17T15:11:00Z",
                "price": 100.0,
                "nbbo_bid": 99.0,
                "nbbo_ask": 100.0,
                "premium": 30_000_000.0,
                "sale_cond_codes": ["QCT"],
            },
            {
                "executed_at": "2026-06-17T15:12:00Z",
                "price": 100.0,
                "nbbo_bid": 99.0,
                "nbbo_ask": 100.0,
                "premium": 10_000_000.0,
                "sale_cond_codes": ["sold_out_of_seq"],
            },
        ],
        opt_trades=[_atm("call", ask=4_000_000.0)],
    )

    assert response.raw_dark_pool_notional_usd == 120_000_000.0
    assert response.stripped_plumbing_notional_usd == 90_000_000.0
    assert response.kept_dark_pool_notional_usd == 30_000_000.0
    assert response.strict_buy_notional_usd == 20_000_000.0
    assert response.strict_sell_notional_usd == 5_000_000.0
    assert response.midpoint_lean_buy_notional_usd == 23_000_000.0
    assert response.midpoint_lean_sell_notional_usd == 7_000_000.0
    assert response.net_classified_flow_usd == 16_000_000.0
    assert response.buy_share == pytest.approx(23_000_000.0 / 30_000_000.0)
    assert response.largest_dark_pool_buy_usd == 20_000_000.0
    assert response.largest_stripped_print_usd == 50_000_000.0
    assert response.stripped_notional_by_reason == {
        "average_price_trade": 50_000_000.0,
        "QCT": 30_000_000.0,
        "sold_out_of_seq": 10_000_000.0,
    }


@pytest.mark.parametrize(
    "plumbing_code",
    [
        "average_price_trade",
        "prior_reference_price",
        "derivative_priced",
        "QCT",
        "sold_out_of_sequence",
        "sold_out_of_seq",
    ],
)
def test_f4a_strips_required_plumbing_aliases(plumbing_code: str) -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=8_000_000_000.0,
        dp_prints=[
            _dp_keep_sell("2026-06-17", 3_000_000.0),
            {
                "executed_at": "2026-06-17T15:10:00Z",
                "price": 100.0,
                "nbbo_bid": 99.0,
                "nbbo_ask": 100.0,
                "premium": 100_000_000.0,
                "sale_cond_codes": [plumbing_code],
            },
        ],
        opt_trades=[_atm("put", ask=3_000_000.0)],
    )

    assert response.raw_dark_pool_notional_usd == 103_000_000.0
    assert response.stripped_plumbing_notional_usd == 100_000_000.0
    assert response.kept_dark_pool_notional_usd == 3_000_000.0
    assert response.dark_pool_net_flow_usd == -3_000_000.0
    assert response.dark_pool_prints_count == 1
    expected_reason = (
        "sold_out_of_seq" if plumbing_code == "sold_out_of_sequence" else plumbing_code
    )
    assert response.stripped_notional_by_reason.get(expected_reason) == 100_000_000.0


def test_f4a_chip_and_flow_monitor_use_stripped_genuine_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    import atlas.services.options_flow_service as svc

    captured: dict[str, object] = {}
    original_resolve_flow_monitor = svc.resolve_flow_monitor

    def _fake_resolve_flow_monitor(inputs: object) -> object:
        captured["inputs"] = inputs
        return original_resolve_flow_monitor(inputs)  # pragma: no cover

    monkeypatch.setattr(svc, "resolve_flow_monitor", _fake_resolve_flow_monitor)

    response = _build_response_v2(
        ticker="SNDK",
        market_cap=8_000_000_000.0,
        dp_prints=[
            _dp_keep_sell("2026-06-17", 20_000_000.0),
            _dp_keep_sell("2026-06-16", 10_000_000.0),
            {
                "executed_at": "2026-06-17T15:10:00Z",
                "price": 100.0,
                "nbbo_bid": 99.0,
                "nbbo_ask": 100.0,
                "premium": 200_000_000.0,
                "sale_cond_codes": ["average_price_trade"],
            },
        ],
        opt_trades=[_atm("call", ask=4_000_000.0)],
    )

    assert response.dark_pool_state == "ACTIVE_DISTRIBUTION"
    assert response.dark_pool_net_flow_usd == -30_000_000.0
    assert response.largest_dark_pool_buy_usd is None
    assert response.largest_stripped_print_usd == 200_000_000.0

    inputs = captured["inputs"]
    assert hasattr(inputs, "f4a_state")
    assert getattr(inputs, "f4a_state") == "BEARISH"


def test_f4a_canceled_flag_string_false_is_not_stripped() -> None:
    response = _build_response_v2(
        ticker="ASML",
        market_cap=300_000_000_000.0,
        dp_prints=[
            {
                "executed_at": "2026-06-17T15:00:00Z",
                "price": 100.0,
                "nbbo_bid": 99.0,
                "nbbo_ask": 100.0,
                "premium": 4_000_000.0,
                "canceled": "false",
                "sale_cond_codes": [],
            }
        ],
        opt_trades=[_atm("call", ask=2_000_000.0)],
    )

    assert response.stripped_plumbing_notional_usd == 0.0
    assert response.kept_dark_pool_notional_usd == 4_000_000.0
    assert response.dark_pool_net_flow_usd == 4_000_000.0


def test_f4a_raw_and_kept_notional_include_premium_when_price_missing() -> None:
    response = _build_response_v2(
        ticker="ASML",
        market_cap=300_000_000_000.0,
        dp_prints=[
            {
                "executed_at": "2026-06-17T15:00:00Z",
                "premium": 7_500_000.0,
                "sale_cond_codes": [],
            }
        ],
        opt_trades=[_atm("call", ask=2_000_000.0)],
    )

    assert response.raw_dark_pool_notional_usd == 7_500_000.0
    assert response.kept_dark_pool_notional_usd == 7_500_000.0
    assert response.dark_pool_prints_count == 0
    assert response.net_classified_flow_usd == 0.0
