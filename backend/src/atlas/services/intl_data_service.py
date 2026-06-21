"""INTL-3F data service — sources I1/I2/I3 from foreign-capable providers.

International / ADR / OTC operating companies are not served well by the
domestic factor feeds. This service wires the INTL-3F factors to providers that
DO cover them:

  * I2 Market / Momentum / Liquidity  ← Polygon daily aggregates. Polygon serves
    U.S.-listed foreign ordinaries (…F) and ADRs (…Y) traded OTC, so price,
    trend, and dollar-liquidity are available even when the domestic momentum
    service bails.
  * I1 Business / Forward Fundamentals ← Financial Modeling Prep (FMP) income
    statements (international coverage): revenue growth, profitability, margin.
  * I3 External Confirmation           ← FMP ratings snapshot (analyst rating).

Every axis degrades to ``available=False`` (NOT a low/bearish score) on any gap
so a missing feed never reads as a bad company — the caller surfaces that as a
coverage label / data-task, per the INTL-3F handoff.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import fmean
from typing import Any, Final

import httpx

from atlas.services.provider_response_cache import fetch_polygon_daily_bars_cached

_FMP_BASE: Final[str] = "https://financialmodelingprep.com/stable"
_FMP_INCOME_URL: Final[str] = f"{_FMP_BASE}/income-statement"
_FMP_RATINGS_URL: Final[str] = f"{_FMP_BASE}/ratings-snapshot"
_BARS_LOOKBACK_DAYS: Final[int] = 400
_INTL_MIN_BARS: Final[int] = 30
_TIMEOUT: Final[float] = 15.0

_RATING_LETTER_SCORE: Final[dict[str, int]] = {
    "S": 95, "A+": 90, "A": 85, "A-": 80,
    "B+": 72, "B": 66, "B-": 60,
    "C+": 52, "C": 46, "C-": 40,
    "D": 30, "F": 15,
}


def _clamp(score: float) -> int:
    return max(0, min(100, round(score)))


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Pure scoring helpers (no I/O)
# ---------------------------------------------------------------------------


def score_intl_market(bars: list[dict[str, Any]]) -> tuple[int | None, str]:
    """Score I2 (market / momentum / liquidity) from ascending daily bars.

    Returns ``(score, source)`` or ``(None, "DATA_GAP")`` when there is too
    little price history to judge. Pure function — no I/O.
    """
    closes = [c for c in (_to_float(b.get("c")) for b in bars) if c is not None]
    if len(closes) < _INTL_MIN_BARS:
        return None, "DATA_GAP"

    price = closes[-1]
    ma50 = fmean(closes[-50:]) if len(closes) >= 50 else fmean(closes)
    ma200 = fmean(closes[-200:]) if len(closes) >= 200 else fmean(closes)

    pts = 0.0
    if price >= ma50:
        pts += 18
    if price >= ma200:
        pts += 22

    base = closes[-61] if len(closes) >= 61 else closes[0]
    ret = (price - base) / base if base else 0.0
    if ret > 0.20:
        pts += 25
    elif ret > 0.05:
        pts += 18
    elif ret > -0.05:
        pts += 12
    elif ret > -0.20:
        pts += 6

    dollar_vols = [
        c * v
        for b in bars[-20:]
        if (c := _to_float(b.get("c"))) is not None and (v := _to_float(b.get("v"))) is not None
    ]
    advd = fmean(dollar_vols) if dollar_vols else 0.0
    if advd >= 2_000_000:
        pts += 35
    elif advd >= 500_000:
        pts += 28
    elif advd >= 100_000:
        pts += 18
    elif advd >= 20_000:
        pts += 10
    else:
        pts += 3

    return _clamp(pts), "polygon"


def score_intl_fundamentals(reports: list[Any]) -> tuple[int | None, str]:
    """Score I1 (business / forward fundamentals) from FMP income statements.

    ``reports`` is the FMP income-statement list (newest first). Returns
    ``(None, "DATA_GAP")`` when no usable revenue figure exists. Pure function.
    """
    rows = [
        r
        for r in reports
        if isinstance(r, dict) and _to_float(r.get("revenue")) not in (None, 0.0)
    ]
    if not rows:
        return None, "DATA_GAP"

    latest = rows[0]
    revenue = _to_float(latest.get("revenue")) or 0.0
    pts = 0.0

    prev_rev = _to_float(rows[1].get("revenue")) if len(rows) >= 2 else None
    if prev_rev:
        growth = (revenue - prev_rev) / prev_rev
        if growth > 0.25:
            pts += 35
        elif growth > 0.10:
            pts += 27
        elif growth > 0.0:
            pts += 18
        elif growth > -0.10:
            pts += 10
        else:
            pts += 3
    else:
        pts += 15  # single period — neutral, not penalised

    net_income = _to_float(latest.get("netIncome"))
    if net_income is not None and net_income > 0:
        pts += 30
    elif net_income is not None and net_income == 0:
        pts += 12
    else:
        pts += 6

    gross_profit = _to_float(latest.get("grossProfit"))
    if gross_profit is not None and revenue:
        margin = gross_profit / revenue
        if margin > 0.45:
            pts += 35
        elif margin > 0.30:
            pts += 27
        elif margin > 0.15:
            pts += 18
        elif margin > 0.0:
            pts += 10
        else:
            pts += 3
    else:
        pts += 15

    return _clamp(pts), "fmp-financials"


def score_intl_confirmation(payload: Any) -> tuple[int | None, str]:
    """Score I3 (external confirmation) from an FMP ratings snapshot.

    Accepts the FMP ratings-snapshot list or dict. Prefers a numeric
    ``overallScore`` (1-5), then a letter ``rating``. Pure function.
    """
    rec: Any = None
    if isinstance(payload, list) and payload:
        rec = payload[0]
    elif isinstance(payload, dict):
        rec = payload
    if not isinstance(rec, dict):
        return None, "DATA_GAP"

    numeric = _to_float(rec.get("overallScore")) or _to_float(rec.get("ratingScore"))
    if numeric is not None and numeric > 0:
        return _clamp(numeric / 5.0 * 100.0), "fmp-ratings"

    rating = str(rec.get("rating", "")).strip().upper()
    if rating in _RATING_LETTER_SCORE:
        return _RATING_LETTER_SCORE[rating], "fmp-ratings"
    return None, "DATA_GAP"


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntlFactorData:
    """One resolved INTL-3F factor (score + availability + provenance)."""

    score: int
    available: bool
    source: str


@dataclass(frozen=True)
class IntlData:
    """Resolved I1/I2/I3 for an international name from foreign-capable feeds."""

    i1: IntlFactorData
    i2: IntlFactorData
    i3: IntlFactorData


def _factor_from(scored: tuple[int | None, str]) -> IntlFactorData:
    score, source = scored
    if score is None:
        return IntlFactorData(score=50, available=False, source="DATA_GAP")
    return IntlFactorData(score=score, available=True, source=source)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class IntlDataService:
    """Fetches and scores INTL-3F factors from Polygon (I2) + FMP (I1/I3)."""

    def __init__(self, polygon_api_key: str, fmp_api_key: str = "") -> None:
        self._polygon_key = polygon_api_key
        self._fmp_key = fmp_api_key

    async def compute_intl(self, client: httpx.AsyncClient, ticker: str) -> IntlData:
        """Resolve I1/I2/I3 for *ticker*. Each axis degrades to unavailable."""
        bars, income, ratings = await asyncio.gather(
            self._fetch_bars(client, ticker),
            self._fetch_income(client, ticker),
            self._fetch_ratings(client, ticker),
        )
        return IntlData(
            i1=_factor_from(score_intl_fundamentals(income)),
            i2=_factor_from(score_intl_market(bars)),
            i3=_factor_from(score_intl_confirmation(ratings)),
        )

    async def _fetch_bars(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[dict[str, Any]]:
        to_date = date.today()
        from_date = to_date - timedelta(days=_BARS_LOOKBACK_DAYS)
        return await fetch_polygon_daily_bars_cached(
            client,
            ticker=ticker,
            api_key=self._polygon_key,
            from_date=from_date,
            to_date=to_date,
        )

    async def _fetch_income(self, client: httpx.AsyncClient, ticker: str) -> list[Any]:
        if not self._fmp_key:
            return []
        try:
            resp = await client.get(
                _FMP_INCOME_URL,
                params={"symbol": ticker, "limit": 5, "apikey": self._fmp_key},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError, TypeError):
            return []
        return payload if isinstance(payload, list) else []

    async def _fetch_ratings(self, client: httpx.AsyncClient, ticker: str) -> Any:
        if not self._fmp_key:
            return None
        try:
            resp = await client.get(
                _FMP_RATINGS_URL,
                params={"symbol": ticker, "apikey": self._fmp_key},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError, TypeError):
            return None
