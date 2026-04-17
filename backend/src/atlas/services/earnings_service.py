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

import asyncio
import contextlib
import logging
import re
from typing import Any, Final

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

# Pre-profitability weights — applied when a name has negative EPS AND
# revenue growth >20% YoY.  Growth trajectory (revenue + guidance) = 60%;
# current profitability metrics (EPS beat + margin + backlog) = 40%.
# Derived by preserving within-group proportions:
#   Revenue 30/(30+20) × 60% = 36%  |  Guidance 20/(30+20) × 60% = 24%
#   EPS beat 20/(20+15+15) × 40% = 16%  |  Margin 15/50 × 40% = 12%  |  Backlog 15/50 × 40% = 12%
_W_REVENUE_PP: Final[float] = 0.36
_W_EPS_BEAT_PP: Final[float] = 0.16
_W_GUIDANCE_PP: Final[float] = 0.24
_W_MARGIN_PP: Final[float] = 0.12
_W_BACKLOG_PP: Final[float] = 0.12

# Revenue growth threshold that, combined with negative EPS, triggers pre-profitability mode.
_PP_REVENUE_GROWTH_MIN: Final[float] = 20.0  # >20% YoY

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
# UNDETECTED is excluded — it means no pattern fired in the transcript;
# the sub-factor is dropped and remaining weights are rescaled to 100%.
_GUIDANCE_SCORES: Final[dict[str, int]] = {
    "RAISE_FULL_YEAR": 100,  # management raised full-year guidance
    "MAINTAIN": 70,  # guidance maintained / reaffirmed
    "NARROW_RANGE": 55,  # guidance range narrowed
    "LOWER": 20,  # guidance cut / lowered
    "UNDETECTED": -1,  # sentinel — no pattern matched; excluded from scoring
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

# Polygon financials endpoint — fallback for AV INCOME_STATEMENT.
# GET /vX/reference/financials?ticker={T}&timeframe=quarterly&limit={N}&apiKey={K}
_POLYGON_FINANCIALS_URL: Final[str] = "https://api.polygon.io/vX/reference/financials"

# FMP stable earnings endpoint — fallback for AV EARNINGS (EPS beat history).
# GET /stable/earnings?symbol={S}&limit={N}&apikey={K}
_FMP_EARNINGS_URL: Final[str] = "https://financialmodelingprep.com/stable/earnings"

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Guidance semantic scoring rubric
# ---------------------------------------------------------------------------

# Extracts sentences that are plausibly forward-looking.  Used to focus the
# scorer on guidance-bearing text and reduce noise from historical commentary.
_FORWARD_LOOKING_FILTER: Final[re.Pattern[str]] = re.compile(
    r"\b(?:expect|anticipat|forecast|project|outlook|guid|plan\s|will\s+"
    r"(?:be|likely|continue|remain)|next\s+(?:quarter|fiscal|year)|"
    r"full.?year|fiscal\s+\d{4}|calendar\s+\d{4}|going\s+forward|"
    r"look(?:ing)?\s+ahead)",
    re.I,
)

# Scoring rubric: each category maps to a list of (term, weight) pairs.
# Term is a lowercase substring; weight is the evidence strength.
# The scorer sums weights of all terms found in the forward-looking text,
# then picks the category with the highest aggregate score above the
# minimum threshold.  Multiple weak signals accumulate into a verdict —
# no single exact phrase is required.
_GUIDANCE_RUBRIC: Final[dict[str, list[tuple[str, float]]]] = {
    "RAISE_FULL_YEAR": [
        # Explicit raise language
        ("raising guidance",          5.0),
        ("raise guidance",            5.0),
        ("raised guidance",           5.0),
        ("raising our guidance",      5.0),
        ("raised our guidance",       5.0),
        ("increasing guidance",       4.5),
        ("increase our guidance",     4.5),
        ("increased our guidance",    4.5),
        ("upward revision",           5.0),
        ("upwardly revising",         4.5),
        ("raising outlook",           4.5),
        ("raised outlook",            4.5),
        ("raising our outlook",       4.5),
        # Above-prior-call signals
        ("higher than our last",      5.0),
        ("higher than our prior",     5.0),
        ("above our prior",           4.0),
        ("above prior expectations",  4.5),
        ("above our expectations",    3.5),
        ("above the high end of our guidance", 5.0),
        ("well above",                3.0),
        ("above guidance",            3.5),
        ("exceeded guidance",         3.5),
        ("beat guidance",             3.5),
        ("exceeded the high end",     4.0),
        ("above our forecast",        4.0),
        # Record / new-high framing
        ("record revenue",            4.0),
        ("record earnings",           3.5),
        ("record eps",                3.5),
        ("record free cash flow",     3.0),
        ("new record",                3.0),
        ("new records",               3.0),
        ("anticipate record",         4.0),
        ("anticipate substantial",    3.5),
        ("expect record",             3.5),
        ("substantially new records", 4.0),
        ("substantial new records",   4.0),
        ("expect revenue to be a record", 4.5),
        # Scope amplifiers — add weight when full-year framing is present
        ("full fiscal year",          2.0),
        ("full year",                 1.5),
        ("fiscal year 20",            1.5),
        ("for the year",              1.0),
        ("calendar year",             1.0),
    ],
    "LOWER": [
        # Explicit cut language
        ("lowering guidance",         5.0),
        ("lowering our guidance",     5.0),
        ("lower our guidance",        5.0),
        ("reducing guidance",         5.0),
        ("reducing our guidance",     5.0),
        ("cutting guidance",          5.0),
        ("cut our guidance",          5.0),
        ("revising down",             4.5),
        ("downward revision",         5.0),
        ("downwardly revising",       4.5),
        ("lowering outlook",          4.5),
        ("lower our outlook",         4.5),
        # Below-prior signals
        ("below guidance",            4.0),
        ("below our guidance",        4.0),
        ("below expectations",        3.5),
        ("below our expectations",    3.5),
        ("below our prior",           4.0),
        ("below prior",               3.0),
        ("miss guidance",             4.0),
        ("missed guidance",           4.0),
        ("weaker than expected",      3.0),
        ("weaker than anticipated",   3.0),
        # Macro/demand headwinds context
        ("disappointing",             2.0),
        ("headwinds",                 1.5),
        ("challenging environment",   1.5),
        ("uncertain demand",          2.0),
        ("macro uncertainty",         1.5),
        ("softer demand",             2.5),
        ("slowing demand",            2.5),
    ],
    "NARROW_RANGE": [
        ("narrowing our guidance",    5.0),
        ("narrowing guidance",        5.0),
        ("narrowing the range",       4.5),
        ("narrowed our range",        4.5),
        ("narrowed the range",        4.5),
        ("tightening guidance",       4.5),
        ("tightening our guidance",   5.0),
        ("tighter guidance range",    4.5),
        ("refined our guidance",      4.0),
        ("more confident in our",     2.5),
        ("better visibility",         2.0),
    ],
    "MAINTAIN": [
        # Explicit reaffirmation
        ("reaffirm",                  5.0),
        ("reaffirming",               5.0),
        ("reiterate",                 5.0),
        ("reiterating",               5.0),
        ("maintain guidance",         5.0),
        ("maintaining guidance",      5.0),
        ("maintaining our guidance",  5.0),
        ("on track",                  3.0),
        ("in line with our guidance", 4.5),
        ("consistent with our guidance", 4.5),
        # Issuing specific next-quarter guidance (forward, not a raise/cut)
        ("non-gaap guidance",         3.5),
        ("plus or minus",             3.0),
        ("guidance of",               3.0),
        ("guidance for",              2.5),
        ("guiding for",               3.5),
        ("expect revenue of",         3.0),
        ("expect revenue to be",      2.5),
        ("forecast revenue of",       3.5),
        ("midpoint of",               3.0),
        ("our outlook is",            3.0),
        ("outlook for the",           2.5),
    ],
}

# Minimum aggregate score for a category to be accepted.
# Below this threshold the scorer returns UNDETECTED.
_GUIDANCE_MIN_SCORE: Final[float] = 4.0

# Tie-break priority (highest to lowest) when two categories score equally.
_GUIDANCE_PRIORITY: Final[list[str]] = [
    "RAISE_FULL_YEAR", "LOWER", "NARROW_RANGE", "MAINTAIN",
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


def _score_revenue_growth_yoy(yoy_pct: float | None) -> int | None:
    """Map YoY revenue growth (%) to a 0-100 raw score.

    Factor_Mapping_Guide §F2 Revenue Growth bands:
      > 100 % → 100    (hypergrowth)
      ≥  50 % →  90    (LITE example: +65% → 90)
      ≥  25 % →  75
      ≥  10 % →  60
      ≥   0 % →  45    (low single-digit)
      <   0 % →  20    (negative — declining)
      None    →  None  (AV rate-limited / no data — excluded from F2 with weight rescaling)
    """
    if yoy_pct is None:
        return None
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


def _score_guidance_direction(guidance_label: str) -> int | None:
    """Map guidance category label to a 0-100 raw score, or None when undetected.

    Factor_Mapping_Guide §F2 Guidance Direction bands:
      RAISE_FULL_YEAR → 100  (raised full-year guidance; LITE → 100)
      MAINTAIN        →  70  (maintained / reaffirmed)
      NARROW_RANGE    →  55  (narrowed range)
      LOWER           →  20  (guidance cut)
      UNDETECTED      → None (no pattern matched transcript — excluded from F2)
    """
    if guidance_label == "UNDETECTED":
        return None
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
    """Score guidance direction from an earnings-call transcript.

    Algorithm:
      1. Extract forward-looking sentences via _FORWARD_LOOKING_FILTER to
         focus on guidance-bearing text and reduce noise.
      2. For each category in _GUIDANCE_RUBRIC, sum the weights of all terms
         found in the extracted text (case-insensitive substring match).
      3. Return the highest-scoring category whose total exceeds
         _GUIDANCE_MIN_SCORE.  Ties break by _GUIDANCE_PRIORITY order.
      4. Return UNDETECTED when no category clears the threshold.

    Multiple weak signals accumulate into a verdict — no single exact phrase
    is required.  This is a pure function: no I/O, no randomness.
    """
    if not transcript_text.strip():
        return "UNDETECTED"

    # Step 1 — extract forward-looking sentences
    sentences = re.split(r"[.!?]\s+", transcript_text)
    forward_sentences = [s for s in sentences if _FORWARD_LOOKING_FILTER.search(s)]
    scoring_text = " ".join(forward_sentences).lower() if forward_sentences else transcript_text.lower()

    # Step 2 — score each category
    scores: dict[str, float] = {cat: 0.0 for cat in _GUIDANCE_RUBRIC}
    for category, terms in _GUIDANCE_RUBRIC.items():
        for term, weight in terms:
            if term in scoring_text:
                scores[category] += weight

    # Step 3 — pick winner above threshold in priority order
    eligible = [cat for cat in _GUIDANCE_PRIORITY if scores[cat] >= _GUIDANCE_MIN_SCORE]
    if not eligible:
        return "UNDETECTED"
    return max(eligible, key=lambda cat: scores[cat])


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


def _is_pre_profitability(
    earnings_data: dict[str, object],
    yoy_pct: float | None,
) -> bool:
    """Return True when the ticker qualifies as a pre-profitability growth name.

    Conditions (both must hold):
      1. Most recent quarterly ``reportedEPS`` is negative.
      2. YoY revenue growth exceeds ``_PP_REVENUE_GROWTH_MIN`` (20%).

    Pure function — no I/O, no side effects.
    """
    if yoy_pct is None or yoy_pct <= _PP_REVENUE_GROWTH_MIN:
        return False
    quarterly: list[dict[str, object]] = earnings_data.get("quarterlyEarnings", [])  # type: ignore[assignment]
    if not quarterly:
        return False
    reported_raw = quarterly[0].get("reportedEPS", "None")
    if reported_raw in ("None", "N/A", "", None):
        return False
    try:
        return float(str(reported_raw)) < 0.0
    except ValueError:
        return False


def _compute_f2_total(
    rev_raw: int | None,
    eps_raw: int,
    guidance_raw: int | None,
    margin_raw: int,
    backlog_raw: int,
    *,
    pre_profitability: bool = False,
) -> int:
    """Compute the weighted F2 composite score (0-100).

    When ``pre_profitability`` is True the growth-trajectory sub-factors
    (revenue + guidance) receive 60% of the total weight and the current-
    profitability sub-factors (EPS beat + margin + backlog) receive 40%,
    as per the Factor_Mapping_Guide §F2 pre-profitability adjustment.

    Any sub-factor whose raw score is None (no data) is excluded and the
    remaining weights are rescaled proportionally so they still sum to 1.0.
    """
    if pre_profitability:
        w_rev, w_eps, w_guid, w_mar, w_bkl = (
            _W_REVENUE_PP,
            _W_EPS_BEAT_PP,
            _W_GUIDANCE_PP,
            _W_MARGIN_PP,
            _W_BACKLOG_PP,
        )
    else:
        w_rev, w_eps, w_guid, w_mar, w_bkl = (
            _W_REVENUE,
            _W_EPS_BEAT,
            _W_GUIDANCE,
            _W_MARGIN,
            _W_BACKLOG,
        )

    missing_weight = (
        (w_rev if rev_raw is None else 0.0)
        + (w_guid if guidance_raw is None else 0.0)
    )
    scale = 1.0 / (1.0 - missing_weight) if missing_weight < 1.0 else 1.0

    weighted = (
        (rev_raw * w_rev * scale if rev_raw is not None else 0.0)
        + eps_raw * w_eps * scale
        + (guidance_raw * w_guid * scale if guidance_raw is not None else 0.0)
        + margin_raw * w_mar * scale
        + backlog_raw * w_bkl * scale
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
        polygon_api_key: str,
        client: httpx.AsyncClient,
    ) -> None:
        # Used for INCOME_STATEMENT and EARNINGS endpoints.
        self._api_key = api_key
        # Used exclusively for EARNINGS_CALL_TRANSCRIPT endpoint and FMP EARNINGS fallback.
        self._transcript_api_key = transcript_api_key
        # Used for INCOME_STATEMENT fallback via Polygon /vX/reference/financials.
        self._polygon_key = polygon_api_key
        self._client = client

    async def compute_earnings(
        self,
        ticker: str,
        *,
        income_task: asyncio.Task[dict[str, Any]] | None = None,
    ) -> EarningsResponse:
        """Compute all earnings-quality indicators and the F2 score for ``ticker``.

        Steps:
        1. Fetch quarterly income statements (revenue, gross margin).
        2. Fetch quarterly EPS history (reported vs estimated).
        3. Fetch latest earnings call transcript (guidance, backlog).
        4. Score each pure indicator and assemble the weighted response.

        Falls back to neutral scores when data is insufficient or unavailable.
        """
        # ---- Fetch raw data ----
        # Use the pre-fetched shared task when provided (avoids duplicate
        # INCOME_STATEMENT call that FundamentalService also makes).
        income_data = (
            await income_task
            if income_task is not None
            else await self._fetch_income_statement(ticker)
        )
        earnings_data = await self._fetch_earnings(ticker)

        # Both empty → AV was rate-limited; scores will be fallback-only.
        av_data_available = bool(income_data or earnings_data)

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

        # ---- EPS Beat History (rolling 3 quarters) ----
        beats_in_3, quarters_checked = self._count_eps_beats(earnings_data)
        eps_raw = _score_eps_beat_history(beats_in_3)

        # ---- Guidance Direction (from transcript) ----
        guidance_label = _classify_guidance_from_transcript(transcript_text)
        guidance_raw = _score_guidance_direction(guidance_label)  # None when UNDETECTED

        # ---- Gross Margin Trend ----
        gross_margins = self._extract_gross_margins(income_data)
        margin_change_pts = self._compute_margin_change(gross_margins)
        margin_raw = _score_gross_margin_trend(margin_change_pts)

        # ---- Backlog / Visibility (from transcript) ----
        backlog_label = _classify_backlog_from_transcript(transcript_text)
        backlog_raw = _score_backlog_visibility(backlog_label)

        # ---- Pre-profitability detection ----
        # When EPS is negative AND revenue growth >20% YoY, growth-trajectory
        # sub-factors (revenue + guidance) are upweighted to 60% and
        # profitability sub-factors (EPS beat + margin + backlog) to 40%.
        is_pp = _is_pre_profitability(earnings_data, yoy_pct)
        if is_pp:
            logger.debug("[F2] %s classified as pre-profitability growth name", ticker.upper())

        # Choose weights for weighted-score display in the response.
        w_rev   = _W_REVENUE_PP   if is_pp else _W_REVENUE
        w_eps   = _W_EPS_BEAT_PP  if is_pp else _W_EPS_BEAT
        w_guid  = _W_GUIDANCE_PP  if is_pp else _W_GUIDANCE
        w_mar   = _W_MARGIN_PP    if is_pp else _W_MARGIN
        w_bkl   = _W_BACKLOG_PP   if is_pp else _W_BACKLOG

        rev_score      = round(rev_raw * w_rev) if rev_raw is not None else None
        eps_score      = round(eps_raw * w_eps)
        guidance_score = round(guidance_raw * w_guid) if guidance_raw is not None else None
        margin_score   = round(margin_raw * w_mar)
        backlog_score  = round(backlog_raw * w_bkl)
        logger.debug(
            "[F2] %s backlog classification: label=%s raw_score=%d contribution=%d",
            ticker.upper(),
            backlog_label,
            backlog_raw,
            backlog_score,
        )

        # ---- F2 composite ----
        f2_total = _compute_f2_total(
            rev_raw, eps_raw, guidance_raw, margin_raw, backlog_raw,
            pre_profitability=is_pp,
        )
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
            data_available=av_data_available,
            is_pre_profitability=is_pp,
        )

    # ------------------------------------------------------------------
    # Private network helpers
    # ------------------------------------------------------------------

    async def _fetch_income_statement(self, ticker: str) -> dict[str, object]:
        """Fetch quarterly income statement from AV; falls back to Polygon on failure."""
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
            if "Note" in data or "Information" in data:
                logger.debug("AV INCOME_STATEMENT unavailable for %s — trying Polygon", ticker)
                return await self._fetch_income_statement_polygon(ticker)
            return data
        except (httpx.HTTPStatusError, httpx.RequestError):
            logger.debug("AV INCOME_STATEMENT request failed for %s — trying Polygon", ticker)
            return await self._fetch_income_statement_polygon(ticker)

    async def _fetch_earnings(self, ticker: str) -> dict[str, object]:
        """Fetch quarterly EPS history from AV; falls back to FMP on failure."""
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
            if "Note" in data or "Information" in data:
                logger.debug("AV EARNINGS unavailable for %s — trying FMP", ticker)
                return await self._fetch_earnings_fmp(ticker)
            return data
        except (httpx.HTTPStatusError, httpx.RequestError):
            logger.debug("AV EARNINGS request failed for %s — trying FMP", ticker)
            return await self._fetch_earnings_fmp(ticker)

    async def _fetch_income_statement_polygon(
        self, ticker: str
    ) -> dict[str, object]:
        """Fetch quarterly income statement from Polygon and normalise to AV shape.

        Returns ``{"quarterlyReports": [{"totalRevenue": ..., "grossProfit": ...}, ...]}``,
        most-recent first — matching AV's INCOME_STATEMENT layout so downstream
        extraction helpers need no changes.
        """
        if not self._polygon_key:
            return {}
        try:
            response = await self._client.get(
                _POLYGON_FINANCIALS_URL,
                params={
                    "ticker": ticker,
                    "timeframe": "quarterly",
                    # Fetch one extra so _compute_yoy_revenue_growth has 5 quarters.
                    "limit": _INCOME_STMT_QUARTERS + 1,
                    "apiKey": self._polygon_key,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            raw: dict[str, object] = response.json()
            results: list[dict[str, object]] = raw.get("results", [])  # type: ignore[assignment]
            quarterly_reports: list[dict[str, object]] = []
            for r in results:
                financials = r.get("financials", {})
                income = (
                    financials.get("income_statement", {})
                    if isinstance(financials, dict)
                    else {}
                )
                rev_entry = income.get("revenues", {}) if isinstance(income, dict) else {}
                gp_entry = income.get("gross_profit", {}) if isinstance(income, dict) else {}
                rev_val = rev_entry.get("value") if isinstance(rev_entry, dict) else None
                gp_val = gp_entry.get("value") if isinstance(gp_entry, dict) else None
                quarterly_reports.append(
                    {
                        "totalRevenue": (
                            str(int(rev_val)) if rev_val is not None else "None"
                        ),
                        "grossProfit": (
                            str(int(gp_val)) if gp_val is not None else "None"
                        ),
                    }
                )
            logger.debug(
                "Polygon INCOME_STATEMENT fallback: %d quarters for %s",
                len(quarterly_reports),
                ticker,
            )
            return {"quarterlyReports": quarterly_reports}
        except (httpx.HTTPStatusError, httpx.RequestError):
            return {}

    async def _fetch_earnings_fmp(self, ticker: str) -> dict[str, object]:
        """Fetch quarterly EPS history from FMP and normalise to AV shape.

        Returns ``{"quarterlyEarnings": [{"fiscalDateEnding": ..., "reportedEPS": ...,
        "estimatedEPS": ...}, ...]}``, most-recent first — matching AV's EARNINGS layout
        so ``_count_eps_beats`` and ``_latest_year_quarter_from_earnings`` work unchanged.
        """
        if not self._transcript_api_key:
            return {}
        try:
            response = await self._client.get(
                _FMP_EARNINGS_URL,
                params={
                    "symbol": ticker,
                    # Fetch a few extra in case some entries are missing EPS fields.
                    "limit": _EPS_BEAT_QUARTERS + 3,
                    "apikey": self._transcript_api_key,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, list):
                return {}
            quarterly_earnings: list[dict[str, object]] = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                eps_actual = item.get("epsActual")
                eps_estimated = item.get("epsEstimated")
                date = item.get("date", "")
                quarterly_earnings.append(
                    {
                        "fiscalDateEnding": str(date),
                        "reportedEPS": (
                            str(eps_actual) if eps_actual is not None else "None"
                        ),
                        "estimatedEPS": (
                            str(eps_estimated) if eps_estimated is not None else "None"
                        ),
                    }
                )
            logger.debug(
                "FMP EARNINGS fallback: %d quarters for %s",
                len(quarterly_earnings),
                ticker,
            )
            return {"quarterlyEarnings": quarterly_earnings}
        except (httpx.HTTPStatusError, httpx.RequestError):
            return {}

    async def _fetch_transcript_text(self, ticker: str, year: int, quarter: int) -> str:
        """Fetch the earnings call transcript text from Financial Modeling Prep.

        Calls the FMP stable earnings-call-transcript endpoint:
          GET /stable/earning-call-transcript
              ?symbol={SYMBOL}&year={YYYY}&quarter={Q}&apikey={KEY}

        FMP indexes transcripts by the calendar year/quarter of the call, which
        may differ from the fiscal year/quarter derived from the earnings date
        (e.g. a company with an October fiscal year-end reports in February but
        the call is indexed under the prior calendar year Q4).  When the primary
        (year, quarter) returns empty, the method probes up to three adjacent
        quarter slots in reverse-chronological order before giving up.
        """
        # Build a probe sequence: primary slot first, then up to 3 prior quarters.
        def _prev_quarter(y: int, q: int) -> tuple[int, int]:
            return (y - 1, 4) if q == 1 else (y, q - 1)

        slots: list[tuple[int, int]] = [(year, quarter)]
        y, q = year, quarter
        for _ in range(3):
            y, q = _prev_quarter(y, q)
            slots.append((y, q))

        for slot_year, slot_quarter in slots:
            try:
                response = await self._client.get(
                    _FMP_TRANSCRIPT_URL,
                    params={
                        "symbol": ticker,
                        "year": slot_year,
                        "quarter": slot_quarter,
                        "apikey": self._transcript_api_key,
                    },
                    timeout=20.0,
                )
                response.raise_for_status()
                raw = response.json()
                if not isinstance(raw, list):
                    logger.debug("FMP transcript non-list response for %s: %s", ticker, raw)
                    continue
                records: list[dict[str, object]] = raw
                if not records:
                    continue
                content = records[0].get("content", "")
                text = str(content) if content else ""
                if text:
                    logger.debug(
                        "[F2] %s transcript found at slot %dQ%d (primary was %dQ%d)",
                        ticker.upper(), slot_year, slot_quarter, year, quarter,
                    )
                    return text
            except (httpx.HTTPStatusError, httpx.RequestError):
                continue

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
