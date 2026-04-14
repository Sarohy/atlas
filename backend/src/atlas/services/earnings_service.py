"""F2 Earnings Quality scoring service.

Computes five earnings-quality indicators per the Factor_Mapping_Guide,
scores each 0-100, applies internal F2 weights, and produces a 0-100
composite F2 score.

Data sources:
  Alpha Vantage INCOME_STATEMENT  — quarterly totalRevenue + grossProfit
  Alpha Vantage EARNINGS          — quarterly reportedEPS vs estimatedEPS (last 3Q)
  FMP earning-call-transcript     — latest transcript for guidance + backlog NLP

F2 internal weights (Factor_Mapping_Guide §F2):
  Revenue Growth YoY      30%  → max 30 pts contribution
  EPS Beat History (3Q)   20%  → max 20 pts contribution
  Guidance Direction      20%  → max 20 pts contribution
  Gross Margin Trend      15%  → max 15 pts contribution
  Backlog / Visibility    15%  → max 15 pts contribution
  TOTAL                  100%  → max 100 pts

All calculation helpers are pure functions (no I/O, no side-effects) so they
can be tested in isolation without any network calls.  The ``EarningsService``
class owns all Alpha Vantage API access and calls the pure helpers once the
raw data has been fetched.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Final

import httpx

logger = logging.getLogger(__name__)

from atlas.schemas.earnings import (
    BacklogBtbIndicator,
    EarningsResponse,
    EpsBeatsIndicator,
    F2Grade,
    GuidanceIndicator,
    MarginTrajectoryIndicator,
    RevenueGrowthIndicator,
)

# ---------------------------------------------------------------------------
# Named constants — F2 internal weights
# ---------------------------------------------------------------------------

# Each input is scored 0-100 (raw_score); multiplied by its weight to give
# the contribution that sums to the composite F2 score (0-100).
_W_REVENUE: Final[float] = 0.30  # 30% — Revenue Growth YoY
_W_EPS_BEAT: Final[float] = 0.20  # 20% — EPS Beat History (rolling 3Q)
_W_GUIDANCE: Final[float] = 0.20  # 20% — Guidance Direction (transcript)
_W_MARGIN: Final[float] = 0.15  # 15% — Gross Margin Trend
_W_BACKLOG: Final[float] = 0.15  # 15% — Backlog / Visibility (transcript)

# Number of consecutive quarters to evaluate for EPS beat history.
_EPS_BEAT_QUARTERS: Final[int] = 3

# EPS beat count → raw score mapping (Factor_Mapping_Guide §F2).
_EPS_BEAT_SCORE: Final[dict[int, int]] = {3: 100, 2: 80, 1: 55, 0: 20}

# Rolling quarters of income-statement data to fetch (need 5 for 1 full YoY).
_INCOME_STMT_QUARTERS: Final[int] = 5

# F2 grade boundary thresholds (inclusive lower bound, Factor_Mapping_Guide §Final).
_GRADE_STRONG_BUY_MIN: Final[int] = 80
_GRADE_BUY_MIN: Final[int] = 65
_GRADE_NEUTRAL_MIN: Final[int] = 40
_GRADE_WEAK_MIN: Final[int] = 20

# ---------------------------------------------------------------------------
# Named constants — guidance label scores (Factor_Mapping_Guide §F2)
# ---------------------------------------------------------------------------

# Categorical guidance scores mapped from transcript analysis.
_GUIDANCE_SCORES: Final[dict[str, int]] = {
    "RAISE_FULL_YEAR": 100,  # management raised full-year guidance
    "MAINTAIN": 70,  # guidance maintained / reaffirmed
    "NARROW_RANGE": 55,  # guidance range narrowed
    "LOWER": 20,  # guidance cut / lowered
}

# Categorical backlog/visibility scores mapped from transcript analysis.
_BACKLOG_SCORES: Final[dict[str, int]] = {
    "EXPLICIT_MULTI_QUARTER": 100,  # explicit dollar amount + multi-quarter visibility
    "STRONG": 80,  # strong demand / pipeline commentary
    "LIMITED": 50,  # limited or uncertain visibility
    "NO_COMMENTARY": 30,  # no backlog or visibility mentioned
}

# ---------------------------------------------------------------------------
# Named constants — Alpha Vantage endpoints
# ---------------------------------------------------------------------------

_AV_BASE_URL: Final[str] = "https://www.alphavantage.co/query"

# Base URL for the FMP stable earnings-call-transcript endpoint.
# Docs: https://site.financialmodelingprep.com/developer/docs/stable/search-transcripts
# Pattern: GET /stable/earning-call-transcript?symbol={S}&year={Y}&quarter={Q}&apikey={K}
_FMP_TRANSCRIPT_URL: Final[str] = "https://financialmodelingprep.com/stable/earning-call-transcript"

# ---------------------------------------------------------------------------
# Named constants — transcript regex patterns (compiled once at import time)
# ---------------------------------------------------------------------------

# Guidance patterns ordered from strongest signal to weakest.
# Each tuple: (compiled_regex, label)
_GUIDANCE_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    # RAISE_FULL_YEAR — explicitly raising guidance
    (re.compile(r"rais\w*\s+(?:\S+\s+){0,4}full.?year\s+guidance", re.I), "RAISE_FULL_YEAR"),
    (re.compile(r"rais\w*\s+(?:\S+\s+){0,4}guidance", re.I), "RAISE_FULL_YEAR"),
    (re.compile(r"increas\w*\s+(?:\S+\s+){0,4}guidance", re.I), "RAISE_FULL_YEAR"),
    (re.compile(r"rais\w*\s+(?:\S+\s+){0,4}outlook", re.I), "RAISE_FULL_YEAR"),
    (re.compile(r"upward.{0,15}guidance", re.I), "RAISE_FULL_YEAR"),
    # RAISE_FULL_YEAR — first-time annual target issuance with explicit dollar figure
    # e.g. "we expect to generate over $1,000,000,000 in revenue this year"
    (re.compile(r"expect\w*\s+(?:\w+\s+){0,6}(?:over|more than|exceed|above)\s+\$[\d,]+", re.I), "RAISE_FULL_YEAR"),
    (re.compile(r"(?:full.?year|annual|fiscal.?year)\s+(?:\w+\s+){0,4}(?:revenue|target|outlook).{0,40}\$[\d,]+", re.I), "RAISE_FULL_YEAR"),
    (re.compile(r"expect\w*\s+(?:\w+\s+){0,6}(?:billion|million).{0,30}(?:this year|full.?year)", re.I), "RAISE_FULL_YEAR"),
    # LOWER — explicitly lowering guidance
    (re.compile(r"lower\w*\s+(?:\S+\s+){0,4}guidance", re.I), "LOWER"),
    (re.compile(r"reduc\w+\s+(?:\S+\s+){0,4}guidance", re.I), "LOWER"),
    (re.compile(r"cut\s+(?:\S+\s+){0,4}guidance", re.I), "LOWER"),
    (re.compile(r"lower\w*\s+(?:\S+\s+){0,4}outlook", re.I), "LOWER"),
    (re.compile(r"revis\w+\s+down\w*\s+(?:\S+\s+){0,4}guidance", re.I), "LOWER"),
    # NARROW_RANGE — narrowing the guidance range (verb forms only; excludes
    # "narrower than our guidance range" which describes EPS performance, not
    # a guidance action)
    (re.compile(r"\bnarrow(?:ing|ed|s)\b\s+(?:\S+\s+){0,4}guidance", re.I), "NARROW_RANGE"),
    (re.compile(r"\bnarrow(?:ing|ed|s)\b\s+(?:our\s+|the\s+)?(?:\w+\s+){0,2}range", re.I), "NARROW_RANGE"),
    (re.compile(r"tighten\w*\s+(?:\S+\s+){0,4}guidance", re.I), "NARROW_RANGE"),
    # MAINTAIN — reaffirming guidance
    (re.compile(r"reaffirm\w*\s+(?:\S+\s+){0,4}guidance", re.I), "MAINTAIN"),
    (re.compile(r"maintain\w*\s+(?:\S+\s+){0,4}guidance", re.I), "MAINTAIN"),
    (re.compile(r"reiterat\w*\s+(?:\S+\s+){0,4}guidance", re.I), "MAINTAIN"),
    (re.compile(r"on\s+track\s+(?:\S+\s+){0,6}guidance", re.I), "MAINTAIN"),
]

_BACKLOG_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    # EXPLICIT_MULTI_QUARTER — dollar amount or multi-quarter visibility stated
    (re.compile(r"backlog.{0,50}\$\s*[\d,.]+", re.I), "EXPLICIT_MULTI_QUARTER"),
    (re.compile(r"backlog.{0,50}\d+.{0,15}(?:billion|million)", re.I), "EXPLICIT_MULTI_QUARTER"),
    (re.compile(r"record\s+backlog", re.I), "EXPLICIT_MULTI_QUARTER"),
    (re.compile(r"order\s+book.{0,50}\d", re.I), "EXPLICIT_MULTI_QUARTER"),
    (re.compile(r"backlog.{0,30}(?:months?|quarters?)\s+of", re.I), "EXPLICIT_MULTI_QUARTER"),
    (
        re.compile(r"\d+\s+months?\s+of\s+(?:backlog|visibility|coverage)", re.I),
        "EXPLICIT_MULTI_QUARTER",
    ),
    # STRONG — strong demand / pipeline without explicit figures
    (re.compile(r"strong\s+(?:\w+\s+){0,3}(?:backlog|pipeline|demand|bookings)", re.I), "STRONG"),
    (re.compile(r"growing\s+(?:\w+\s+){0,3}pipeline", re.I), "STRONG"),
    (re.compile(r"increas\w+\s+(?:\w+\s+){0,3}(?:order|demand|bookings)", re.I), "STRONG"),
    # LIMITED — limited visibility
    (re.compile(r"limited\s+(?:\w+\s+){0,4}visibility", re.I), "LIMITED"),
    (re.compile(r"uncertain\s+(?:\w+\s+){0,4}demand", re.I), "LIMITED"),
    (re.compile(r"visibility.{0,20}limited", re.I), "LIMITED"),
    (re.compile(r"limited\s+(?:\w+\s+){0,4}(?:backlog|pipeline)", re.I), "LIMITED"),
]


# ---------------------------------------------------------------------------
# Pure computation helpers — scored 0-100 (raw_score before weighting)
# ---------------------------------------------------------------------------


def _score_revenue_growth_yoy(yoy_pct: float | None) -> int:
    """Map YoY revenue growth (%) to a 0-100 raw score.

    Factor_Mapping_Guide §F2 Revenue Growth bands:
      > 100 % → 100    (hypergrowth)
      ≥  50 % →  90    (LITE example: +65% → 90)
      ≥  25 % →  75
      ≥  10 % →  60
      ≥   0 % →  45    (low single-digit)
      <   0 % →  20    (negative — declining)
      None    →   0    (data unavailable)
    """
    if yoy_pct is None:
        return 0
    if yoy_pct > 100.0:
        return 100
    if yoy_pct >= 50.0:
        return 90
    if yoy_pct >= 25.0:
        return 75
    if yoy_pct >= 10.0:
        return 60
    if yoy_pct >= 0.0:
        return 45
    return 20


def _score_eps_beat_history(beats_in_3: int) -> int:
    """Map rolling 3-quarter EPS beat count to a 0-100 raw score.

    Factor_Mapping_Guide §F2 EPS Beat History bands:
      3 consecutive beats → 100  (LITE: 3 consecutive → 100)
      2 of 3              →  80
      1 of 3              →  55
      0 of 3              →  20
    """
    return _EPS_BEAT_SCORE.get(max(0, min(3, beats_in_3)), 20)


def _score_guidance_direction(guidance_label: str) -> int:
    """Map guidance category label to a 0-100 raw score.

    Factor_Mapping_Guide §F2 Guidance Direction bands:
      RAISE_FULL_YEAR → 100  (raised full-year guidance; LITE → 100)
      MAINTAIN        →  70  (maintained / reaffirmed)
      NARROW_RANGE    →  55  (narrowed range)
      LOWER           →  20  (guidance cut)
      Unknown         →  55  (default neutral)
    """
    return _GUIDANCE_SCORES.get(guidance_label, 55)


def _score_gross_margin_trend(change_pts: float | None) -> int:
    """Map gross margin change (ppts) to a 0-100 raw score.

    Factor_Mapping_Guide §F2 Gross Margin Trend bands:
      Expanding  > 3 pts  → 100
      Expanding  ≥ 1 pt   →  80  (LITE: expanding ~2pts → 80)
      Flat      ≥ -1 pt   →  60
      Contracting < -1 pt →  30
      None                →  60  (neutral when data unavailable)
    """
    if change_pts is None:
        return 60  # neutral — no data
    if change_pts > 3.0:
        return 100
    if change_pts >= 1.0:
        return 80
    if change_pts >= -1.0:
        return 60  # flat
    return 30  # contracting


def _score_backlog_visibility(backlog_label: str) -> int:
    """Map backlog/visibility category to a 0-100 raw score.

    Factor_Mapping_Guide §F2 Backlog / Visibility bands:
      EXPLICIT_MULTI_QUARTER → 100  (dollar amount + multi-quarter; LITE → 100)
      STRONG                 →  80  (strong commentary without figures)
      LIMITED                →  50  (limited visibility)
      NO_COMMENTARY          →  30  (no mention)
      Unknown                →  30  (default to most conservative)
    """
    return _BACKLOG_SCORES.get(backlog_label, 30)


def _classify_guidance_from_transcript(transcript_text: str) -> str:
    """Classify guidance direction from an earnings-call transcript string.

    Scans for guidance-related phrases in priority order
    (RAISE_FULL_YEAR > LOWER > NARROW_RANGE > MAINTAIN).
    Returns 'MAINTAIN' when the transcript is empty or no pattern fires.

    This is a pure function: no I/O, no randomness.
    """
    if not transcript_text.strip():
        return "MAINTAIN"

    for pattern, label in _GUIDANCE_PATTERNS:
        if pattern.search(transcript_text):
            return label

    return "MAINTAIN"  # default: guidance is assumed maintained


def _classify_backlog_from_transcript(transcript_text: str) -> str:
    """Classify backlog/visibility level from an earnings-call transcript string.

    Scans for backlog-related phrases in priority order
    (EXPLICIT_MULTI_QUARTER > STRONG > LIMITED).
    Returns 'NO_COMMENTARY' when no pattern fires.

    This is a pure function: no I/O, no randomness.
    """
    for pattern, label in _BACKLOG_PATTERNS:
        if pattern.search(transcript_text):
            return label

    return "NO_COMMENTARY"


def _compute_f2_total(
    rev_raw: int,
    eps_raw: int,
    guidance_raw: int,
    margin_raw: int,
    backlog_raw: int,
) -> int:
    """Compute the weighted F2 composite score (0-100).

    Applies Factor_Mapping_Guide §F2 weights:
      Revenue   * 0.30
      EPS Beat  * 0.20
      Guidance  * 0.20
      Margin    * 0.15
      Backlog   * 0.15
    """
    weighted = (
        rev_raw * _W_REVENUE
        + eps_raw * _W_EPS_BEAT
        + guidance_raw * _W_GUIDANCE
        + margin_raw * _W_MARGIN
        + backlog_raw * _W_BACKLOG
    )
    return min(100, round(weighted))


def _grade_from_total(total: int) -> str:
    """Convert a numeric F2 total to a human-readable grade string.

    Factor_Mapping_Guide final-score boundaries:
      ≥ 80 → STRONG BUY
      ≥ 65 → BUY
      ≥ 40 → NEUTRAL
      ≥ 20 → WEAK
      <  20 → AVOID
    """
    if total >= _GRADE_STRONG_BUY_MIN:
        return F2Grade.STRONG_BUY
    if total >= _GRADE_BUY_MIN:
        return F2Grade.BUY
    if total >= _GRADE_NEUTRAL_MIN:
        return F2Grade.NEUTRAL
    if total >= _GRADE_WEAK_MIN:
        return F2Grade.WEAK
    return F2Grade.AVOID


# ---------------------------------------------------------------------------
# Network-dependent service
# ---------------------------------------------------------------------------


class EarningsService:
    """Fetches financial data from Alpha Vantage and computes the F2 Earnings
    Quality score for a given ticker."""

    def __init__(
        self,
        api_key: str,
        transcript_api_key: str,
        client: httpx.AsyncClient,
    ) -> None:
        # Used for INCOME_STATEMENT and EARNINGS endpoints.
        self._api_key = api_key
        # Used exclusively for EARNINGS_CALL_TRANSCRIPT endpoint.
        self._transcript_api_key = transcript_api_key
        self._client = client

    async def compute_earnings(self, ticker: str) -> EarningsResponse:
        """Compute all earnings-quality indicators and the F2 score for ``ticker``.

        Steps:
        1. Fetch quarterly income statements (revenue, gross margin).
        2. Fetch quarterly EPS history (reported vs estimated).
        3. Fetch latest earnings call transcript (guidance, backlog).
        4. Score each pure indicator and assemble the weighted response.

        Falls back to neutral scores when data is insufficient or unavailable.
        """
        # ---- Fetch raw data ----
        income_data = await self._fetch_income_statement(ticker)
        earnings_data = await self._fetch_earnings(ticker)

        # Determine latest quarter for transcript fetch (FMP requires separate year + quarter).
        year_quarter = self._latest_year_quarter_from_earnings(earnings_data)
        transcript_quarter_str: str | None = None
        transcript_text = ""
        if year_quarter:
            year, quarter = year_quarter
            transcript_quarter_str = f"{year}Q{quarter}"
            transcript_text = await self._fetch_transcript_text(ticker, year, quarter)
            logger.debug(
                "[F2] %s transcript fetched (quarter=%s, chars=%d)",
                ticker.upper(),
                transcript_quarter_str,
                len(transcript_text),
            )
            if transcript_text:
                logger.debug(
                    "[F2] %s transcript snippet (first 500 chars): %r",
                    ticker.upper(),
                    transcript_text[:500],
                )
            else:
                logger.debug(
                    "[F2] %s transcript is empty — FMP returned no content for %s",
                    ticker.upper(),
                    transcript_quarter_str,
                )

        # ---- Revenue Growth YoY ----
        # Use most recent quarter vs same quarter one year prior (index 4).
        quarterly_revenues = self._extract_quarterly_revenues(income_data)
        yoy_pct = self._compute_yoy_revenue_growth(quarterly_revenues)
        rev_raw = _score_revenue_growth_yoy(yoy_pct)
        rev_score = round(rev_raw * _W_REVENUE)

        # ---- EPS Beat History (rolling 3 quarters) ----
        beats_in_3, quarters_checked = self._count_eps_beats(earnings_data)
        eps_raw = _score_eps_beat_history(beats_in_3)
        eps_score = round(eps_raw * _W_EPS_BEAT)

        # ---- Guidance Direction (from transcript) ----
        guidance_label = _classify_guidance_from_transcript(transcript_text)
        guidance_raw = _score_guidance_direction(guidance_label)
        guidance_score = round(guidance_raw * _W_GUIDANCE)

        # ---- Gross Margin Trend ----
        gross_margins = self._extract_gross_margins(income_data)
        margin_change_pts = self._compute_margin_change(gross_margins)
        margin_raw = _score_gross_margin_trend(margin_change_pts)
        margin_score = round(margin_raw * _W_MARGIN)

        # ---- Backlog / Visibility (from transcript) ----
        backlog_label = _classify_backlog_from_transcript(transcript_text)
        backlog_raw = _score_backlog_visibility(backlog_label)
        backlog_score = round(backlog_raw * _W_BACKLOG)
        logger.debug(
            "[F2] %s backlog classification: label=%s raw_score=%d contribution=%d/15",
            ticker.upper(),
            backlog_label,
            backlog_raw,
            backlog_score,
        )

        # ---- F2 composite ----
        f2_total = _compute_f2_total(rev_raw, eps_raw, guidance_raw, margin_raw, backlog_raw)
        f2_grade = _grade_from_total(f2_total)

        return EarningsResponse(
            ticker=ticker.upper(),
            revenue_growth=RevenueGrowthIndicator(
                yoy_pct=round(yoy_pct, 2) if yoy_pct is not None else None,
                raw_score=rev_raw,
                score=rev_score,
                max_score=30,
            ),
            eps_beats=EpsBeatsIndicator(
                beats_in_3=beats_in_3,
                quarters_checked=quarters_checked,
                raw_score=eps_raw,
                score=eps_score,
                max_score=20,
            ),
            guidance=GuidanceIndicator(
                guidance_label=guidance_label,
                transcript_quarter=transcript_quarter_str,
                raw_score=guidance_raw,
                score=guidance_score,
                max_score=20,
            ),
            margin_trajectory=MarginTrajectoryIndicator(
                gross_margins=[round(m, 2) for m in gross_margins],
                margin_change_pts=(
                    round(margin_change_pts, 2) if margin_change_pts is not None else None
                ),
                raw_score=margin_raw,
                score=margin_score,
                max_score=15,
            ),
            backlog_btb=BacklogBtbIndicator(
                backlog_label=backlog_label,
                raw_score=backlog_raw,
                score=backlog_score,
                max_score=15,
            ),
            f2_score=f2_total,
            f2_grade=f2_grade,
        )

    # ------------------------------------------------------------------
    # Private network helpers
    # ------------------------------------------------------------------

    async def _fetch_income_statement(self, ticker: str) -> dict[str, object]:
        """Fetch quarterly income statement from Alpha Vantage INCOME_STATEMENT."""
        try:
            response = await self._client.get(
                _AV_BASE_URL,
                params={
                    "function": "INCOME_STATEMENT",
                    "symbol": ticker,
                    "apikey": self._api_key,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            data: dict[str, object] = response.json()
            return data
        except (httpx.HTTPStatusError, httpx.RequestError):
            return {}

    async def _fetch_earnings(self, ticker: str) -> dict[str, object]:
        """Fetch quarterly EPS history from Alpha Vantage EARNINGS."""
        try:
            response = await self._client.get(
                _AV_BASE_URL,
                params={
                    "function": "EARNINGS",
                    "symbol": ticker,
                    "apikey": self._api_key,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            data: dict[str, object] = response.json()
            return data
        except (httpx.HTTPStatusError, httpx.RequestError):
            return {}

    async def _fetch_transcript_text(self, ticker: str, year: int, quarter: int) -> str:
        """Fetch the earnings call transcript text from Financial Modeling Prep.

        Calls the FMP stable earnings-call-transcript endpoint:
          GET /stable/earning-call-transcript
              ?symbol={SYMBOL}&year={YYYY}&quarter={Q}&apikey={KEY}

        FMP returns a list with a single record whose ``content`` field
        contains the full transcript as a single string.  Returns an empty
        string when the transcript is unavailable or the request fails.
        """
        try:
            response = await self._client.get(
                _FMP_TRANSCRIPT_URL,
                params={
                    "symbol": ticker,
                    "year": year,
                    "quarter": quarter,
                    "apikey": self._transcript_api_key,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            records: list[dict[str, object]] = response.json()
            if not records:
                return ""
            content = records[0].get("content", "")
            return str(content) if content else ""
        except (httpx.HTTPStatusError, httpx.RequestError):
            return ""

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_quarterly_revenues(income_data: dict) -> list[float]:  # type: ignore[type-arg]
        """Extract quarterly total revenue values (oldest first).

        Alpha Vantage returns ``quarterlyReports`` in reverse-chron order
        (most recent first).  We reverse to get oldest-to-newest so index 0
        is the oldest and index -1 is the most recent.
        """
        reports: list[dict] = income_data.get("quarterlyReports", [])  # type: ignore[type-arg]
        revenues: list[float] = []
        for r in reversed(reports[:_INCOME_STMT_QUARTERS]):
            raw = r.get("totalRevenue", "None")
            if raw and raw not in ("None", "N/A", ""):
                with contextlib.suppress(ValueError):
                    revenues.append(float(raw))
        return revenues

    @staticmethod
    def _compute_yoy_revenue_growth(revenues: list[float]) -> float | None:
        """Compute YoY revenue growth from the quarterly revenue list.

        Compares the most recent quarter (index -1) to the same quarter
        one year prior (index -5, i.e. 4 quarters back).
        Returns None when insufficient data.
        """
        if len(revenues) < 5:
            return None
        current = revenues[-1]
        year_ago = revenues[-5]
        if year_ago == 0.0:
            return None
        return (current - year_ago) / abs(year_ago) * 100.0

    @staticmethod
    def _count_eps_beats(earnings_data: dict) -> tuple[int, int]:  # type: ignore[type-arg]
        """Count EPS beats in the last 3 reported quarters.

        Iterates the ``quarterlyEarnings`` array (most recent first) and
        compares ``reportedEPS`` to ``estimatedEPS``.

        Returns (beats_in_3, quarters_checked) where beats_in_3 is 0-3.
        """
        quarterly: list[dict] = earnings_data.get("quarterlyEarnings", [])  # type: ignore[type-arg]
        beats = 0
        checked = 0
        for q in quarterly[:_EPS_BEAT_QUARTERS]:
            reported = q.get("reportedEPS", "None")
            estimated = q.get("estimatedEPS", "None")
            if reported in ("None", "N/A", "") or estimated in ("None", "N/A", ""):
                continue
            try:
                if float(reported) > float(estimated):
                    beats += 1
                checked += 1
            except ValueError:
                pass
        return beats, checked

    @staticmethod
    def _extract_gross_margins(income_data: dict) -> list[float]:  # type: ignore[type-arg]
        """Extract gross-margin percentages (oldest first) for the last 3 quarters."""
        reports: list[dict] = income_data.get("quarterlyReports", [])  # type: ignore[type-arg]
        margins: list[float] = []
        for r in reversed(reports[:3]):
            gp_raw = r.get("grossProfit", "None")
            rev_raw = r.get("totalRevenue", "None")
            if gp_raw in ("None", "N/A", "") or rev_raw in ("None", "N/A", ""):
                continue
            try:
                gp = float(gp_raw)
                rev = float(rev_raw)
                if rev != 0.0:
                    margins.append(round(gp / rev * 100.0, 4))
            except ValueError:
                pass
        return margins

    @staticmethod
    def _compute_margin_change(gross_margins: list[float]) -> float | None:
        """Compute gross-margin change in percentage points (most recent vs oldest).

        Returns None when fewer than 2 data points are available.
        A positive value means margins have expanded.
        """
        if len(gross_margins) < 2:
            return None
        return gross_margins[-1] - gross_margins[0]

    @staticmethod
    def _latest_year_quarter_from_earnings(
        earnings_data: dict[str, object],
    ) -> tuple[int, int] | None:
        """Derive the most recent fiscal (year, quarter) from the EARNINGS response.

        FMP requires ``year`` and ``quarter`` as separate integer parameters.
        Quarter is derived from the fiscal month: Jan-Mar->Q1, Apr-Jun->Q2,
        Jul-Sep->Q3, Oct-Dec->Q4.

        Returns None when data is unavailable.
        """
        quarterly: list[dict[str, object]] = earnings_data.get("quarterlyEarnings", [])  # type: ignore[assignment]
        if not quarterly:
            return None
        fiscal_date = quarterly[0].get("fiscalDateEnding", "")
        if not fiscal_date:
            return None
        try:
            year_str, month_str, _ = str(fiscal_date).split("-")
            quarter_num = (int(month_str) - 1) // 3 + 1
            return int(year_str), quarter_num
        except (ValueError, AttributeError):
            return None
