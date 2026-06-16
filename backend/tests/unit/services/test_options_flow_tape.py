"""Tests for the F4 options-source fix (empty-vs-error + per-trade tape fallback).

The flow-ALERTS feed is the primary, anchor-calibrated score source; the raw
per-trade tape is a fallback used only when alerts hard-error. These tests cover:
  - the empty-vs-error distinction at the fetch boundary ([] vs None);
  - a successful-but-EMPTY feed → real neutral 50 (OPTIONS_ONLY), NOT a gap;
  - only "no source at all" (tape None + alerts None) is a DATA_GAP;
  - the per-trade tape aggregator + flow-recent schema normalization
    (option_type from the OCC symbol, side from UW tags / NBBO).
"""

from __future__ import annotations

from typing import Any

import pytest

from atlas.services import provider_response_cache as cache
from atlas.services.options_flow_service import (
    _build_response_v2,
    _decay_weighted_tape,
    _fetch_option_trades_tape,
    _normalize_tape_record,
)

LARGE_CAP = 60_000_000_000.0


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    cache.clear_provider_response_cache()
    yield
    cache.clear_provider_response_cache()


# ---------------------------------------------------------------------------
# Pure aggregation — _decay_weighted_tape over per-trade records
# ---------------------------------------------------------------------------


def _call(side: str, prem: float, day: str = "2026-06-15") -> dict[str, Any]:
    return {
        "type": "call",
        "side": side,
        "premium": prem,
        "executed_at": f"{day}T15:00:00Z",
    }


def test_decay_weighted_tape_empty_is_zero() -> None:
    assert _decay_weighted_tape([]) == (0.0, None)


def test_decay_weighted_tape_bullish_calls_positive() -> None:
    net, largest = _decay_weighted_tape(
        [_call("ASK", 3_000_000.0), _call("ASK", 1_000_000.0)]
    )
    assert net > 0
    assert largest == 3_000_000.0


def test_decay_weighted_tape_strips_profit_taking() -> None:
    # call sold on BID = PROFIT_TAKING → stripped → net 0.
    net, _ = _decay_weighted_tape([_call("BID", 5_000_000.0)])
    assert net == 0.0


# ---------------------------------------------------------------------------
# Record normalization — side inferred from NBBO, premium reconstructed
# ---------------------------------------------------------------------------


def test_normalize_infers_side_from_nbbo() -> None:
    rec = _normalize_tape_record(
        {"type": "call", "price": 5.0, "nbbo_ask": 5.0, "nbbo_bid": 4.5,
         "premium": 1_000_000.0, "created_at": "2026-06-15T15:00:00Z"}
    )
    assert rec["side"] == "ASK"
    assert rec["executed_at"] == "2026-06-15T15:00:00Z"


def test_normalize_reads_real_flow_recent_schema() -> None:
    # Real UW flow-recent record: no `type`/`side` fields — type is in the OCC
    # symbol, side is in `tags`. This was the bug that floored every score at 50.
    rec = _normalize_tape_record(
        {
            "option_chain_id": "NVDA260617P00202500",
            "tags": ["ask_side", "bearish"],
            "premium": "23.00",
            "executed_at": "2026-06-16T14:03:33Z",
        }
    )
    assert rec["option_type"] == "put"
    assert rec["side"] == "ASK"
    # put bought on the ask = bearish → negative contribution.
    net, _ = _decay_weighted_tape([rec])
    assert net < 0


def test_normalize_reconstructs_premium_from_size_price() -> None:
    rec = _normalize_tape_record(
        {"type": "put", "price": 2.0, "size": 100, "executed_at": "2026-06-15T15:00:00Z"}
    )
    assert rec["premium"] == pytest.approx(2.0 * 100 * 100.0)


# ---------------------------------------------------------------------------
# Builder — tape is the primary source; empty tape is neutral, not a gap
# ---------------------------------------------------------------------------


def test_empty_tape_is_real_neutral_not_data_gap() -> None:
    r = _build_response_v2(ticker="ABC", market_cap=LARGE_CAP, dp_prints=None, opt_tape=[])
    assert r.f4_score == 50
    assert r.data_source == "OPTIONS_ONLY"  # earned neutral, not a gap
    assert r.data_gap_reason is not None and "not a data gap" in r.data_gap_reason


def test_no_source_at_all_is_data_gap() -> None:
    r = _build_response_v2(
        ticker="ABC", market_cap=LARGE_CAP, dp_prints=None, opt_tape=None, opt_trades=None
    )
    assert r.f4_score == 50
    assert r.data_source == "DATA_GAP"


def test_tape_bullish_flow_lifts_score_above_neutral() -> None:
    r = _build_response_v2(
        ticker="ABC",
        market_cap=LARGE_CAP,
        dp_prints=None,
        opt_tape=[_call("ASK", 60_000_000.0)],
    )
    assert r.f4_score > 50
    assert r.data_source == "OPTIONS_ONLY"
    assert r.flow_direction == "BULLISH"


def test_alerts_used_as_fallback_when_tape_errors() -> None:
    # opt_tape is None (hard error) but the alerts feed has data → fallback path.
    r = _build_response_v2(
        ticker="ABC",
        market_cap=LARGE_CAP,
        dp_prints=None,
        opt_tape=None,
        opt_trades=[
            {"type": "call", "created_at": "2026-06-15T15:00:00Z",
             "total_ask_side_prem": 60_000_000.0, "total_premium": 60_000_000.0},
        ],
    )
    assert r.data_source == "OPTIONS_ONLY"
    assert r.f4_score > 50


# ---------------------------------------------------------------------------
# Fetch — empty-success returns [], hard error returns None
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, payload: Any, *, fail: bool = False) -> None:
        self._payload = payload
        self._fail = fail

    def raise_for_status(self) -> None:
        if self._fail:
            import httpx

            raise httpx.HTTPError("boom")

    def json(self) -> Any:
        return self._payload


class _Client:
    def __init__(self, responses: list[_Resp]) -> None:
        self._responses = responses
        self.calls = 0

    async def get(self, *_a: Any, **_k: Any) -> _Resp:
        r = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return r


@pytest.mark.asyncio
async def test_fetch_tape_empty_success_returns_empty_list() -> None:
    client = _Client([_Resp({"data": []})])
    out = await _fetch_option_trades_tape(client, "ABC", {})  # type: ignore[arg-type]
    assert out == []  # NOT None — a real "no flow" reading


@pytest.mark.asyncio
async def test_fetch_tape_hard_error_returns_none() -> None:
    client = _Client([_Resp(None, fail=True)])
    out = await _fetch_option_trades_tape(client, "ABC", {})  # type: ignore[arg-type]
    assert out is None
