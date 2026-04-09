"""F3 Analyst Conviction service.

Pure computation functions (all deterministic, no I/O) plus the
``AnalystService`` class that fetches data from Polygon.io and produces
an ``AnalystResponse``.

F3 sub-indicators (0-20 pts each, total 0-100):
  1. Consensus Rating    — buy/hold/sell analyst breakdown
  2. PT Upside           — % upside from current price to consensus PT
  3. PT Direction        — whether the consensus PT is being raised or cut
  4. Analyst Coverage    — number of analysts covering the stock
  5. Recent Upgrades     — net upgrade/downgrade balance over 90 days
"""

from __future__ import annotations

import os
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
# Named scoring thresholds
# ---------------------------------------------------------------------------

# Consensus rating thresholds (% of analysts with a buy rating)
_CONSENSUS_STRONG_BUY_PCT: Final[float] = 70.0  # >=70 % → STRONG BUY / 20 pts
_CONSENSUS_BUY_PCT: Final[float] = 50.0  # >=50 % → BUY / 15 pts
_CONSENSUS_HOLD_PCT: Final[float] = 30.0  # >=30 % → HOLD / 10 pts
_CONSENSUS_UNDERPERFORM_PCT: Final[float] = 20.0  # >=20 % → UNDERPERFORM / 5 pts

# PT upside thresholds (% upside from current price to consensus PT)
_PT_UPSIDE_STRONG: Final[float] = 25.0  # >=25 % → 20 pts
_PT_UPSIDE_GOOD: Final[float] = 10.0  # >=10 % → 15 pts
_PT_UPSIDE_MODERATE: Final[float] = 5.0  # >=5 %  → 10 pts
# >=0 % but <5 % → 5 pts; negative → 0 pts

# PT direction thresholds (% change in consensus PT vs prior reading)
_PT_DIR_STRONG_UP: Final[float] = 5.0  # PT raised >=5 % → 20 pts
_PT_DIR_MILD_UP: Final[float] = 1.0  # PT raised >=1 % → 15 pts
_PT_DIR_MILD_DOWN: Final[float] = -1.0  # flat band (-1 % to +1 %) → 10 pts
_PT_DIR_STRONG_DOWN: Final[float] = -5.0  # PT cut >=5 % → 0 pts

# Analyst coverage thresholds (number of covering analysts)
_COVERAGE_STRONG: Final[int] = 20  # >=20 analysts → 20 pts
_COVERAGE_GOOD: Final[int] = 10  # >=10 analysts → 15 pts
_COVERAGE_MODERATE: Final[int] = 5  # >=5  analysts → 10 pts
_COVERAGE_MINIMAL: Final[int] = 2  # >=2  analysts → 5 pts; <2 → 0 pts

# Net-upgrades thresholds (upgrades - downgrades over last 90 days)
_UPGRADES_STRONG: Final[int] = 3  # net >=+3 → 20 pts
_UPGRADES_MILD: Final[int] = 1  # net >=+1 → 15 pts
# net ==  0 → 10 pts (neutral)
_DOWNGRADES_MILD: Final[int] = -2  # net >=-2 → 5 pts; net <-2 → 0 pts

# Grade thresholds
_GRADE_STRONG_BUY: Final[int] = 80
_GRADE_BUY: Final[int] = 60
_GRADE_NEUTRAL: Final[int] = 40
_GRADE_WEAK: Final[int] = 20

_MAX_SCORE_PER_INDICATOR: Final[int] = 20
_POLYGON_TIMEOUT_SECONDS: Final[float] = 10.0

# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------


def _compute_consensus_rating(buy: int, hold: int, sell: int) -> tuple[str, float | None]:
    """Compute consensus label and buy percentage from analyst counts.

    Args:
        buy:  Analysts with a buy / strong-buy rating.
        hold: Analysts with a hold / neutral rating.
        sell: Analysts with an underperform / sell rating.

    Returns:
        ``(label, buy_pct)`` where label is one of:
        ``"STRONG BUY" | "BUY" | "HOLD" | "UNDERPERFORM" | "SELL" | "NO DATA"``
        and ``buy_pct`` is the percentage of buy ratings (0-100), or ``None``
        when the total analyst count is zero.
    """
    total = buy + hold + sell
    if total == 0:
        return "NO DATA", None
    buy_pct = buy / total * 100.0
    if buy_pct >= _CONSENSUS_STRONG_BUY_PCT:
        return "STRONG BUY", buy_pct
    if buy_pct >= _CONSENSUS_BUY_PCT:
        return "BUY", buy_pct
    if buy_pct >= _CONSENSUS_HOLD_PCT:
        return "HOLD", buy_pct
    if buy_pct >= _CONSENSUS_UNDERPERFORM_PCT:
        return "UNDERPERFORM", buy_pct
    return "SELL", buy_pct


