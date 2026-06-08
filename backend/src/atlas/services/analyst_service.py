"""F3 Analyst Conviction service — v7.3.5 scoring algorithm.

Data sources:
  - Benzinga   → consensus ratings, analyst count, consensus PT, PT revision (30d),
                 net upgrades/downgrades (90d for recency-weighted momentum)
  - Alpha Vantage → fallback consensus (OVERVIEW endpoint)
  - FMP        → second fallback consensus
  - Polygon.io → current stock price

F3 v7.3.5 scoring (4-bucket PT approach + recency-weighted upgrade modifier):
  Bucket 1: PT > price                              → base 80
  Bucket 2: PT ≤ price + positive revision (30d)   → base 55
  Bucket 3: PT ≤ price + ≥20 analysts + avg ≥ 4.0 → base 65
  Bucket 4: Neither                                 → base 40
  Plus: recency-weighted upgrade/downgrade modifier (0-30d 1.0x, 31-60d 0.5x, 61-90d 0.25x)
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final

import httpx
import yfinance as yf  # type: ignore[import-untyped]

from atlas.schemas.analyst import (
    AnalystCoverageIndicator,
    AnalystResponse,
    ConsensusRatingIndicator,
    PtDirectionIndicator,
    PtUpsideIndicator,
    RecentUpgradesIndicator,
)
from atlas.services.provider_response_cache import fetch_alpha_vantage_cached

# ---------------------------------------------------------------------------
# F3 factor weight (in the conviction score formula)
# ---------------------------------------------------------------------------

_W_F3: Final[float] = 0.15

# ---------------------------------------------------------------------------
# v7.3.4 base score constants — Priority 1
# ---------------------------------------------------------------------------

_BASE_STRONG_BUY: Final[int] = 90
_BASE_BUY: Final[int] = 78
_BASE_HOLD: Final[int] = 55
_BASE_SELL: Final[int] = 30

# v7.3.5 — 4-bucket base scores (Change 1)
_F3_BUCKET_PT_ABOVE: Final[int] = 80  # Bucket 1: PT > price
_F3_BUCKET_POS_REVISION: Final[int] = 55  # Bucket 2: PT ≤ price + positive revision (30d)
_F3_BUCKET_STRONG_COV: Final[int] = 65  # Bucket 3: PT ≤ price + strong coverage/consensus
_F3_BUCKET_NEITHER: Final[int] = 40  # Bucket 4: none of the above

# Bucket 3 thresholds
_F3_BUCKET3_MIN_ANALYSTS: Final[int] = 20  # ≥20 analysts required
_F3_BUCKET3_MIN_CONSENSUS_AVG: Final[float] = 4.0  # weighted avg consensus ≥ 4.0 required

# Grade thresholds (unchanged from v7.3.3)
_GRADE_STRONG_BUY: Final[int] = 80
_GRADE_BUY: Final[int] = 60
_GRADE_NEUTRAL: Final[int] = 40
_GRADE_WEAK: Final[int] = 20

# ---------------------------------------------------------------------------
# API constants
# ---------------------------------------------------------------------------

_BENZINGA_BASE_URL: Final[str] = "https://api.benzinga.com"
_POLYGON_BASE_URL: Final[str] = "https://api.polygon.io"
_FMP_BASE_URL: Final[str] = "https://financialmodelingprep.com"
_TIMEOUT: Final[float] = 10.0

# PT revision / upgrade look-back windows in days
_REVISION_DAYS: Final[int] = 30  # PT raises/lowers — bucket 2 signal
_REVISION_DAYS_EXTENDED: Final[int] = 90  # upgrade/downgrade fetch window (Change 2)

# Recency weights for upgrade/downgrade momentum (Change 2)
_UD_WEIGHT_RECENT: Final[float] = 1.0  # 0-30 days
_UD_WEIGHT_MID: Final[float] = 0.5  # 31-60 days
_UD_WEIGHT_OLD: Final[float] = 0.25  # 61-90 days

# Price vs target band labels
_BAND_BELOW_20: Final[str] = "20%+ below target (+10)"
_BAND_BELOW_10: Final[str] = "10-20% below target (+5)"
_BAND_NEUTRAL: Final[str] = "At target — neutral (0)"
_BAND_ABOVE_10: Final[str] = "10-20% above target (-15)"
_BAND_ABOVE_20: Final[str] = "20%+ above target"


# ---------------------------------------------------------------------------
# FactorScore return type for score_f3
# ---------------------------------------------------------------------------


@dataclass
class FactorScore:
    """Return value from score_f3 — full breakdown of the F3 calculation."""

    raw_score: float
    """F3 score clamped to [0, 100]."""

    weight: float
    """F3 weight in the conviction formula (always 0.15)."""

    weighted_contribution: float
    """raw_score * weight — contribution to the final conviction score."""

    breakdown: dict[str, Any]
    """Per-component values for audit trail and UI display."""

    override_applied: bool
    """Always False in v7.3.5 (override mechanism removed)."""

    override_reason: str | None
    """Always None in v7.3.5."""


# ---------------------------------------------------------------------------
# v7.3.4 pure scoring helpers — no I/O, no side effects
# ---------------------------------------------------------------------------


def _base_score_from_consensus(consensus_rating: str) -> int:
    """Priority 1 — map consensus label to base score.

    Strong Buy → 90 | Buy → 78 | Hold → 55 | Sell (or unknown) → 30
    """
    r = consensus_rating.strip().upper()
    if r == "STRONG BUY":
        return _BASE_STRONG_BUY
    if r == "BUY":
        return _BASE_BUY
    if r == "HOLD":
        return _BASE_HOLD
    return _BASE_SELL


def _analyst_count_modifier(count: int) -> int:
    """Priority 2 — analyst coverage count → modifier.

    >30 → +8 | 20-30 → +5 | 10-19 → +3 | 5-9 → 0 | <5 → -5
    """
    if count > 30:
        return 8
    if count >= 20:
        return 5
    if count >= 10:
        return 3
    if count >= 5:
        return 0
    return -5


def _pt_revision_direction_label(raises: int, lowers: int) -> str:
    """Derive PT revision direction label from raw raise/lower counts.

    Computes net = raises - lowers then maps to label:
      net >= 2  → MULTIPLE_RAISES
      net == 1  → SINGLE_RAISE
      net == 0  → NO_CHANGE
      net == -1 → SINGLE_CUT
      net <= -2 → MULTIPLE_CUTS
    """
    net = raises - lowers
    if net >= 2:
        return "MULTIPLE_RAISES"
    if net == 1:
        return "SINGLE_RAISE"
    if net == 0:
        return "NO_CHANGE"
    if net == -1:
        return "SINGLE_CUT"
    return "MULTIPLE_CUTS"


def _pt_revision_modifier(direction: str) -> int:
    """Priority 3 — PT revision direction → modifier.

    MULTIPLE_RAISES → +5 | SINGLE_RAISE → +3 | NO_CHANGE → 0
    SINGLE_CUT → -5 | MULTIPLE_CUTS → -10
    """
    d = direction.strip().upper()
    if d == "MULTIPLE_RAISES":
        return 5
    if d == "SINGLE_RAISE":
        return 3
    if d == "NO_CHANGE":
        return 0
    if d == "SINGLE_CUT":
        return -5
    return -10


def _upgrade_downgrade_modifier(net_upgrades: int) -> int:
    """Priority 4 — net rating upgrades/downgrades (last 30d) → modifier.

    > 2 → +5 | 1-2 → +3 | 0 → 0 | -1 to -2 → -5 | < -2 → -10
    """
    if net_upgrades > 2:
        return 5
    if net_upgrades >= 1:
        return 3
    if net_upgrades == 0:
        return 0
    if net_upgrades >= -2:
        return -5
    return -10


def _price_vs_target(current_price: float, analyst_target: float) -> float:
    """Priority 5 — compute price vs target ratio.

    price_vs_target = round((current_price - analyst_target) / analyst_target, 4)
    Positive = stock above target. Negative = stock below target.
    """
    if analyst_target == 0:
        return 0.0
    return round((current_price - analyst_target) / analyst_target, 4)


def _price_vs_target_band(pvt: float) -> str:
    """Return the display band label for the given pvt ratio."""
    if pvt < -0.20:
        return _BAND_BELOW_20
    if pvt < -0.10:
        return _BAND_BELOW_10
    if pvt <= 0.10:
        return _BAND_NEUTRAL
    if pvt <= 0.20:
        return _BAND_ABOVE_10
    return _BAND_ABOVE_20


def _grade_from_total(total: int) -> str:
    """Map F3 score to grade label (unchanged from v7.3.3)."""
    if total >= _GRADE_STRONG_BUY:
        return "STRONG BUY"
    if total >= _GRADE_BUY:
        return "BUY"
    if total >= _GRADE_NEUTRAL:
        return "NEUTRAL"
    if total >= _GRADE_WEAK:
        return "WEAK"
    return "AVOID"


def classify_consensus(
    strong_buy_count: int,
    buy_count: int,
    hold_count: int,
    sell_count: int,
    strong_sell_count: int,
) -> tuple[str, int]:
    """Classify consensus using a weighted average of the full SB/B/H/S/SS distribution.

    Weights: Strong Buy=5, Buy=4, Hold=3, Sell=2, Strong Sell=1.

    weighted_avg thresholds → (label, base_score):
      >= 4.5 → STRONG BUY / 90
      >= 3.5 → BUY / 78
      >= 2.5 → HOLD / 55
      <  2.5 → SELL / 30
      total == 0 → NO COVERAGE / 55 (neutral fallback)
    """
    total = strong_buy_count + buy_count + hold_count + sell_count + strong_sell_count
    if total == 0:
        return "NO COVERAGE", _BASE_HOLD
    weighted = (
        strong_buy_count * 5
        + buy_count * 4
        + hold_count * 3
        + sell_count * 2
        + strong_sell_count * 1
    ) / total
    if weighted >= 4.5:
        return "STRONG BUY", _BASE_STRONG_BUY
    if weighted >= 3.5:
        return "BUY", _BASE_BUY
    if weighted >= 2.5:
        return "HOLD", _BASE_HOLD
    return "SELL", _BASE_SELL


def _upside_color(pvt: float) -> str:
    """Map price-vs-target ratio to a semantic colour token.

    pvt < -0.20  → GREEN       (20%+ below target — significant upside)
    pvt < -0.10  → LIGHT_GREEN (10-20% below target)
    pvt <= +0.10 → NEUTRAL     (within ±10% — neutral zone)
    pvt <= +0.20 → AMBER       (10-20% above target — caution)
    pvt >  +0.20 → RED         (20%+ above target — overextended)
    """
    if pvt < -0.20:
        return "GREEN"
    if pvt < -0.10:
        return "LIGHT_GREEN"
    if pvt <= 0.10:
        return "NEUTRAL"
    if pvt <= 0.20:
        return "AMBER"
    return "RED"


def _weighted_consensus_avg(
    strong_buy: int, buy: int, hold: int, sell: int, strong_sell: int
) -> float:
    """Weighted average consensus (SB=5, B=4, H=3, S=2, SS=1). 0.0 when no analysts."""
    total = strong_buy + buy + hold + sell + strong_sell
    if total == 0:
        return 0.0
    return (strong_buy * 5 + buy * 4 + hold * 3 + sell * 2 + strong_sell * 1) / total


def _recency_weight(days_ago: int) -> float:
    """Recency weight for upgrade/downgrade events (Change 2).

    0-30d → 1.0 | 31-60d → 0.5 | 61-90d → 0.25 | >90d → 0.0
    """
    if days_ago <= 30:
        return _UD_WEIGHT_RECENT
    if days_ago <= 60:
        return _UD_WEIGHT_MID
    if days_ago <= 90:
        return _UD_WEIGHT_OLD
    return 0.0


def _weighted_upgrade_modifier(weighted_net: float) -> int:
    """Map recency-weighted net upgrades to score modifier.

    > 2.0 → +5 | >= 1.0 → +3 | > -1.0 → 0 | >= -2.0 → -5 | < -2.0 → -10
    """
    if weighted_net > 2.0:
        return 5
    if weighted_net >= 1.0:
        return 3
    if weighted_net > -1.0:
        return 0
    if weighted_net >= -2.0:
        return -5
    return -10


# ---------------------------------------------------------------------------
# score_f3 — public pure function (v7.3.5 — 4-bucket + recency modifier)
# ---------------------------------------------------------------------------


def score_f3(
    formula_pt: float | None,
    current_price: float | None,
    pt_revision_direction: str,
    num_analysts: int,
    consensus_weighted_avg: float,
    weighted_net_upgrades: float,
) -> FactorScore:
    """Compute the v7.3.5 F3 Analyst Conviction score.

    Parameters
    ----------
    formula_pt:
        Analyst price target driving the bucket determination (highest or
        consensus PT).  None when no price target is available.
    current_price:
        Most recent closing price (USD).  None when unavailable.
    pt_revision_direction:
        PT revision direction label over the last 30 days: "MULTIPLE_RAISES",
        "SINGLE_RAISE", "NO_CHANGE", "SINGLE_CUT", or "MULTIPLE_CUTS".
    num_analysts:
        Total number of analysts covering the stock.
    consensus_weighted_avg:
        Weighted-average consensus score (SB=5, B=4, H=3, S=2, SS=1).
    weighted_net_upgrades:
        Recency-weighted net rating upgrades over 90 days (0-30d 1.0x,
        31-60d 0.5x, 61-90d 0.25x).

    Returns
    -------
    FactorScore
        raw_score clamped to [0, 100], weight=0.15, full breakdown dict.
        override_applied is always False (override mechanism removed in v7.3.5).
    """
    # Bucket selection (Change 1) — evaluated in strict priority order.
    # Bucket 1: PT above current price → clear upside.
    if formula_pt is not None and current_price is not None and formula_pt > current_price:
        bucket = _F3_BUCKET_PT_ABOVE
        bucket_reason = "pt_above_price"
    # Bucket 2: positive revision direction in last 30 days (checked before bucket 3).
    elif pt_revision_direction.strip().upper() in ("MULTIPLE_RAISES", "SINGLE_RAISE"):
        bucket = _F3_BUCKET_POS_REVISION
        bucket_reason = "positive_revision_direction"
    # Bucket 3: strong analyst coverage + high consensus.
    elif (
        num_analysts >= _F3_BUCKET3_MIN_ANALYSTS
        and consensus_weighted_avg >= _F3_BUCKET3_MIN_CONSENSUS_AVG
    ):
        bucket = _F3_BUCKET_STRONG_COV
        bucket_reason = "strong_coverage_and_consensus"
    # Bucket 4: neither of the above.
    else:
        bucket = _F3_BUCKET_NEITHER
        bucket_reason = "neither"

    # Recency-weighted upgrade/downgrade modifier (Change 2).
    ud_mod = _weighted_upgrade_modifier(weighted_net_upgrades)

    f3_raw = max(0, min(100, bucket + ud_mod))

    return FactorScore(
        raw_score=float(f3_raw),
        weight=_W_F3,
        weighted_contribution=f3_raw * _W_F3,
        breakdown={
            "bucket_score": bucket,
            "bucket_reason": bucket_reason,
            "weighted_net_upgrades_90d": weighted_net_upgrades,
            "upgrade_modifier": ud_mod,
        },
        override_applied=False,
        override_reason=None,
    )


# ---------------------------------------------------------------------------
# Assembly function — called by AnalystService.compute_analyst
# ---------------------------------------------------------------------------


def _build_analyst_response(
    ticker: str,
    strong_buy: int,
    buy: int,
    hold: int,
    sell: int,
    strong_sell: int,
    num_analysts: int | None,
    consensus_pt: float | None,
    current_price: float | None,
    has_coverage: bool,
    ratings_data: dict[str, int | float] | None,
    *,
    highest_pt: float | None = None,
) -> AnalystResponse:
    """Assemble an AnalystResponse from raw fetched values using v7.3.5 scoring.

    ``highest_pt`` (Yahoo Finance ``targetHighPrice``) is the primary driver of the
    bucket-1 PT-above-price check.  ``consensus_pt`` (mean target) is retained
    for display only.  When ``highest_pt`` is None the formula falls back to
    ``consensus_pt``.
    """
    total_analysts = strong_buy + buy + hold + sell + strong_sell
    effective_count = (
        (num_analysts if num_analysts is not None else total_analysts) if has_coverage else 0
    )

    # The PT used in the formula: highest_pt preferred, falls back to consensus_pt.
    formula_pt: float | None = highest_pt if highest_pt is not None else consensus_pt

    # Buy percentage for consensus label derivation
    buy_pct: float | None = None
    if has_coverage and total_analysts > 0:
        buy_pct = (strong_buy + buy) / total_analysts * 100.0

    # Upside — computed against formula_pt for display consistency with the formula.
    upside_pct: float | None = None
    if current_price and formula_pt and current_price > 0 and formula_pt > 0:
        upside_pct = (formula_pt - current_price) / current_price * 100.0

    # PT revision data — integer fields cast explicitly to satisfy mypy (dict type is int | float).
    pt_raises = int(ratings_data["raises"]) if ratings_data is not None else 0
    pt_lowers = int(ratings_data["lowers"]) if ratings_data is not None else 0
    raw_net_upgrades = int(ratings_data["net_upgrades"]) if ratings_data is not None else 0
    direction_label = (
        _pt_revision_direction_label(pt_raises, pt_lowers)
        if ratings_data is not None
        else "NO_DATA"
    )

    # Compute F3 score when we have analyst coverage (v7.3.5 — single path).
    f3_score: int | None = None
    f3_before: int | None = None
    override_applied = False
    override_reason: str | None = None
    weighted_net_upg: float = 0.0

    if has_coverage:
        consensus_weighted_avg_val = _weighted_consensus_avg(
            strong_buy, buy, hold, sell, strong_sell
        )
        weighted_net_upg = (
            float(ratings_data.get("weighted_net_upgrades", float(raw_net_upgrades)))
            if ratings_data is not None
            else 0.0
        )
        fs = score_f3(
            formula_pt=formula_pt,
            current_price=current_price,
            pt_revision_direction=direction_label if direction_label != "NO_DATA" else "NO_CHANGE",
            num_analysts=effective_count,
            consensus_weighted_avg=consensus_weighted_avg_val,
            weighted_net_upgrades=weighted_net_upg,
        )
        f3_score = round(fs.raw_score)
        f3_before = fs.breakdown["bucket_score"]
        override_applied = fs.override_applied
        override_reason = fs.override_reason

    # Price-vs-target for display in pt_upside_indicator only (not used in scoring).
    pvt: float | None = None
    pvt_band: str | None = None
    if current_price and formula_pt and current_price > 0 and formula_pt > 0:
        pvt = _price_vs_target(current_price, formula_pt)
        pvt_band = _price_vs_target_band(pvt)

    # Build sub-indicators
    cr_label, cr_base = classify_consensus(strong_buy, buy, hold, sell, strong_sell)
    consensus_indicator = ConsensusRatingIndicator(
        strong_buy_count=strong_buy,
        buy_count=buy,
        hold_count=hold,
        sell_count=sell,
        strong_sell_count=strong_sell,
        total_analysts=total_analysts,
        buy_pct=buy_pct,
        label=cr_label,
        base_score=cr_base if has_coverage and total_analysts > 0 else None,
    )

    coverage_indicator = AnalystCoverageIndicator(
        num_analysts=effective_count,
        modifier=_analyst_count_modifier(effective_count) if has_coverage else None,
    )

    pt_direction_indicator = PtDirectionIndicator(
        raises_30d=pt_raises,
        lowers_30d=pt_lowers,
        direction_label=direction_label,
        modifier=_pt_revision_modifier(direction_label)
        if ratings_data is not None and direction_label != "NO_DATA"
        else None,
    )

    recent_upgrades_indicator = RecentUpgradesIndicator(
        upgrades_30d=max(0, raw_net_upgrades) if ratings_data is not None else 0,
        downgrades_30d=max(0, -raw_net_upgrades) if ratings_data is not None else 0,
        net_upgrades_30d=raw_net_upgrades,
        modifier=_weighted_upgrade_modifier(weighted_net_upg) if ratings_data is not None else None,
    )

    pt_upside_indicator = PtUpsideIndicator(
        current_price=current_price,
        highest_pt=highest_pt,
        consensus_pt=consensus_pt,
        upside_pct=upside_pct,
        price_vs_target=pvt,
        price_vs_target_band=pvt_band,
        adjustment=None,  # display-only field; no longer derived from scoring (v7.3.5)
        upside_color=_upside_color(pvt) if pvt is not None else None,
    )

    grade = _grade_from_total(f3_score) if f3_score is not None else "NO DATA"

    return AnalystResponse(
        ticker=ticker.upper(),
        consensus_rating=consensus_indicator,
        analyst_coverage=coverage_indicator,
        pt_direction=pt_direction_indicator,
        recent_upgrades=recent_upgrades_indicator,
        pt_upside=pt_upside_indicator,
        f3_before_price_adjustment=f3_before,
        override_applied=override_applied,
        override_reason=override_reason,
        f3_score=f3_score,
        f3_grade=grade,
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class AnalystService:
    """Fetches F3 data from Benzinga + Polygon and computes the F3 score."""

    def __init__(
        self,
        benzinga_api_key: str,
        polygon_api_key: str = "",
        alphavantage_api_key: str = "",
        fmp_api_key: str = "",
    ) -> None:
        self._benzinga_key = benzinga_api_key
        self._polygon_key = polygon_api_key
        self._av_key = alphavantage_api_key
        self._fmp_key = fmp_api_key

    @classmethod
    def from_env(cls) -> AnalystService:
        return cls(
            benzinga_api_key=os.environ.get("BENZINGA_API_KEY", ""),
            polygon_api_key=os.environ.get("POLYGON_API_KEY", ""),
            alphavantage_api_key=os.environ.get("ALPHAVANTAGE_API_KEY", ""),
            fmp_api_key=os.environ.get("EARNINGS_TRANSCRIPT_API_KEY", ""),
        )

    async def compute_analyst(
        self,
        ticker: str,
        *,
        overview_task: asyncio.Task[dict[str, Any]] | None = None,
    ) -> AnalystResponse:
        """Fetch data from Benzinga + Polygon + Yahoo Finance and return an AnalystResponse.

        Highest analyst PT (``targetHighPrice``) is fetched from yfinance concurrently
        with the other network calls and used as the primary input to the price-vs-target
        formula (Priority 5).  Consensus PT (mean) is kept for display only.
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            consensus_task = asyncio.create_task(self._fetch_consensus(client, ticker))
            ratings_task = asyncio.create_task(self._fetch_recent_ratings(client, ticker))
            price_task = asyncio.create_task(self._fetch_current_price(client, ticker))
            yf_pt_task = asyncio.create_task(self._fetch_yfinance_pt(ticker))

            consensus_data = await consensus_task
            if not consensus_data:
                consensus_data = await self._fetch_consensus_av(
                    client, ticker, overview_task=overview_task
                )
            if not consensus_data:
                consensus_data = await self._fetch_consensus_fmp(client, ticker)

            ratings_data = await ratings_task
            current_price = await price_task
            highest_pt = await yf_pt_task

        has_coverage = bool(consensus_data)
        strong_buy = consensus_data.get("strong_buy", 0)
        buy = consensus_data.get("buy", 0)
        hold = consensus_data.get("hold", 0)
        sell = consensus_data.get("sell", 0)
        strong_sell = consensus_data.get("strong_sell", 0)
        num_analysts: int | None = consensus_data.get("num_analysts")
        consensus_pt: float | None = consensus_data.get("consensus_pt")

        return _build_analyst_response(
            ticker=ticker,
            strong_buy=strong_buy,
            buy=buy,
            hold=hold,
            sell=sell,
            strong_sell=strong_sell,
            num_analysts=num_analysts,
            consensus_pt=consensus_pt,
            highest_pt=highest_pt,
            current_price=current_price,
            has_coverage=has_coverage,
            ratings_data=ratings_data,
        )

    # ------------------------------------------------------------------
    # Yahoo Finance — highest analyst price target
    # ------------------------------------------------------------------

    async def _fetch_yfinance_pt(self, ticker: str) -> float | None:
        """Return the highest individual analyst price target from Yahoo Finance.

        yfinance's ``targetHighPrice`` is the 12-month high end of the analyst PT
        range, sourced from Yahoo Finance quotes pages.  Runs the synchronous
        yfinance call in a thread-pool executor to avoid blocking the event loop.
        Returns None on any error or missing value.
        """
        loop = asyncio.get_running_loop()
        try:
            raw = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(ticker).info.get("targetHighPrice"),
            )
        except Exception:
            return None
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Benzinga — consensus ratings
    # ------------------------------------------------------------------

    async def _fetch_consensus(self, client: httpx.AsyncClient, ticker: str) -> dict[str, Any]:
        """Fetch consensus rating breakdown from Benzinga."""
        try:
            resp = await client.get(
                f"{_BENZINGA_BASE_URL}/api/v1/consensus-ratings",
                params={
                    "tickers": ticker.upper(),
                    "aggregate_type": "number",
                    "token": self._benzinga_key,
                },
            )
            resp.raise_for_status()
            raw = resp.json()

            if not isinstance(raw, dict):
                return {}
            payload: dict[str, Any] = raw

            agg: dict[str, Any] | None = payload.get("aggregate_ratings")
            if not agg:
                return {}

            def _get_count(keys: list[str]) -> int:
                for k in keys:
                    v = agg.get(k)
                    if v is not None:
                        try:
                            return int(v)
                        except (TypeError, ValueError):
                            pass
                return 0

            strong_buy = _get_count(["strong_buy", "strongBuy"])
            buy = _get_count(["buy"])
            hold = _get_count(["hold", "neutral"])
            sell = _get_count(["sell"])
            strong_sell = _get_count(["strong_sell", "strongSell"])

            raw_count = payload.get("unique_analyst_count") or payload.get("total_analyst_count")
            num_analysts: int | None = int(raw_count) if raw_count else None

            raw_pt = payload.get("consensus_price_target")
            consensus_pt: float | None = None
            with contextlib.suppress(TypeError, ValueError):
                if raw_pt:
                    consensus_pt = float(raw_pt)

            return {
                "strong_buy": strong_buy,
                "buy": buy,
                "hold": hold,
                "sell": sell,
                "strong_sell": strong_sell,
                "num_analysts": num_analysts,
                "consensus_pt": consensus_pt,
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Alpha Vantage — consensus fallback
    # ------------------------------------------------------------------

    async def _fetch_consensus_av(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        *,
        overview_task: asyncio.Task[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Fallback consensus from Alpha Vantage OVERVIEW."""
        if not self._av_key:
            return {}
        try:
            if overview_task is not None:
                payload: dict[str, Any] = await overview_task
            else:
                payload = await fetch_alpha_vantage_cached(
                    client,
                    api_key=self._av_key,
                    function="OVERVIEW",
                    symbol=ticker,
                )

            if not payload or "Note" in payload or "Information" in payload:
                return {}

            def _int(key: str) -> int:
                try:
                    return int(payload.get(key) or 0)
                except (TypeError, ValueError):
                    return 0

            strong_buy = _int("AnalystRatingStrongBuy")
            buy = _int("AnalystRatingBuy")
            hold = _int("AnalystRatingHold")
            sell = _int("AnalystRatingSell")
            strong_sell = _int("AnalystRatingStrongSell")
            total = strong_buy + buy + hold + sell + strong_sell
            if total == 0:
                return {}

            consensus_pt: float | None = None
            raw_pt = payload.get("AnalystTargetPrice")
            with contextlib.suppress(TypeError, ValueError):
                if raw_pt:
                    consensus_pt = float(raw_pt)

            return {
                "strong_buy": strong_buy,
                "buy": buy,
                "hold": hold,
                "sell": sell,
                "strong_sell": strong_sell,
                "num_analysts": total,
                "consensus_pt": consensus_pt,
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # FMP — consensus grades fallback
    # ------------------------------------------------------------------

    async def _fetch_consensus_fmp(self, client: httpx.AsyncClient, ticker: str) -> dict[str, Any]:
        """Fallback consensus from FMP."""
        if not self._fmp_key:
            return {}
        try:
            grades_resp, pt_resp = await asyncio.gather(
                client.get(
                    f"{_FMP_BASE_URL}/stable/grades-consensus",
                    params={"symbol": ticker.upper(), "apikey": self._fmp_key},
                ),
                client.get(
                    f"{_FMP_BASE_URL}/stable/price-target-consensus",
                    params={"symbol": ticker.upper(), "apikey": self._fmp_key},
                ),
            )
            grades_resp.raise_for_status()
            pt_resp.raise_for_status()

            grades_list: list[Any] = grades_resp.json()
            pt_list: list[Any] = pt_resp.json()

            if not grades_list or not isinstance(grades_list, list):
                return {}
            g: dict[str, Any] = grades_list[0]

            def _gi(key: str) -> int:
                try:
                    return int(g.get(key) or 0)
                except (TypeError, ValueError):
                    return 0

            strong_buy = _gi("strongBuy")
            buy = _gi("buy")
            hold = _gi("hold")
            sell = _gi("sell")
            strong_sell = _gi("strongSell")
            total = strong_buy + buy + hold + sell + strong_sell
            if total == 0:
                return {}

            consensus_pt: float | None = None
            if pt_list and isinstance(pt_list, list):
                raw_pt = pt_list[0].get("targetConsensus")
                with contextlib.suppress(TypeError, ValueError):
                    if raw_pt:
                        consensus_pt = float(raw_pt)
            return {
                "strong_buy": strong_buy,
                "buy": buy,
                "hold": hold,
                "sell": sell,
                "strong_sell": strong_sell,
                "num_analysts": total,
                "consensus_pt": consensus_pt,
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Benzinga — calendar ratings (PT revision direction + net upgrades)
    # ------------------------------------------------------------------

    async def _fetch_recent_ratings(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, int | float] | None:
        """Count PT raises/lowers (30d) and recency-weighted net upgrades (90d).

        PT raises/lowers use the 30-day window only — they drive the bucket 2
        PT revision direction signal.

        Upgrade/downgrade events are recency-weighted over 90 days:
          0-30d → 1.0x | 31-60d → 0.5x | 61-90d → 0.25x | >90d → 0

        action_pt values that count as raises: 'Raises', 'Announces'
        action_pt values that count as lowers: 'Lowers'
        action_company values that count as upgrades: 'Upgrades', 'Initiates Coverage On'
        action_company values that count as downgrades: 'Downgrades'

        Returns None on any fetch/parse failure.
        """
        try:
            today = date.today()
            date_from = (today - timedelta(days=_REVISION_DAYS_EXTENDED)).isoformat()
            date_to = today.isoformat()

            resp = await client.get(
                f"{_BENZINGA_BASE_URL}/api/v2.1/calendar/ratings",
                params={
                    "tickers": ticker.upper(),
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "token": self._benzinga_key,
                },
                headers={"accept": "application/json"},
            )
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()

            ratings: list[Any] = payload.get("ratings") or []
            raises = 0
            lowers = 0
            upgrades_30d = 0
            downgrades_30d = 0
            weighted_upgrades = 0.0
            weighted_downgrades = 0.0

            for r in ratings:
                if r.get("ticker", "").upper() != ticker.upper():
                    continue

                # Parse event date for recency weighting.
                raw_date: str = (r.get("date") or r.get("updated") or "").split("T")[0]
                days_ago: int = _REVISION_DAYS_EXTENDED + 1  # default: outside window
                try:
                    event_date = date.fromisoformat(raw_date)
                    days_ago = (today - event_date).days
                except ValueError:
                    pass

                # PT revision direction — 30d window only.
                if days_ago <= _REVISION_DAYS:
                    action_pt: str = (r.get("action_pt") or "").strip().lower()
                    if action_pt in ("raises", "announces"):
                        raises += 1
                    elif action_pt == "lowers":
                        lowers += 1

                # Upgrade/downgrade momentum — recency-weighted over 90d.
                weight = _recency_weight(days_ago)
                if weight > 0:
                    action_co: str = (r.get("action_company") or "").strip().lower()
                    if action_co in ("upgrades", "initiates coverage on"):
                        weighted_upgrades += weight
                        if days_ago <= _REVISION_DAYS:
                            upgrades_30d += 1
                    elif action_co == "downgrades":
                        weighted_downgrades += weight
                        if days_ago <= _REVISION_DAYS:
                            downgrades_30d += 1

            return {
                "raises": raises,
                "lowers": lowers,
                "net_upgrades": upgrades_30d - downgrades_30d,
                "weighted_net_upgrades": weighted_upgrades - weighted_downgrades,
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Polygon.io — current price
    # ------------------------------------------------------------------

    async def _fetch_current_price(self, client: httpx.AsyncClient, ticker: str) -> float | None:
        """Return the most recent closing price from Polygon snapshot.

        Prefers day.c. Falls back to prevDay.c when day.c is absent or zero.
        """
        if not self._polygon_key:
            return None
        try:
            resp = await client.get(
                f"{_POLYGON_BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}",
                params={"apiKey": self._polygon_key},
            )
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()
            ticker_data: dict[str, Any] = payload.get("ticker", {})
            day: dict[str, Any] = ticker_data.get("day", {})
            raw = day.get("c")
            if raw is not None and float(raw) > 0:
                return float(raw)
            prev_day: dict[str, Any] = ticker_data.get("prevDay", {})
            raw_prev = prev_day.get("c")
            return float(raw_prev) if raw_prev is not None and float(raw_prev) > 0 else None
        except Exception:
            return None
