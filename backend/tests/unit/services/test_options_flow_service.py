"""Unit tests for strategy-aware adjustments in F4 options flow scoring."""

from __future__ import annotations

from atlas.services.options_flow_service import (
    _alert_dte_days,
    _apply_dark_pool_quality_boost,
    _apply_strategy_aware_adjustment,
    _build_response_v2,
    _dark_pool_settlement_ratio,
)


def test_build_response_v2_applies_strategy_adjustment_for_complex_bullish_structure() -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "strike": 42,
                "underlying_price": 50,
                "total_ask_side_prem": 8_000_000.0,
                "total_bid_side_prem": 6_400_000.0,
                "total_premium": 9_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-09-19",
                "strike": 38,
                "underlying_price": 50,
                "total_ask_side_prem": 4_000_000.0,
                "total_bid_side_prem": 3_200_000.0,
                "total_premium": 4_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2026-08-21",
                "strike": 55,
                "underlying_price": 50,
                "total_ask_side_prem": 2_000_000.0,
                "total_bid_side_prem": 6_000_000.0,
                "total_premium": 6_200_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:12:00Z",
                "expiry": "2028-01-21",
                "strike": 65,
                "underlying_price": 50,
                "total_ask_side_prem": 5_000_000.0,
                "total_bid_side_prem": 500_000.0,
                "total_premium": 5_200_000.0,
            },
        ],
    )

    assert response.market_cap_tier == "MID"
    assert response.data_source == "OPTIONS_ONLY"
    assert response.options_net_flow_usd == 0.0
    assert response.options_flow_score == 50
    assert response.f4_score == 50
    assert response.flow_direction == "NEUTRAL"
    assert response.f4_grade == "NEUTRAL"


def test_build_response_v2_does_not_adjust_when_any_bullish_leg_is_missing() -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "strike": 42,
                "underlying_price": 50,
                "total_ask_side_prem": 8_000_000.0,
                "total_bid_side_prem": 6_400_000.0,
                "total_premium": 9_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-09-19",
                "strike": 38,
                "underlying_price": 50,
                "total_ask_side_prem": 4_000_000.0,
                "total_bid_side_prem": 3_200_000.0,
                "total_premium": 4_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2026-08-21",
                "strike": 55,
                "underlying_price": 50,
                "total_ask_side_prem": 2_000_000.0,
                "total_bid_side_prem": 6_000_000.0,
                "total_premium": 6_200_000.0,
            },
        ],
    )

    assert response.options_net_flow_usd == -10_000_000.0
    assert response.options_flow_score == 17
    assert response.f4_score == 17
    assert response.flow_direction == "BEARISH"
    assert response.f4_grade == "AVOID"


def test_build_response_v2_caps_adjustment_at_neutral_not_bullish_flip() -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "strike": 42,
                "underlying_price": 50,
                "total_ask_side_prem": 7_000_000.0,
                "total_bid_side_prem": 5_500_000.0,
                "total_premium": 7_500_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-09-19",
                "strike": 38,
                "underlying_price": 50,
                "total_ask_side_prem": 4_000_000.0,
                "total_bid_side_prem": 3_000_000.0,
                "total_premium": 4_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2026-08-21",
                "strike": 55,
                "underlying_price": 50,
                "total_ask_side_prem": 3_000_000.0,
                "total_bid_side_prem": 6_000_000.0,
                "total_premium": 6_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:12:00Z",
                "expiry": "2028-01-21",
                "strike": 65,
                "underlying_price": 50,
                "total_ask_side_prem": 5_000_000.0,
                "total_bid_side_prem": 300_000.0,
                "total_premium": 5_200_000.0,
            },
        ],
    )

    assert response.options_net_flow_usd == 0.0
    assert response.options_flow_score == 50
    assert response.flow_direction == "NEUTRAL"


def test_build_response_v2_applies_strategy_adjustment_when_overwrite_leg_is_one_year_dte() -> None:
    response = _build_response_v2(
        ticker="SNDK",
        market_cap=10_000_000_000.0,
        dp_prints=None,
        opt_trades=[
            {
                "type": "put",
                "created_at": "2026-06-03T15:00:00Z",
                "expiry": "2026-09-19",
                "strike": 42,
                "underlying_price": 50,
                "total_ask_side_prem": 8_000_000.0,
                "total_bid_side_prem": 6_400_000.0,
                "total_premium": 9_000_000.0,
            },
            {
                "type": "put",
                "created_at": "2026-06-03T15:05:00Z",
                "expiry": "2026-09-19",
                "strike": 38,
                "underlying_price": 50,
                "total_ask_side_prem": 4_000_000.0,
                "total_bid_side_prem": 3_200_000.0,
                "total_premium": 4_500_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:10:00Z",
                "expiry": "2027-06-18",
                "strike": 55,
                "underlying_price": 50,
                "total_ask_side_prem": 2_000_000.0,
                "total_bid_side_prem": 6_000_000.0,
                "total_premium": 6_200_000.0,
            },
            {
                "type": "call",
                "created_at": "2026-06-03T15:12:00Z",
                "expiry": "2028-01-21",
                "strike": 65,
                "underlying_price": 50,
                "total_ask_side_prem": 5_000_000.0,
                "total_bid_side_prem": 500_000.0,
                "total_premium": 5_200_000.0,
            },
        ],
    )

    assert response.options_net_flow_usd == 0.0
    assert response.options_flow_score == 50
    assert response.f4_score == 50
    assert response.flow_direction == "NEUTRAL"
    assert response.f4_grade == "NEUTRAL"


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
    # F4 is options-only now: strong dark-pool accumulation does NOT lift the score
    # (it surfaces via the chip/clearance instead). Options neutral -> F4 == 50.
    assert response.f4_score == 50
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
    assert response.dark_pool_score <= 50


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


async def test_dark_pool_fetch_paginates_until_five_sessions() -> None:
    from atlas.services.options_flow_service import _fetch_dark_pool_prints

    pages = [
        {"data": [_dp("2026-06-12"), _dp("2026-06-11")]},  # 2 distinct days
        {"data": [_dp("2026-06-10"), _dp("2026-06-09")]},  # 4 cumulative
        {"data": [_dp("2026-06-08")]},  # 5 cumulative -> stop
    ]
    client = _PagedClient(pages)
    prints = await _fetch_dark_pool_prints(client, "MU", {})  # type: ignore[arg-type]

    assert prints is not None and len(prints) == 5
    assert len(client.calls) == 3  # paginated across three pages
    # Pages 2 and 3 carry the older_than cursor from the prior page's last record.
    assert client.calls[1]["older_than"] == "2026-06-11T15:00:00Z"
    assert client.calls[2]["older_than"] == "2026-06-09T15:00:00Z"


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
    assert resp.dark_pool_sessions_covered == 5
