"""F3 Analyst Conviction service — v7.3.4 scoring algorithm.

Data sources:
  - Benzinga   → consensus ratings, analyst count, consensus PT, PT revision,
                 net upgrades/downgrades in last 30 days
  - Alpha Vantage → fallback consensus (OVERVIEW endpoint)
  - FMP        → second fallback consensus
  - Polygon.io → current stock price

F3 v7.3.4 scoring (base-score + modifier approach):
  Priority 1: Consensus label  → base score (Strong Buy 90 / Buy 78 / Hold 55 / Sell 30)
  Priority 2: Analyst count    → modifier (+8/+5/+3/0/-5)
  Priority 3: PT revision dir  → modifier (+5/+3/0/-5/-10)
  Priority 4: Net upgrades 30d → modifier (+5/+3/0/-5/-10)
  Priority 5: Price vs target  → adjustment (applied last)

High consensus override: Buy/SB + >=9 analysts + 0 sells + raised/maintained PT → min 78
Hard cap: pvt > +20% → f3_final = min(f3_before, 45)
Half penalty: pvt in (10%,20%] AND consensus NOT deteriorating → -7 instead of -15
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final

import httpx

from atlas.schemas.analyst import (
    AnalystCoverageIndicator,
    AnalystResponse,
    ConsensusRatingIndicator,
    PtDirectionIndicator,
    PtUpsideIndicator,
    RecentUpgradesIndicator,
)

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

# Hard cap applied when price is >20% above consensus target
_HARD_CAP_ABOVE_20: Final[int] = 45

# Full penalty when price is 10-20% above target
_ABOVE_10_FULL_PENALTY: Final[int] = -15

# Half penalty divisor — int(-15 / 2) = -7 (truncate toward zero)
_ABOVE_10_HALF_PENALTY: Final[int] = -7

# High consensus override minimum score
_HIGH_CONSENSUS_MIN: Final[int] = 78

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

# PT revision / upgrade look-back window in days
_REVISION_DAYS: Final[int] = 30

# Price vs target band labels
_BAND_BELOW_20: Final[str] = "20%+ below target (+10)"
_BAND_BELOW_10: Final[str] = "10-20% below target (+5)"
_BAND_NEUTRAL: Final[str] = "At target — neutral (0)"
_BAND_ABOVE_10: Final[str] = "10-20% above target (-15)"
_BAND_ABOVE_20: Final[str] = "20%+ above target (capped at 45)"


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
    """True when the high consensus override lifted the score to 78."""

    override_reason: str | None
    """Human-readable reason string when override_applied is True."""


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


def _is_deteriorating(*, net_upgrades: int, pt_direction: str) -> bool:
    """Return True when consensus is weakening (net downgrades OR PT cuts).

    Used to decide between full penalty (-15) and half penalty (-7) when
    price is 10-20% above the consensus target.
    """
    has_net_downgrades = net_upgrades < 0
    has_pt_cuts = pt_direction.strip().upper() in ("SINGLE_CUT", "MULTIPLE_CUTS")
    return has_net_downgrades or has_pt_cuts


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


def _consensus_label(buy_pct: float | None) -> str:
    """Map buy percentage to consensus label for display and scoring."""
    if buy_pct is None:
        return "NO DATA"
    if buy_pct > 80:
        return "STRONG BUY"
    if buy_pct >= 60:
        return "BUY"
    if buy_pct >= 40:
        return "HOLD"
    return "SELL"


# ---------------------------------------------------------------------------
# score_f3 — public pure function (Priority 1-5 + overrides)
# ---------------------------------------------------------------------------


def score_f3(
    consensus_rating: str,
    analyst_count: int,
    pt_revision_direction: str,
    net_upgrades_30d: int,
    current_price: float,
    analyst_target: float,
    sell_count: int,
) -> FactorScore:
    """Compute the v7.3.4 F3 Analyst Conviction score.

    Parameters
    ----------
    consensus_rating:
        Consensus label: "Strong Buy", "Buy", "Hold", or "Sell".
    analyst_count:
        Total number of analysts covering the stock.
    pt_revision_direction:
        PT direction label: "MULTIPLE_RAISES", "SINGLE_RAISE", "NO_CHANGE",
        "SINGLE_CUT", or "MULTIPLE_CUTS".
    net_upgrades_30d:
        Net rating upgrades minus downgrades in the last 30 days.
        Positive = net upgrades, negative = net downgrades.
    current_price:
        Most recent closing price (USD).
    analyst_target:
        Consensus 12-month price target (USD).
    sell_count:
        Number of analysts with a Sell or Strong Sell rating.

    Returns
    -------
    FactorScore
        raw_score clamped to [0, 100], weight=0.15, full breakdown dict,
        override_applied flag, override_reason string.
    """
    # Priority 1 — base score from consensus label
    base = _base_score_from_consensus(consensus_rating)

    # Priority 2 — analyst count modifier
    count_mod = _analyst_count_modifier(analyst_count)

    # Priority 3 — PT revision direction modifier
    pt_mod = _pt_revision_modifier(pt_revision_direction)

    # Priority 4 — net upgrades/downgrades modifier
    ud_mod = _upgrade_downgrade_modifier(net_upgrades_30d)

    f3_before = base + count_mod + pt_mod + ud_mod

    # Priority 5 — price vs target adjustment
    pvt = _price_vs_target(current_price, analyst_target)
    band_label = _price_vs_target_band(pvt)
    deteriorating = _is_deteriorating(
        net_upgrades=net_upgrades_30d,
        pt_direction=pt_revision_direction,
    )

    if pvt < -0.20:
        # 20%+ below target → +10
        adjustment = 10
        f3_after = f3_before + adjustment
    elif pvt < -0.10:
        # 10-20% below target → +5
        adjustment = 5
        f3_after = f3_before + adjustment
    elif pvt <= 0.10:
        # Neutral zone → 0
        adjustment = 0
        f3_after = f3_before
    elif pvt <= 0.20:
        # 10-20% above target
        # Part 4: full penalty only when BOTH above target AND consensus deteriorating.
        # If consensus is NOT deteriorating → half penalty (-7 instead of -15).
        adjustment = _ABOVE_10_FULL_PENALTY if deteriorating else _ABOVE_10_HALF_PENALTY
        f3_after = f3_before + adjustment
    else:
        # 20%+ above target → hard cap at 45
        f3_after = min(f3_before, _HARD_CAP_ABOVE_20)
        adjustment = f3_after - f3_before  # 0 or negative

    # Clamp to [0, 100] before override check
    f3_clamped = max(0, min(100, f3_after))

    # High consensus override — minimum 78 when ALL conditions met.
    # Exception: when price is >20% above target (the hard-cap band) the
    # hard cap takes priority and the override does NOT fire.  The spec's
    # "REGARDLESS of price vs target" covers the neutral zone and the
    # 10-20% above band, NOT the extreme >20% hard-cap case.
    in_hard_cap_band = pvt > 0.20

    is_buy_or_sb = consensus_rating.strip().upper() in ("BUY", "STRONG BUY")
    sufficient_coverage = analyst_count >= 9
    no_sells = sell_count == 0
    pt_maintained_or_raised = pt_revision_direction.strip().upper() in (
        "MULTIPLE_RAISES",
        "SINGLE_RAISE",
        "NO_CHANGE",
    )

    override_applied = False
    override_reason: str | None = None

    if (
        not in_hard_cap_band
        and is_buy_or_sb
        and sufficient_coverage
        and no_sells
        and pt_maintained_or_raised
        and f3_clamped < _HIGH_CONSENSUS_MIN
    ):
        f3_clamped = _HIGH_CONSENSUS_MIN
        override_applied = True
        override_reason = "High consensus minimum rule applied"

    breakdown: dict[str, Any] = {
        "base_score": base,
        "analyst_count_modifier": count_mod,
        "pt_revision_modifier": pt_mod,
        "upgrade_downgrade_modifier": ud_mod,
        "f3_before_price_adjustment": f3_before,
        "price_vs_target": pvt,
        "price_vs_target_band_label": band_label,
        "price_vs_target_adjustment": adjustment,
        "deteriorating": deteriorating,
    }

    return FactorScore(
        raw_score=float(f3_clamped),
        weight=_W_F3,
        weighted_contribution=f3_clamped * _W_F3,
        breakdown=breakdown,
        override_applied=override_applied,
        override_reason=override_reason,
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
    ratings_data: dict[str, int] | None,
) -> AnalystResponse:
    """Assemble an AnalystResponse from raw fetched values using v7.3.4 scoring."""
    total_analysts = strong_buy + buy + hold + sell + strong_sell
    effective_count = (
        (num_analysts if num_analysts is not None else total_analysts) if has_coverage else 0
    )

    # Buy percentage for consensus label derivation
    buy_pct: float | None = None
    if has_coverage and total_analysts > 0:
        buy_pct = (strong_buy + buy) / total_analysts * 100.0

    # Traditional upside (for display)
    upside_pct: float | None = None
    if current_price and consensus_pt and current_price > 0 and consensus_pt > 0:
        upside_pct = (consensus_pt - current_price) / current_price * 100.0

    # PT revision data
    pt_raises = ratings_data["raises"] if ratings_data is not None else 0
    pt_lowers = ratings_data["lowers"] if ratings_data is not None else 0
    raw_net_upgrades = ratings_data["net_upgrades"] if ratings_data is not None else 0
    direction_label = (
        _pt_revision_direction_label(pt_raises, pt_lowers)
        if ratings_data is not None
        else "NO_DATA"
    )

    # Compute F3 score when we have enough data
    f3_score: int | None = None
    f3_before: int | None = None
    pvt: float | None = None
    pvt_band: str | None = None
    pvt_adj: int | None = None
    override_applied = False
    override_reason: str | None = None

    if has_coverage and current_price and consensus_pt and current_price > 0 and consensus_pt > 0:
        sell_count = sell + strong_sell
        consensus_label = _consensus_label(buy_pct)
        # Use "HOLD" if no data / neutral label
        if consensus_label == "NO DATA":
            consensus_label = "HOLD"

        fs = score_f3(
            consensus_rating=consensus_label,
            analyst_count=effective_count,
            pt_revision_direction=direction_label if direction_label != "NO_DATA" else "NO_CHANGE",
            net_upgrades_30d=raw_net_upgrades,
            current_price=current_price,
            analyst_target=consensus_pt,
            sell_count=sell_count,
        )

        f3_score = round(fs.raw_score)
        f3_before = fs.breakdown["f3_before_price_adjustment"]
        pvt = fs.breakdown["price_vs_target"]
        pvt_band = fs.breakdown["price_vs_target_band_label"]
        pvt_adj = fs.breakdown["price_vs_target_adjustment"]
        override_applied = fs.override_applied
        override_reason = fs.override_reason
    elif has_coverage and (not current_price or not consensus_pt):
        # Coverage exists but no price data — score without price adjustment
        sell_count = sell + strong_sell
        consensus_label = _consensus_label(buy_pct)
        if consensus_label == "NO DATA":
            consensus_label = "HOLD"
        count = effective_count
        pt_mod = _pt_revision_modifier(
            direction_label if direction_label != "NO_DATA" else "NO_CHANGE"
        )
        ud_mod = _upgrade_downgrade_modifier(raw_net_upgrades)
        base = _base_score_from_consensus(consensus_label)
        count_mod = _analyst_count_modifier(count)
        raw = base + count_mod + pt_mod + ud_mod
        raw_clamped = max(0, min(100, raw))

        # No price data → skip pvt adjustment; still check override
        is_buy_or_sb = consensus_label.upper() in ("BUY", "STRONG BUY")
        no_sells = sell_count == 0
        sufficient_cov = count >= 9
        pt_ok = (direction_label if direction_label != "NO_DATA" else "NO_CHANGE").upper() in (
            "MULTIPLE_RAISES",
            "SINGLE_RAISE",
            "NO_CHANGE",
        )
        if (
            is_buy_or_sb
            and no_sells
            and sufficient_cov
            and pt_ok
            and raw_clamped < _HIGH_CONSENSUS_MIN
        ):
            raw_clamped = _HIGH_CONSENSUS_MIN
            override_applied = True
            override_reason = "High consensus minimum rule applied"

        f3_score = raw_clamped
        f3_before = raw
        pvt_adj = 0
        pvt_band = _BAND_NEUTRAL

    # Build sub-indicators
    consensus_indicator = ConsensusRatingIndicator(
        strong_buy_count=strong_buy,
        buy_count=buy,
        hold_count=hold,
        sell_count=sell,
        strong_sell_count=strong_sell,
        total_analysts=total_analysts,
        buy_pct=buy_pct,
        label=_consensus_label(buy_pct),
        base_score=_base_score_from_consensus(_consensus_label(buy_pct))
        if buy_pct is not None
        else None,
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
        modifier=_upgrade_downgrade_modifier(raw_net_upgrades)
        if ratings_data is not None
        else None,
    )

    pt_upside_indicator = PtUpsideIndicator(
        current_price=current_price,
        consensus_pt=consensus_pt,
        upside_pct=upside_pct,
        price_vs_target=pvt,
        price_vs_target_band=pvt_band,
        adjustment=pvt_adj,
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
        """Fetch data from Benzinga + Polygon and return an AnalystResponse."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            consensus_data = await self._fetch_consensus(client, ticker)
            if not consensus_data:
                consensus_data = await self._fetch_consensus_av(
                    client, ticker, overview_task=overview_task
                )
            if not consensus_data:
                consensus_data = await self._fetch_consensus_fmp(client, ticker)
            ratings_data = await self._fetch_recent_ratings(client, ticker)
            current_price = await self._fetch_current_price(client, ticker)

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
            current_price=current_price,
            has_coverage=has_coverage,
            ratings_data=ratings_data,
        )

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
                resp = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        "function": "OVERVIEW",
                        "symbol": ticker.upper(),
                        "apikey": self._av_key,
                    },
                )
                resp.raise_for_status()
                payload = resp.json()

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
    ) -> dict[str, int] | None:
        """Count PT raises/lowers and net rating upgrades from Benzinga (last 30 days).

        action_pt values that count as raises: 'Raises', 'Announces'
        action_pt values that count as lowers: 'Lowers'
        action_company values that count as upgrades: 'Upgrades', 'Initiates Coverage On'
        action_company values that count as downgrades: 'Downgrades'

        Returns None on any fetch/parse failure.
        """
        try:
            date_from = (date.today() - timedelta(days=_REVISION_DAYS)).isoformat()
            date_to = date.today().isoformat()

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
            upgrades = 0
            downgrades = 0

            for r in ratings:
                if r.get("ticker", "").upper() != ticker.upper():
                    continue

                action_pt: str = (r.get("action_pt") or "").strip().lower()
                if action_pt in ("raises", "announces"):
                    raises += 1
                elif action_pt == "lowers":
                    lowers += 1

                action_co: str = (r.get("action_company") or "").strip().lower()
                if action_co in ("upgrades", "initiates coverage on"):
                    upgrades += 1
                elif action_co == "downgrades":
                    downgrades += 1

            return {
                "raises": raises,
                "lowers": lowers,
                "net_upgrades": upgrades - downgrades,
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