def _score_consensus(buy_pct: float | None) -> int:
    """Map analyst buy percentage to a 0-20 score.

    Args:
        buy_pct: Percentage of analysts with a buy rating (0-100), or ``None``.

    Returns:
        Integer score: 0, 5, 10, 15, or 20.
    """
    if buy_pct is None:
        return 0
    if buy_pct >= _CONSENSUS_STRONG_BUY_PCT:
        return 20
    if buy_pct >= _CONSENSUS_BUY_PCT:
        return 15
    if buy_pct >= _CONSENSUS_HOLD_PCT:
        return 10
    if buy_pct >= _CONSENSUS_UNDERPERFORM_PCT:
        return 5
    return 0


def _compute_pt_upside(current_price: float | None, consensus_pt: float | None) -> float | None:
    """Compute percentage upside from current price to consensus price target.

    Returns ``None`` when either argument is ``None`` or ``current_price`` is zero.
    """
    if current_price is None or consensus_pt is None:
        return None
    if current_price == 0.0:
        return None
    return (consensus_pt - current_price) / current_price * 100.0


def _score_pt_upside(upside_pct: float | None) -> int:
    """Map PT upside percentage to a 0-20 score.

    Args:
        upside_pct: Percentage upside (negative = downside), or ``None``.

    Returns:
        Integer score: 0, 5, 10, 15, or 20.
    """
    if upside_pct is None:
        return 0
    if upside_pct >= _PT_UPSIDE_STRONG:
        return 20
    if upside_pct >= _PT_UPSIDE_GOOD:
        return 15
    if upside_pct >= _PT_UPSIDE_MODERATE:
        return 10
    if upside_pct >= 0.0:
        return 5
    return 0


def _compute_pt_direction(current_pt: float | None, prior_pt: float | None) -> float | None:
    """Compute percentage change in consensus PT from prior to current reading.

    Returns:
        Positive value when the PT is being raised; negative when cut.
        ``None`` when either argument is ``None`` or ``prior_pt`` is zero.
    """
    if current_pt is None or prior_pt is None:
        return None
    if prior_pt == 0.0:
        return None
    return (current_pt - prior_pt) / prior_pt * 100.0


def _score_pt_direction(direction_pct: float | None) -> int:
    """Map PT direction percentage to a 0-20 score.

    ``None`` (no historical PT data available) returns 10 — neutral, since
    there is no evidence of a raise or a cut.
    """
    if direction_pct is None:
        return 10
    if direction_pct >= _PT_DIR_STRONG_UP:
        return 20
    if direction_pct >= _PT_DIR_MILD_UP:
        return 15
    if direction_pct >= _PT_DIR_MILD_DOWN:
        return 10
    if direction_pct >= _PT_DIR_STRONG_DOWN:
        return 5
    return 0


def _score_analyst_coverage(num_analysts: int | None) -> int:
    """Map analyst count to a 0-20 score.

    More analysts means a more reliable and liquid consensus signal.
    ``None`` returns 0 (no coverage data available).
    """
    if num_analysts is None:
        return 0
    if num_analysts >= _COVERAGE_STRONG:
        return 20
    if num_analysts >= _COVERAGE_GOOD:
        return 15
    if num_analysts >= _COVERAGE_MODERATE:
        return 10
    if num_analysts >= _COVERAGE_MINIMAL:
        return 5
    return 0


def _compute_net_upgrades(upgrades: int, downgrades: int) -> int:
    """Compute net upgrade balance (upgrades - downgrades) over a recent window."""
    return upgrades - downgrades


def _score_net_upgrades(net_upgrades: int | None) -> int:
    """Map net upgrade count to a 0-20 score.

    ``None`` (no recent rating-change data) returns 10 — neutral.
    """
    if net_upgrades is None:
        return 10
    if net_upgrades >= _UPGRADES_STRONG:
        return 20
    if net_upgrades >= _UPGRADES_MILD:
        return 15
    if net_upgrades >= 0:
        return 10
    if net_upgrades >= _DOWNGRADES_MILD:
        return 5
    return 0


def _grade_from_total(total: int) -> str:
    """Convert a numeric F3 total (0-100) into a grade string."""
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
# Assembly helper
# ---------------------------------------------------------------------------


