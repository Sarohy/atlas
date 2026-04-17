"""Unit tests for AnalystService — pure calculation functions.

All external HTTP calls are avoided; these tests cover the computation
logic that is deterministic from a known input.

F3 Analyst Conviction sub-indicators (0-100 each, weighted):
  1. Consensus Rating     (35%) — (Strong Buy + Buy) % of total analysts
  2. Analyst Count        (10%) — unique analysts covering the stock
  3. PT vs Current Price  (30%) — % upside from current price to consensus PT
  4. PT Revision Direction(25%) — PT raises / lowers in last 30 days

PT Ratio guard: when current_price / consensus_PT > 1.40, F3 is capped at 55.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.services.analyst_service import (
    _PT_RATIO_CAP_THRESHOLD,
    _PT_RATIO_F3_CAP,
    _build_analyst_response,
    _grade_from_total,
    _score_analyst_coverage,
    _score_consensus,
    _score_pt_revision,
    _score_pt_upside,
    AnalystService,
)

# ---------------------------------------------------------------------------
# _score_consensus
# ---------------------------------------------------------------------------


class TestScoreConsensus:
    """Buy-percentage → 0-100 component score (35% weight in F3)."""

    def test_above_80_pct_buy_scores_100(self) -> None:
        assert _score_consensus(81.0) == 100

    def test_exactly_80_pct_scores_80(self) -> None:
        # ">80" is the STRONG BUY gate; 80.0 is not > 80
        assert _score_consensus(80.0) == 80

    def test_60_pct_buy_scores_80(self) -> None:
        assert _score_consensus(60.0) == 80

    def test_59_pct_buy_scores_55(self) -> None:
        assert _score_consensus(59.9) == 55

    def test_40_pct_buy_scores_55(self) -> None:
        assert _score_consensus(40.0) == 55

    def test_39_pct_buy_scores_20(self) -> None:
        assert _score_consensus(39.9) == 20

    def test_zero_pct_buy_scores_20(self) -> None:
        assert _score_consensus(0.0) == 20

    def test_none_returns_55_neutral(self) -> None:
        # No analyst data → neutral, not zero
        assert _score_consensus(None) == 55


# ---------------------------------------------------------------------------
# _score_analyst_coverage
# ---------------------------------------------------------------------------


class TestScoreAnalystCoverage:
    """Analyst count → 0-100 component score (10% weight in F3)."""

    def test_more_than_20_analysts_scores_100(self) -> None:
        assert _score_analyst_coverage(21) == 100

    def test_exactly_20_analysts_scores_85(self) -> None:
        # ">20" gate; 20 falls into the 10-20 band
        assert _score_analyst_coverage(20) == 85

    def test_10_analysts_scores_85(self) -> None:
        assert _score_analyst_coverage(10) == 85

    def test_9_analysts_scores_65(self) -> None:
        assert _score_analyst_coverage(9) == 65

    def test_5_analysts_scores_65(self) -> None:
        assert _score_analyst_coverage(5) == 65

    def test_4_analysts_scores_40(self) -> None:
        # Hard cap at 40 for <5 analysts per guide
        assert _score_analyst_coverage(4) == 40

    def test_0_analysts_scores_40(self) -> None:
        assert _score_analyst_coverage(0) == 40

    def test_none_returns_40(self) -> None:
        assert _score_analyst_coverage(None) == 40


# ---------------------------------------------------------------------------
# _score_pt_upside
# ---------------------------------------------------------------------------


class TestScorePtUpside:
    """% upside to consensus PT → 0-100 component score (30% weight in F3)."""

    def test_above_30_pct_upside_scores_100(self) -> None:
        assert _score_pt_upside(31.0) == 100

    def test_exactly_30_pct_upside_scores_85(self) -> None:
        # ">30" gate; 30.0 is not > 30
        assert _score_pt_upside(30.0) == 85

    def test_15_pct_upside_scores_85(self) -> None:
        assert _score_pt_upside(15.0) == 85

    def test_14_pct_upside_scores_70(self) -> None:
        assert _score_pt_upside(14.9) == 70

    def test_5_pct_upside_scores_70(self) -> None:
        assert _score_pt_upside(5.0) == 70

    def test_4_pct_upside_scores_55(self) -> None:
        assert _score_pt_upside(4.9) == 55

    def test_zero_upside_scores_55(self) -> None:
        assert _score_pt_upside(0.0) == 55

    def test_negative_upside_scores_20(self) -> None:
        # Stock above PT → 20 (bearish signal)
        assert _score_pt_upside(-10.0) == 20

    def test_none_returns_55_neutral(self) -> None:
        assert _score_pt_upside(None) == 55


# ---------------------------------------------------------------------------
# _score_pt_revision
# ---------------------------------------------------------------------------


class TestScorePtRevision:
    """PT revision counts (last 30 days) → 0-100 component score (25% weight in F3)."""

    def test_two_or_more_raises_scores_100(self) -> None:
        assert _score_pt_revision(raises=2, lowers=0) == 100
        assert _score_pt_revision(raises=5, lowers=1) == 100

    def test_one_raise_scores_80(self) -> None:
        assert _score_pt_revision(raises=1, lowers=0) == 80

    def test_no_change_scores_60(self) -> None:
        assert _score_pt_revision(raises=0, lowers=0) == 60

    def test_any_lower_scores_20(self) -> None:
        assert _score_pt_revision(raises=0, lowers=1) == 20
        assert _score_pt_revision(raises=0, lowers=3) == 20


# ---------------------------------------------------------------------------
# _grade_from_total
# ---------------------------------------------------------------------------


class TestGradeFromTotal:
    """F3 score → STRONG BUY / BUY / NEUTRAL / WEAK / AVOID label."""

    def test_80_is_strong_buy(self) -> None:
        assert _grade_from_total(80) == "STRONG BUY"

    def test_100_is_strong_buy(self) -> None:
        assert _grade_from_total(100) == "STRONG BUY"

    def test_79_is_buy(self) -> None:
        assert _grade_from_total(79) == "BUY"

    def test_60_is_buy(self) -> None:
        assert _grade_from_total(60) == "BUY"

    def test_59_is_neutral(self) -> None:
        assert _grade_from_total(59) == "NEUTRAL"

    def test_40_is_neutral(self) -> None:
        assert _grade_from_total(40) == "NEUTRAL"

    def test_39_is_weak(self) -> None:
        assert _grade_from_total(39) == "WEAK"

    def test_20_is_weak(self) -> None:
        assert _grade_from_total(20) == "WEAK"

    def test_19_is_avoid(self) -> None:
        assert _grade_from_total(19) == "AVOID"

    def test_0_is_avoid(self) -> None:
        assert _grade_from_total(0) == "AVOID"


# ---------------------------------------------------------------------------
# _build_analyst_response — PT Ratio cap
#
# The cap: if current_price / consensus_PT > 1.40 the stock is trading more
# than 40% above analyst targets. F3 is capped at 55 (NEUTRAL) regardless of
# the weighted composite.  The cap must run BEFORE the AnalystResponse is
# built so that f3_score in the response is already the final, capped value.
# ---------------------------------------------------------------------------


def _bullish_response(
    *,
    current_price: float | None,
    consensus_pt: float | None,
) -> object:
    """Build a response with maximally bullish non-price inputs so that the
    raw F3 before any cap would be well above 55, making cap-vs-no-cap easy
    to distinguish.

    strong_buy=10 → buy_pct=100% → consensus_score=100 (>80%)
    num_analysts=15 → coverage_score=85 (10-20 analysts)
    pt_raises=2, pt_lowers=0 → revision_score=100 (multiple raises)
    Weighted pre-cap = 100*0.35 + 85*0.10 + upside*0.30 + 100*0.25
    When stock is above PT (upside_score=20): pre-cap = 35+8.5+6+25 = 74.5 → 75
    When no PT data (upside_score=55): pre-cap = 35+8.5+16.5+25 = 85 → 85
    """
    return _build_analyst_response(
        ticker="TEST",
        strong_buy=10,
        buy=0,
        hold=0,
        sell=0,
        strong_sell=0,
        num_analysts=15,
        consensus_pt=consensus_pt,
        current_price=current_price,
        pt_raises=2,
        pt_lowers=0,
    )


class TestPtRatioCap:
    """PT Ratio cap — current_price / consensus_PT > 1.40 → f3_score ≤ 55."""

    def test_cap_applies_when_ratio_above_threshold(self) -> None:
        # pt_ratio = 150/100 = 1.50 > 1.40 → cap must fire
        response = _bullish_response(current_price=150.0, consensus_pt=100.0)
        assert response.f3_score <= _PT_RATIO_F3_CAP  # type: ignore[union-attr]

    def test_cap_brings_score_to_exactly_55_when_raw_is_higher(self) -> None:
        # Without cap the bullish inputs would produce 75; cap must give 55
        response = _bullish_response(current_price=150.0, consensus_pt=100.0)
        assert response.f3_score == _PT_RATIO_F3_CAP  # type: ignore[union-attr]

    def test_cap_does_not_apply_at_exact_threshold(self) -> None:
        # pt_ratio = 140/100 = 1.40; condition is "> 1.40" so 1.40 is excluded
        response = _bullish_response(current_price=140.0, consensus_pt=100.0)
        assert response.f3_score > _PT_RATIO_F3_CAP  # type: ignore[union-attr]

    def test_cap_does_not_apply_when_price_below_pt(self) -> None:
        # Stock below PT → pt_ratio < 1 → no cap
        response = _bullish_response(current_price=80.0, consensus_pt=100.0)
        assert response.f3_score > _PT_RATIO_F3_CAP  # type: ignore[union-attr]

    def test_cap_does_not_apply_when_no_current_price(self) -> None:
        # Polygon returned no price → pt_ratio is None → cap must not silently
        # lower an otherwise legitimate score
        response = _bullish_response(current_price=None, consensus_pt=100.0)
        assert response.f3_score > _PT_RATIO_F3_CAP  # type: ignore[union-attr]

    def test_cap_does_not_apply_when_no_consensus_pt(self) -> None:
        response = _bullish_response(current_price=150.0, consensus_pt=None)
        assert response.f3_score > _PT_RATIO_F3_CAP  # type: ignore[union-attr]

    def test_cap_threshold_constant_is_1_40(self) -> None:
        assert _PT_RATIO_CAP_THRESHOLD == 1.40

    def test_cap_value_constant_is_55(self) -> None:
        assert _PT_RATIO_F3_CAP == 55

    def test_f3_score_stored_in_response_is_already_capped(self) -> None:
        """f3_score on AnalystResponse must be the final, post-cap value so
        that framework_score_service always reads the capped number."""
        response = _bullish_response(current_price=200.0, consensus_pt=100.0)
        # pt_ratio=2.0 >> 1.40; score must be 55, not the raw 75
        assert response.f3_score == 55  # type: ignore[union-attr]

    def test_cap_applies_just_above_threshold(self) -> None:
        # pt_ratio = 141/100 = 1.41, just over the line
        response = _bullish_response(current_price=141.0, consensus_pt=100.0)
        assert response.f3_score == _PT_RATIO_F3_CAP  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# _fetch_current_price — prevDay.c fallback
#
# Polygon sets day.c = 0 before any trade executes on the current session
# (pre-market / overnight).  Using 0 as the price would make the
# ``if current_price`` guard fail in _build_analyst_response, leaving
# pt_ratio as None and silently bypassing the PT-ratio cap.
# The method must fall back to prevDay.c in that case.
# ---------------------------------------------------------------------------


def _polygon_snapshot(day_close: float | None, prev_close: float | None) -> dict:
    """Build a minimal Polygon v2/snapshot response for testing."""
    day: dict = {}
    if day_close is not None:
        day["c"] = day_close
    prev_day: dict = {}
    if prev_close is not None:
        prev_day["c"] = prev_close
    return {"ticker": {"day": day, "prevDay": prev_day}}


def _mock_http_client(payload: dict) -> AsyncMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    return client


class TestFetchCurrentPrice:
    """_fetch_current_price must return prevDay.c when day.c is 0 or absent."""

    async def test_returns_day_close_when_positive(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=150.0, prev_close=140.0))
        result = await service._fetch_current_price(client, "AAOI")
        assert result == 150.0

    async def test_falls_back_to_prevday_when_day_close_is_zero(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=0, prev_close=136.50))
        result = await service._fetch_current_price(client, "AAOI")
        assert result == 136.50

    async def test_falls_back_to_prevday_when_day_close_absent(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=None, prev_close=136.50))
        result = await service._fetch_current_price(client, "AAOI")
        assert result == 136.50

    async def test_returns_none_when_both_prices_are_zero(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=0, prev_close=0))
        result = await service._fetch_current_price(client, "AAOI")
        assert result is None

    async def test_returns_none_when_both_prices_absent(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="poly")
        client = _mock_http_client(_polygon_snapshot(day_close=None, prev_close=None))
        result = await service._fetch_current_price(client, "AAOI")
        assert result is None

    async def test_returns_none_when_no_polygon_key(self) -> None:
        service = AnalystService(benzinga_api_key="bz", polygon_api_key="")
        client = _mock_http_client(_polygon_snapshot(day_close=150.0, prev_close=140.0))
        result = await service._fetch_current_price(client, "AAOI")
        assert result is None
        client.get.assert_not_called()
