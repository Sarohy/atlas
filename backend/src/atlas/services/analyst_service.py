"""F3 Analyst Conviction service.

Data sources:
  - Benzinga        → consensus ratings, analyst count, consensus PT, PT revision direction
  - Alpha Vantage   → fallback consensus when Benzinga has no coverage (OVERVIEW endpoint)
  - FMP             → second fallback consensus when both Benzinga and AV have no data
  - Polygon.io      → current stock price

F3 sub-indicators and weights (Factor_Mapping_Guide):
  1. Consensus Rating     (35%) — (Strong Buy + Buy) % of total analysts
  2. Analyst Count        (10%) — unique analysts covering the stock
  3. PT vs Current Price  (30%) — % upside from current price to consensus PT
  4. PT Revision Direction(25%) — PT raises / lowers from Benzinga in last 30 days

F3 = (score1 × 0.35) + (score2 × 0.10) + (score3 × 0.30) + (score4 × 0.25)

LITE worked example (from guide):
  Consensus 80 × 0.35 = 28.0
  Coverage  85 × 0.10 =  8.5   (10-20 analysts)
  PT Upside 85 × 0.30 = 25.5   (15-30% above current)
  PT Revision 100 × 0.25 = 25.0 (multiple raises)
  F3 = 87 → rounds to 88 per guide (Mizuho top pick, multiple PT raises)
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from typing import Any, Final

import httpx

from atlas.schemas.analyst import (
    AnalystCoverageIndicator,
    AnalystResponse,
    ConsensusRatingIndicator,
    PtRevisionIndicator,
    PtUpsideIndicator,
)

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

_W_CONSENSUS: Final[float] = 0.35
_W_COVERAGE: Final[float] = 0.10
_W_PT_UPSIDE: Final[float] = 0.30
_W_PT_REVISION: Final[float] = 0.25

# ---------------------------------------------------------------------------
# Grade thresholds
# ---------------------------------------------------------------------------

_GRADE_STRONG_BUY: Final[int] = 80
_GRADE_BUY: Final[int] = 60
_GRADE_NEUTRAL: Final[int] = 40
_GRADE_WEAK: Final[int] = 20

# PT Ratio cap — when current_price / consensus_PT > 1.40, the stock is
# trading more than 40% above analyst targets; F3 is capped at 55 (NEUTRAL).
_PT_RATIO_CAP_THRESHOLD: Final[float] = 1.40
_PT_RATIO_F3_CAP: Final[int] = 55

# ---------------------------------------------------------------------------
# API constants
# ---------------------------------------------------------------------------

_BENZINGA_BASE_URL: Final[str] = "https://api.benzinga.com"
_POLYGON_BASE_URL: Final[str] = "https://api.polygon.io"
_FMP_BASE_URL: Final[str] = "https://financialmodelingprep.com"
_TIMEOUT: Final[float] = 10.0

# PT revision look-back window in days
_REVISION_DAYS: Final[int] = 30

# ---------------------------------------------------------------------------
# Scoring functions — each returns 0-100
# ---------------------------------------------------------------------------


def _score_consensus(buy_pct: float | None) -> int | None:
    """Consensus Rating score (0-100). Returns None when no data available."""
    if buy_pct is None:
        return None
    if buy_pct > 80:
        return 100
    if buy_pct >= 60:
        return 80
    if buy_pct >= 40:
        return 55
    return 20


def _score_analyst_coverage(count: int | None) -> int | None:
    """Analyst Count score (0-100). Returns None when no coverage data available."""
    if count is None or count == 0:
        return None
    if count > 20:
        return 100
    if count >= 10:
        return 85
    if count >= 5:
        return 65
    return 40  # <5 analysts: hard cap at 40


def _score_pt_upside(upside_pct: float | None) -> int | None:
    """PT vs Current Price score (0-100). Returns None when price/PT data unavailable."""
    if upside_pct is None:
        return None
    if upside_pct > 30:
        return 100
    if upside_pct >= 15:
        return 85
    if upside_pct >= 5:
        return 70
    if upside_pct >= 0:
        return 55
    return 20


def _score_pt_revision(raises: int, lowers: int) -> int:
    """PT Revision Direction score (0-100).

    Guide: Multiple upgrades last 30d → 100 | 1 upgrade → 80
           No change → 60 | Downgrade → 20
    'Raises' and 'Announces' from Benzinga action_pt count as raises.
    'Lowers' counts as a downgrade.
    """
    if raises >= 2:
        return 100
    if raises == 1:
        return 80
    if lowers == 0:
        return 60  # no change / maintains
    return 20  # any downgrade


def _revision_label(raises: int, lowers: int) -> str:
    if raises >= 2:
        return "MULTIPLE RAISES"
    if raises == 1:
        return "1 RAISE"
    if lowers == 0:
        return "NO CHANGE"
    return "LOWERED"


def _grade_from_total(total: int) -> str:
    if total >= _GRADE_STRONG_BUY:
        return "STRONG BUY"
    if total >= _GRADE_BUY:
        return "BUY"
    if total >= _GRADE_NEUTRAL:
        return "NEUTRAL"
    if total >= _GRADE_WEAK:
        return "WEAK"
    return "AVOID"


# ---------------------------------------------------------------------------
# Consensus label helper
# ---------------------------------------------------------------------------


def _consensus_label(buy_pct: float | None) -> str:
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
# Assembly
# ---------------------------------------------------------------------------


def _compute_f3_total(
    consensus_raw: int | None,
    coverage_raw: int | None,
    upside_raw: int | None,
    revision_raw: int | None,
) -> int | None:
    """Compute weighted F3 total, rescaling when sub-factors have no data.

    Sub-factors with None scores are excluded and the remaining weights are
    rescaled proportionally so they sum to 1.0.  Returns None only when ALL
    four sub-factors have no data.
    """
    pairs = [
        (consensus_raw, _W_CONSENSUS),
        (coverage_raw, _W_COVERAGE),
        (upside_raw, _W_PT_UPSIDE),
        (revision_raw, _W_PT_REVISION),
    ]
    available = [(score, w) for score, w in pairs if score is not None]
    if not available:
        return None
    total_weight = sum(w for _, w in available)
    weighted = sum(score * (w / total_weight) for score, w in available)
    return round(weighted)


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
    """Assemble an AnalystResponse from raw fetched values."""
    total_analysts = strong_buy + buy + hold + sell + strong_sell
    effective_count: int | None = (num_analysts if num_analysts is not None else total_analysts) if has_coverage else None

    # Buy percentage = (Strong Buy + Buy) / total * 100
    buy_pct: float | None = None
    if has_coverage and total_analysts > 0:
        buy_pct = (strong_buy + buy) / total_analysts * 100.0

    # PT upside
    upside_pct: float | None = None
    pt_ratio: float | None = None
    if current_price and consensus_pt and current_price > 0:
        upside_pct = (consensus_pt - current_price) / current_price * 100.0
        pt_ratio = current_price / consensus_pt  # >1.0 means stock exceeds PT

    # Individual scores — None when data unavailable (no fallback points)
    consensus_score = _score_consensus(buy_pct)
    coverage_score = _score_analyst_coverage(effective_count)
    upside_score = _score_pt_upside(upside_pct)
    revision_score: int | None
    if ratings_data is None:
        revision_score = None
    else:
        revision_score = _score_pt_revision(ratings_data["raises"], ratings_data["lowers"])

    # Weighted F3 — excludes None sub-factors and rescales remaining weights
    f3_score = _compute_f3_total(consensus_score, coverage_score, upside_score, revision_score)

    # PT Ratio cap — when stock price exceeds consensus PT by >40%, F3 is
    # capped at 55 (NEUTRAL) regardless of the weighted composite.
    if f3_score is not None and pt_ratio is not None and pt_ratio > _PT_RATIO_CAP_THRESHOLD:
        f3_score = min(f3_score, _PT_RATIO_F3_CAP)

    pt_raises = ratings_data["raises"] if ratings_data is not None else 0
    pt_lowers = ratings_data["lowers"] if ratings_data is not None else 0
    revision_label = _revision_label(pt_raises, pt_lowers) if ratings_data is not None else "NO DATA"

    return AnalystResponse(
        ticker=ticker.upper(),
        consensus_rating=ConsensusRatingIndicator(
            strong_buy_count=strong_buy,
            buy_count=buy,
            hold_count=hold,
            sell_count=sell,
            strong_sell_count=strong_sell,
            total_analysts=total_analysts,
            buy_pct=buy_pct,
            label=_consensus_label(buy_pct),
            score=consensus_score,
            weight=_W_CONSENSUS,
        ),
        analyst_coverage=AnalystCoverageIndicator(
            num_analysts=effective_count if effective_count is not None else 0,
            score=coverage_score,
            weight=_W_COVERAGE,
        ),
        pt_upside=PtUpsideIndicator(
            current_price=current_price,
            consensus_pt=consensus_pt,
            upside_pct=upside_pct,
            pt_ratio=round(pt_ratio, 4) if pt_ratio is not None else None,
            score=upside_score,
            weight=_W_PT_UPSIDE,
        ),
        pt_revision=PtRevisionIndicator(
            raises_30d=pt_raises,
            lowers_30d=pt_lowers,
            revision_label=revision_label,
            score=revision_score,
            weight=_W_PT_REVISION,
        ),
        f3_score=f3_score,
        f3_grade=_grade_from_total(f3_score) if f3_score is not None else "NO DATA",
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
            # Benzinga returns null aggregate_ratings for tickers it doesn't index
            # (typically smaller-cap stocks). Fall back to Alpha Vantage OVERVIEW.
            if not consensus_data:
                consensus_data = await self._fetch_consensus_av(
                    client, ticker, overview_task=overview_task
                )
            # If AV also has no data, try FMP grades-consensus as a second fallback.
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

    async def _fetch_consensus(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        """Fetch consensus rating breakdown from Benzinga.

        Endpoint: GET /api/v1/consensus-ratings
        Params: tickers, aggregate_type=number, token
        """
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

            # Benzinga returns a flat dict for covered tickers:
            #   aggregate_ratings: {strong_buy, buy, hold, sell} | null
            #   consensus_price_target: float
            #   unique_analyst_count: int
            # For tickers with no coverage it returns [] (an empty list).
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

            # unique_analyst_count is more accurate than total_analyst_count
            raw_count = payload.get("unique_analyst_count") or payload.get("total_analyst_count")
            num_analysts: int | None = int(raw_count) if raw_count else None

            # Consensus price target lives at the top level of the payload
            raw_pt = payload.get("consensus_price_target")
            consensus_pt: float | None = None
            if raw_pt:
                try:
                    consensus_pt = float(raw_pt)
                except (TypeError, ValueError):
                    pass

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
    # Alpha Vantage — consensus fallback (OVERVIEW endpoint)
    # ------------------------------------------------------------------

    async def _fetch_consensus_av(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        *,
        overview_task: asyncio.Task[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Fallback consensus from Alpha Vantage OVERVIEW when Benzinga has no coverage.

        Relevant fields returned by AV:
          AnalystRatingStrongBuy, AnalystRatingBuy, AnalystRatingHold,
          AnalystRatingSell, AnalystRatingStrongSell, AnalystTargetPrice
        Analyst count is derived by summing the rating counts.

        Note: AV does not provide PT revision direction — that sub-factor
        stays at its default (NO CHANGE / 60) when this fallback is used.
        """
        if not self._av_key:
            return {}
        try:
            # Use the pre-fetched shared task when available (avoids a
            # duplicate OVERVIEW call that FundamentalService also makes).
            if overview_task is not None:
                payload: dict[str, Any] = await overview_task
            else:
                resp = await client.get(
                    "https://www.alphavantage.co/query",
                    params={"function": "OVERVIEW", "symbol": ticker.upper(), "apikey": self._av_key},
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
            if raw_pt:
                try:
                    consensus_pt = float(raw_pt)
                except (TypeError, ValueError):
                    pass

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

    async def _fetch_consensus_fmp(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        """Fallback consensus from FMP when both Benzinga and AV have no data.

        Endpoints used:
          GET /stable/grades-consensus  → strongBuy, buy, hold, sell, strongSell
          GET /stable/price-target-consensus → targetConsensus
        """
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
                if raw_pt:
                    try:
                        consensus_pt = float(raw_pt)
                    except (TypeError, ValueError):
                        pass

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
    # Benzinga — calendar ratings (PT revision direction, last 30 days)
    # ------------------------------------------------------------------

    async def _fetch_recent_ratings(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, int] | None:
        """Count PT raises and lowers from Benzinga calendar/ratings (last 30 days).

        action_pt values that count as raises: 'Raises', 'Announces'
        action_pt values that count as lowers: 'Lowers'
        'Maintains' → no change (ignored in counts)

        Returns None on any fetch/parse failure so the caller can distinguish
        between "no revisions in 30 days" and "data unavailable".
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
            for r in ratings:
                # Benzinga may ignore the tickers param and return unrelated tickers;
                # always guard by checking the ticker field explicitly.
                if r.get("ticker", "").upper() != ticker.upper():
                    continue
                action_pt: str = (r.get("action_pt") or "").strip().lower()
                if action_pt in ("raises", "announces"):
                    raises += 1
                elif action_pt == "lowers":
                    lowers += 1

            return {"raises": raises, "lowers": lowers}
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Polygon.io — current price
    # ------------------------------------------------------------------

    async def _fetch_current_price(
        self, client: httpx.AsyncClient, ticker: str
    ) -> float | None:
        """Return the most recent closing price from Polygon snapshot.

        Prefers ``day.c`` (today's close).  Falls back to ``prevDay.c`` when
        ``day.c`` is absent or zero — Polygon sets it to 0 before any trade
        executes on the current session (pre-market / closed market).  Using 0
        as the current price would make the ``if current_price`` truthiness
        guard fail and silently skip the PT-ratio cap.
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
            # day.c is 0 or absent — fall back to the previous session's close
            prev_day: dict[str, Any] = ticker_data.get("prevDay", {})
            raw_prev = prev_day.get("c")
            return float(raw_prev) if raw_prev is not None and float(raw_prev) > 0 else None
        except Exception:
            return None