def _build_analyst_response(
    ticker: str,
    buy: int,
    hold: int,
    sell: int,
    current_price: float | None,
    consensus_pt: float | None,
    prior_consensus_pt: float | None,
    num_analysts: int | None,
    upgrades: int,
    downgrades: int,
) -> AnalystResponse:
    """Assemble an ``AnalystResponse`` from raw indicator inputs."""
    label, buy_pct = _compute_consensus_rating(buy, hold, sell)
    upside = _compute_pt_upside(current_price, consensus_pt)
    direction = _compute_pt_direction(consensus_pt, prior_consensus_pt)
    net = _compute_net_upgrades(upgrades, downgrades)

    consensus_score = _score_consensus(buy_pct)
    upside_score = _score_pt_upside(upside)
    direction_score = _score_pt_direction(direction)
    coverage_score = _score_analyst_coverage(num_analysts)
    upgrades_score = _score_net_upgrades(net)

    total = consensus_score + upside_score + direction_score + coverage_score + upgrades_score
    grade = _grade_from_total(total)

    effective_analysts = num_analysts if num_analysts is not None else buy + hold + sell

    return AnalystResponse(
        ticker=ticker.upper(),
        consensus_rating=ConsensusRatingIndicator(
            buy_count=buy,
            hold_count=hold,
            sell_count=sell,
            total_analysts=buy + hold + sell,
            buy_pct=buy_pct,
            label=label,
            score=consensus_score,
            max_score=_MAX_SCORE_PER_INDICATOR,
        ),
        pt_upside=PtUpsideIndicator(
            current_price=current_price,
            consensus_pt=consensus_pt,
            upside_pct=upside,
            score=upside_score,
            max_score=_MAX_SCORE_PER_INDICATOR,
        ),
        pt_direction=PtDirectionIndicator(
            current_consensus_pt=consensus_pt,
            prior_consensus_pt=prior_consensus_pt,
            direction_pct=direction,
            score=direction_score,
            max_score=_MAX_SCORE_PER_INDICATOR,
        ),
        analyst_coverage=AnalystCoverageIndicator(
            num_analysts=effective_analysts,
            score=coverage_score,
            max_score=_MAX_SCORE_PER_INDICATOR,
        ),
        recent_upgrades=RecentUpgradesIndicator(
            upgrades=upgrades,
            downgrades=downgrades,
            net_upgrades=net,
            score=upgrades_score,
            max_score=_MAX_SCORE_PER_INDICATOR,
        ),
        f3_score=total,
        f3_grade=grade,
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class AnalystService:
    """Fetches analyst consensus data from Polygon.io and computes F3 scores."""

    _BASE_URL: Final[str] = "https://api.polygon.io"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_env(cls) -> AnalystService:
        """Construct the service from the ``POLYGON_API_KEY`` environment variable."""
        key = os.environ.get("POLYGON_API_KEY", "")
        return cls(api_key=key)

    async def compute_analyst(self, ticker: str) -> AnalystResponse:
        """Fetch analyst consensus data from Polygon and produce an ``AnalystResponse``."""
        async with httpx.AsyncClient(
            base_url=self._BASE_URL,
            timeout=_POLYGON_TIMEOUT_SECONDS,
            params={"apiKey": self._api_key},
        ) as client:
            current_price = await self._fetch_current_price(client, ticker)
            analyst_data = await self._fetch_analyst_data(client, ticker)

        buy = int(analyst_data.get("buy", 0))
        hold = int(analyst_data.get("hold", 0))
        sell = int(analyst_data.get("sell", 0))
        consensus_pt: float | None = analyst_data.get("consensus_pt")
        prior_pt: float | None = analyst_data.get("prior_consensus_pt")
        raw_num_analysts = analyst_data.get("num_analysts")
        num_analysts: int | None = int(raw_num_analysts) if raw_num_analysts is not None else None
        upgrades = int(analyst_data.get("upgrades", 0))
        downgrades = int(analyst_data.get("downgrades", 0))

        return _build_analyst_response(
            ticker=ticker,
            buy=buy,
            hold=hold,
            sell=sell,
            current_price=current_price,
            consensus_pt=consensus_pt,
            prior_consensus_pt=prior_pt,
            num_analysts=num_analysts,
            upgrades=upgrades,
            downgrades=downgrades,
        )

    async def _fetch_current_price(self, client: httpx.AsyncClient, ticker: str) -> float | None:
        """Return the most recent closing price for ``ticker`` from Polygon snapshots."""
        try:
            resp = await client.get(
                f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}"
            )
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()
            day: dict[str, Any] = payload.get("ticker", {}).get("day", {})
            raw = day.get("c")
            return float(raw) if raw is not None else None
        except Exception:
            return None

    async def _fetch_analyst_data(self, client: httpx.AsyncClient, ticker: str) -> dict[str, Any]:
        """Return a normalised analyst-data dict from Polygon.

        Tries Polygon's ticker snapshot for analyst fields.  Returns an empty
        dict (all indicators will fall back to defaults) if the endpoint is
        unavailable or the subscription tier does not include analyst data.
        """
        try:
            resp = await client.get(
                f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}"
            )
            resp.raise_for_status()
            payload: dict[str, Any] = resp.json()
            ticker_data: dict[str, Any] = payload.get("ticker", {})
            # Analyst fields are present on higher-tier Polygon subscriptions.
            analysts: dict[str, Any] = ticker_data.get("analysts", {})
            return {
                "buy": analysts.get("buy", 0),
                "hold": analysts.get("hold", 0),
                "sell": analysts.get("sell", 0),
                "consensus_pt": analysts.get("priceTarget"),
                "prior_consensus_pt": analysts.get("priorPriceTarget"),
                "num_analysts": analysts.get("numAnalysts"),
                "upgrades": analysts.get("upgrades", 0),
                "downgrades": analysts.get("downgrades", 0),
            }
        except Exception:
            return {}
