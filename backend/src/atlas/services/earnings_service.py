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

from atlas.schemas.earnings import (
    EarningsResponse,
    F2Grade,
)
from atlas.services.provider_response_cache import fetch_alpha_vantage_cached

logger = logging.getLogger(__name__)

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

# Guidance is intentionally fixed to a neutral fallback contribution.
# Transcript NLP is no longer used for the guidance sub-factor.
_GUIDANCE_SCORES: Final[dict[str, int]] = {
    "NO_DATA_AVAILABLE": 50,  # fixed raw fallback -> 10 weighted pts at the nominal 20% weight
}

_GUIDANCE_FIXED_CONTRIBUTION: Final[int] = 10

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


def _score_guidance_direction(guidance_label: str) -> int:
    """Return the fixed raw fallback used for the deprecated guidance signal."""
    return _GUIDANCE_SCORES.get(guidance_label, 50)


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
    """Guidance transcript classification is disabled; always return the fallback label."""
    return "NO_DATA_AVAILABLE"


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
    guidance_raw: int,
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

    Guidance is deprecated and contributes a fixed 10 points instead of
    transcript-derived scoring.
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

    missing_weight = w_rev if rev_raw is None else 0.0
    scale = 1.0 / (1.0 - missing_weight) if missing_weight < 1.0 else 1.0

    weighted = (
        (rev_raw * w_rev * scale if rev_raw is not None else 0.0)
        + eps_raw * w_eps * scale
        + _GUIDANCE_FIXED_CONTRIBUTION
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
# v7.3.4 F2 scoring constants
# ---------------------------------------------------------------------------

_W_SF1: Final[float] = 0.30  # Revenue Growth YoY (normal)
_W_SF2: Final[float] = 0.20  # Gross Margin Trend
_W_SF3: Final[float] = 0.20  # EPS Beat Consistency 4Q
_W_SF4: Final[float] = 0.15  # Guidance Reliability
_W_SF5: Final[float] = 0.15  # Forward Visibility

_W_SF1_PP: Final[float] = 0.375  # Revenue — pre-profit re-weight
_W_SF2_PP: Final[float] = 0.25  # Gross Margin — pre-profit
_W_SF4_PP: Final[float] = 0.1875  # Guidance — pre-profit
_W_SF5_PP: Final[float] = 0.1875  # Forward Visibility — pre-profit

# DATA_GAP raw score is set so the *weighted* contribution to F2 equals 10 points
# at the normal 15% SF4 weight (10 / 0.15 ≈ 66.67).  In pre-profit mode (weight
# 18.75%) the contribution becomes ~12.5 pts — acceptable until Bloomberg lands.
_DATA_GAP_GUIDANCE_SCORE: Final[float] = 10.0 / _W_SF4  # Bloomberg not available in V1
_W_F2: Final[float] = 0.25  # F2 weight in overall conviction score

# Forward visibility label → integer score mapping
_FWD_VIS_SCORES: Final[dict[str, int]] = {
    "SPECIFIC_RAISED": 100,
    "SPECIFIC_MAINTAINED": 80,
    "DIRECTIONAL": 60,
    "VAGUE_NONE": 30,
    "WITHDRAWN_REDUCED": 0,
}
_FWD_VIS_SCORE_TO_LABEL: Final[dict[int, str]] = {v: k for k, v in _FWD_VIS_SCORES.items()}

# Ordered regex patterns for _classify_forward_visibility_from_transcript.
# Higher-priority labels appear first so early-exit gives correct precedence.
_FWD_VIS_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    # WITHDRAWN_REDUCED — check before RAISED to avoid false positives
    (re.compile(r"withdraw\w*\s+(?:our\s+)?guid\w*", re.I), "WITHDRAWN_REDUCED"),
    (re.compile(r"lower\w*\s+(?:our\s+)?(?:guid\w*|outlook)", re.I), "WITHDRAWN_REDUCED"),
    (re.compile(r"reduc\w+\s+(?:our\s+)?(?:guid\w*|forecast|outlook)", re.I), "WITHDRAWN_REDUCED"),
    (
        re.compile(
            r"below\s+(?:our\s+)?(?:prior|previous)\s+(?:guid\w*|outlook|forecast|guide)", re.I
        ),
        "WITHDRAWN_REDUCED",
    ),
    # SPECIFIC_RAISED
    (
        re.compile(
            r"rais\w+\s+(?:our\s+)?(?:full.?year|annual|fy\w*)\s+(?:guid\w*|outlook|forecast|revenue|eps)",
            re.I,
        ),
        "SPECIFIC_RAISED",
    ),
    (
        re.compile(r"rais\w+\s+(?:our\s+)?(?:guid\w*|revenue\s+guid\w*|eps\s+guid\w*)", re.I),
        "SPECIFIC_RAISED",
    ),
    # "increased our [FY28] outlook/guidance/forecast" — allow 0-3 words between
    (
        re.compile(r"increas\w+\s+(?:our\s+)?(?:\w+\s+){0,3}?(?:guid\w*|outlook|forecast)", re.I),
        "SPECIFIC_RAISED",
    ),
    # "we now expect FY27 revenue / full-year EPS / ..." — upward revision phrasing
    (
        re.compile(
            r"now\s+expect\w*\s+(?:.{0,60}?)(?:revenue|sales|eps|earnings|\$\s*\d|billion|million)",
            re.I,
        ),
        "SPECIFIC_RAISED",
    ),
    # "above our prior guide / previous outlook" — explicit upward revision
    (
        re.compile(
            r"above\s+(?:our\s+)?(?:prior|previous)\s+(?:guid\w*|outlook|forecast|guide)", re.I
        ),
        "SPECIFIC_RAISED",
    ),
    # SPECIFIC_MAINTAINED
    (
        re.compile(r"reiterat\w+\b.{0,40}\b(?:guid\w*|outlook|forecast)", re.I),
        "SPECIFIC_MAINTAINED",
    ),
    (
        re.compile(r"reaffirm\w*\b.{0,40}\b(?:guid\w*|outlook|forecast)", re.I),
        "SPECIFIC_MAINTAINED",
    ),
    (
        re.compile(r"maintain\w+\b.{0,40}\b(?:guid\w*|outlook|forecast)", re.I),
        "SPECIFIC_MAINTAINED",
    ),
    (
        re.compile(
            r"on\s+track\s+to\s+(?:achieve|deliver|meet)\s+(?:our\s+)?(?:full.?year|annual)", re.I
        ),
        "SPECIFIC_MAINTAINED",
    ),
    # DIRECTIONAL
    (
        re.compile(
            r"expect\s+(?:revenue|sales|earnings|eps)\s+(?:to\s+)?(?:grow|increas|expand)", re.I
        ),
        "DIRECTIONAL",
    ),
    # "we expect [data center] revenue [...] to grow/continue/deliver/be up/down/flat" —
    # allows intervening words (including hyphenated tokens) between subject and verb.
    (
        re.compile(
            r"expect\s+(?:\S+\s+){0,6}?(?:revenue|sales|earnings|eps|business|growth|guid\w*)"
            r"\s+(?:\S+\s+){0,6}?(?:grow|increas|expand|continu|deliver|be\s+(?:up|down|flat|stronger))",
            re.I,
        ),
        "DIRECTIONAL",
    ),
    # "Looking ahead [to the next quarter], we expect ..."
    (
        re.compile(
            r"looking\s+ahead\b.{0,80}?\bexpect\b.{0,60}?(?:revenue|growth|sales|guid\w*|forecast)",
            re.I,
        ),
        "DIRECTIONAL",
    ),
    # "forecast to grow X%" / "forecast to deliver $X"
    (
        re.compile(
            r"forecast\w*\s+to\s+(?:grow|deliver|generate|reach|exceed|expand|increas)", re.I
        ),
        "DIRECTIONAL",
    ),
    # Explicit dollar-range quarterly guidance: "for the second quarter, we expect revenue
    # between $2,550 million and $2,650 million" — most concrete forward visibility form.
    (
        re.compile(
            r"(?:for\s+the\s+)?(?:second|third|fourth|next|first)\s+quarter"
            r".{0,60}?(?:we\s+)?expect\s+(?:revenue|sales|eps|earnings).{0,40}?"
            r"(?:between|\$\s*\d|range\s+of)",
            re.I,
        ),
        "SPECIFIC_MAINTAINED",
    ),
    # "third/next quarter guidance reflect" — acknowledges issuing forward guidance
    (
        re.compile(r"(?:third|fourth|next|second)\s+quarter\s+guid\w+", re.I),
        "DIRECTIONAL",
    ),
    # "at the midpoint of guidance / forecast / range"
    (
        re.compile(r"midpoint\s+of\s+(?:our\s+)?(?:guid\w*|forecast|range|outlook)", re.I),
        "DIRECTIONAL",
    ),
    (
        re.compile(r"anticipat\w+\s+(?:continued\s+)?(?:growth|increas|expansion)", re.I),
        "DIRECTIONAL",
    ),
    (
        re.compile(r"target\w*\s+(?:revenue|earnings|eps|sales)\s+(?:of|range|between|\$)", re.I),
        "DIRECTIONAL",
    ),
]


# ---------------------------------------------------------------------------
# v7.3.4 pure scoring functions — exported for unit tests
# ---------------------------------------------------------------------------


def _score_revenue_growth_v2(yoy: float) -> float:
    """Map YoY revenue growth (decimal fraction) to a 0-100 score.

    Bands: >40%→100, 30-40%→92, 20-30%→85, 15-20%→78, 10-15%→70,
           5-10%→60, 0-5%→45, <0→20.
    Input is decimal: 0.29 = 29%.
    """
    if yoy > 0.40:
        return 100.0
    if yoy >= 0.30:
        return 92.0
    if yoy >= 0.20:
        return 85.0
    if yoy >= 0.15:
        return 78.0
    if yoy >= 0.10:
        return 70.0
    if yoy >= 0.05:
        return 60.0
    if yoy >= 0.0:
        return 45.0
    return 20.0


def _score_gross_margin_trend_v2(bps: float) -> float:
    """Map YoY gross margin change (basis points) to a 0-100 score.

    Bands: >300→100, 100-300→85, 50-100→70, flat ±50→60,
           contracting 50-100→45, 100-300→30, >300→15.
    """
    if bps > 300.0:
        return 100.0
    if bps >= 100.0:
        return 85.0
    if bps > 50.0:
        return 70.0
    if bps >= -50.0:
        return 60.0
    if bps >= -100.0:
        return 45.0
    if bps >= -300.0:
        return 30.0
    return 15.0


def _score_eps_consistency_4q(beats: int, quarters_available: int) -> float:
    """Map EPS beat count over 4Q (or limited history) to a 0-100 score.

    Full 4Q: 4→100, 3→80, 2→55, 1→30, 0→0.
    Limited history (<4Q): map beat_rate to the same bands proportionally.
    """
    if quarters_available <= 0:
        return 0.0
    if quarters_available < 4:
        beat_rate = beats / quarters_available
        if beat_rate >= 1.0:
            return 100.0
        if beat_rate >= 0.75:
            return 80.0
        if beat_rate >= 0.5:
            return 55.0
        if beat_rate >= 0.25:
            return 30.0
        return 0.0
    clamped = max(0, min(4, beats))
    return {4: 100.0, 3: 80.0, 2: 55.0, 1: 30.0, 0: 0.0}[clamped]


def _score_guidance_reliability(delivered: int) -> float:
    """Map 4Q guidance delivery count to a 0-100 score.

    4→100, 3→80, 2→55, 1→30, 0→0.
    DATA_GAP default (10) is applied by score_f2(), not here.
    """
    clamped = max(0, min(4, delivered))
    return {4: 100.0, 3: 80.0, 2: 55.0, 1: 30.0, 0: 0.0}[clamped]


def _score_guidance_from_eps_proxy(beats: int, quarters_available: int) -> float:
    """Proxy for SF4 guidance reliability derived from EPS beat consistency.

    Used when Bloomberg guidance data is unavailable.  Consistent EPS beats
    indicate the company is reliably meeting (or guiding conservatively toward)
    analyst expectations — a reasonable stand-in for delivery on guidance.

    Beat rate ≥100% (all available quarters beaten) → 100
    Beat rate  ≥75%                                 →  80
    Beat rate  ≥50%                                 →  55
    Beat rate  ≥25%                                 →  30
    Beat rate   <25%                                →   0

    Minimum 2 quarters required; returns None for fewer (triggers data gap).
    """
    if quarters_available < 2:
        return _DATA_GAP_GUIDANCE_SCORE
    beat_rate = beats / quarters_available
    if beat_rate >= 1.0:
        return 100.0
    if beat_rate >= 0.75:
        return 80.0
    if beat_rate >= 0.50:
        return 55.0
    if beat_rate >= 0.25:
        return 30.0
    return 0.0


def _score_forward_visibility(label: str) -> int:
    """Map forward visibility label to an integer score.

    SPECIFIC_RAISED→100, SPECIFIC_MAINTAINED→80, DIRECTIONAL→60,
    VAGUE_NONE→30, WITHDRAWN_REDUCED→0.
    Unknown labels default to VAGUE_NONE (30).
    """
    return _FWD_VIS_SCORES.get(label, 30)


def _classify_forward_visibility_from_transcript(text: str) -> str:
    """Classify forward visibility from an earnings-call transcript string.

    Scans patterns in priority order (WITHDRAWN_REDUCED checked before RAISED).
    Returns 'VAGUE_NONE' when no pattern fires or text is empty.
    """
    for pattern, label in _FWD_VIS_PATTERNS:
        if pattern.search(text):
            return label
    return "VAGUE_NONE"


def score_f2(
    ticker: str,
    revenue_growth_yoy: float,
    gross_margin_current: float,
    gross_margin_prior_year: float,
    eps_beats_last_4q: int,
    eps_quarters_available: int,
    guidance_reliability_4q: int | None,
    guidance_data_available: bool,
    forward_visibility_score: int,
    net_income_ttm: float,
    current_price: float = 0.0,
    analyst_target: float = 0.0,
) -> EarningsResponse:
    """Compute the v7.3.4 F2 Earnings Quality score.  Pure function — no I/O.

    Parameters
    ----------
    ticker:
        Ticker symbol.
    revenue_growth_yoy:
        YoY revenue growth as decimal fraction (0.29 = 29%).
    gross_margin_current:
        Most recent quarter gross margin as decimal ratio (0.45 = 45%).
    gross_margin_prior_year:
        Same quarter prior year gross margin as decimal ratio.
    eps_beats_last_4q:
        Number of EPS beats in the last 4 quarters.
    eps_quarters_available:
        How many quarters of EPS data are available (max 4).
    guidance_reliability_4q:
        Number of quarters guidance was delivered/met (0-4), or None if unavailable.
    guidance_data_available:
        False when Bloomberg data is unavailable (DATA_GAP → sf4 defaults to 10).
    forward_visibility_score:
        Pre-scored integer (0/30/60/80/100) from transcript NLP.
    net_income_ttm:
        Trailing 12-month net income.  Negative triggers pre-profitability mode.
    current_price:
        Current stock price (used for exit_flag calculation).
    analyst_target:
        Analyst consensus price target (used for exit_flag calculation).
    """
    # Pre-profitability: net income TTM < 0
    pre_profit_status = net_income_ttm < 0.0

    # sf1 — Revenue Growth
    sf1_score = _score_revenue_growth_v2(revenue_growth_yoy)
    sf1_pct = round(revenue_growth_yoy * 100, 2)

    # sf2 — Gross Margin Trend (bps)
    gm_trend_bps = (gross_margin_current - gross_margin_prior_year) * 10_000.0
    sf2_score = _score_gross_margin_trend_v2(gm_trend_bps)

    # sf3 — EPS Beat Consistency (excluded when pre-profit)
    if pre_profit_status:
        sf3_score: float | None = None
        sf3_excluded = True
    else:
        sf3_score = _score_eps_consistency_4q(eps_beats_last_4q, eps_quarters_available)
        sf3_excluded = False

    # sf4 — Guidance Reliability (DATA_GAP default = 10)
    sf4_data_gap = not guidance_data_available
    if guidance_data_available and guidance_reliability_4q is not None:
        sf4_score = _score_guidance_reliability(guidance_reliability_4q)
        sf4_data_gap = False
    else:
        sf4_score = _DATA_GAP_GUIDANCE_SCORE
        sf4_data_gap = True

    # sf5 — Forward Visibility
    sf5_score = float(forward_visibility_score)
    sf5_label = _FWD_VIS_SCORE_TO_LABEL.get(forward_visibility_score, "VAGUE_NONE")

    # Limited / IPO history
    ipo_limited_history = eps_quarters_available < 4
    limited_history = ipo_limited_history

    # Weighted composite
    if pre_profit_status:
        f2_raw = (
            sf1_score * _W_SF1_PP
            + sf2_score * _W_SF2_PP
            + sf4_score * _W_SF4_PP
            + sf5_score * _W_SF5_PP
        )
        pre_profit_reweighted = True
    else:
        assert sf3_score is not None
        f2_raw = (
            sf1_score * _W_SF1
            + sf2_score * _W_SF2
            + sf3_score * _W_SF3
            + sf4_score * _W_SF4
            + sf5_score * _W_SF5
        )
        pre_profit_reweighted = False

    f2_contribution = f2_raw * _W_F2
    f2_score_int = min(100, max(0, round(f2_raw)))
    f2_grade = _grade_from_total(f2_score_int)

    # Flags
    data_gap_applied = sf4_data_gap
    guidance_concern = sf4_score == 0.0 and sf5_score == 0.0

    if current_price > 0.0 and analyst_target > 0.0:
        pvt = (current_price - analyst_target) / analyst_target
        exit_flag = (revenue_growth_yoy < 0.0) and (pvt > 0.20)
    else:
        exit_flag = False

    breakdown: dict[str, Any] = {
        "sf1_revenue_growth_pct": sf1_pct,
        "sf1_score": sf1_score,
        "sf2_gross_margin_trend_bps": round(gm_trend_bps, 1),
        "sf2_score": sf2_score,
        "sf3_eps_beats": eps_beats_last_4q if not sf3_excluded else None,
        "sf3_quarters_available": eps_quarters_available,
        "sf3_score": sf3_score,
        "sf3_excluded": sf3_excluded,
        "sf4_guidance_delivered": guidance_reliability_4q,
        "sf4_score": sf4_score,
        "sf4_data_gap": sf4_data_gap,
        "sf5_forward_visibility_label": sf5_label,
        "sf5_score": sf5_score,
        "f2_raw": f2_raw,
        "f2_contribution": f2_contribution,
        "pre_profit_status": pre_profit_status,
        "weights_used": "pre_profit" if pre_profit_status else "normal",
    }

    return EarningsResponse(
        ticker=ticker.upper(),
        sf1_revenue_growth_pct=sf1_pct,
        sf1_score=sf1_score,
        sf2_gross_margin_trend_bps=round(gm_trend_bps, 1),
        sf2_score=sf2_score,
        sf3_eps_beats=eps_beats_last_4q if not sf3_excluded else None,
        sf3_quarters_available=eps_quarters_available,
        sf3_score=sf3_score,
        sf3_excluded=sf3_excluded,
        sf4_guidance_delivered=guidance_reliability_4q,
        sf4_score=sf4_score,
        sf4_data_gap=sf4_data_gap,
        sf5_forward_visibility_label=sf5_label,
        sf5_score=sf5_score,
        f2_raw=f2_raw,
        f2_contribution=f2_contribution,
        f2_score=f2_score_int,
        f2_grade=f2_grade,
        pre_profit_status=pre_profit_status,
        pre_profit_reweighted=pre_profit_reweighted,
        data_gap_applied=data_gap_applied,
        guidance_concern=guidance_concern,
        exit_flag=exit_flag,
        limited_history=limited_history,
        ipo_limited_history=ipo_limited_history,
        data_available=True,
        is_pre_profitability=pre_profit_status,
        breakdown=breakdown,
    )


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
        quarterly_revenues = self._extract_quarterly_revenues(income_data)
        yoy_pct = self._compute_yoy_revenue_growth(quarterly_revenues)
        yoy_decimal = (yoy_pct / 100.0) if yoy_pct is not None else 0.0

        # ---- Gross Margin Trend (YoY bps) ----
        gm_current, gm_prior = self._extract_gross_margin_yoy_ratios(income_data)
        if gm_current is None or gm_prior is None:
            gm_current, gm_prior = 0.50, 0.50  # neutral → 0 bps

        # ---- EPS Beat Consistency (4Q) ----
        eps_beats, eps_avail = self._count_eps_beats(earnings_data)

        # ---- Forward Visibility from transcript ----
        fwd_vis_label = _classify_forward_visibility_from_transcript(transcript_text)
        fwd_vis_score = _score_forward_visibility(fwd_vis_label)

        # ---- Guidance Reliability proxy (EPS beats as stand-in for Bloomberg) ----
        # When EPS data is available for ≥2 quarters, derive a guidance reliability
        # proxy from the beat rate.  This fills the Bloomberg data gap with real data.
        _guidance_proxy_score = _score_guidance_from_eps_proxy(eps_beats, eps_avail)
        _guidance_data_available = (
            eps_avail >= 2 and _guidance_proxy_score != _DATA_GAP_GUIDANCE_SCORE
        )
        # Convert proxy score back to a 0-4 integer for score_f2 compatibility.
        # Use the same beat count directly since score_f2 → _score_guidance_reliability
        # maps integer delivered count; but the proxy already returns the right score,
        # so we pass guidance_reliability_4q=None and override via guidance_data_available.
        # Instead, we bypass the int-count path by using a pre-scored value injected
        # through a dedicated field.  We achieve this by mapping the proxy float back
        # to a delivered-quarters integer (conservative: floor).
        _guidance_delivered_proxy: int | None = None
        if _guidance_data_available:
            _score_to_delivered = {100.0: 4, 80.0: 3, 55.0: 2, 30.0: 1, 0.0: 0}
            _guidance_delivered_proxy = _score_to_delivered.get(
                _guidance_proxy_score, None
            )
            if _guidance_delivered_proxy is None:
                _guidance_data_available = False

        # ---- Net Income TTM ----
        net_income_ttm = self._compute_net_income_ttm(income_data)
        if net_income_ttm is None:
            net_income_ttm = 1.0  # no data → treat as profitable (neutral)

        # ---- Compute F2 score ----
        result = score_f2(
            ticker=ticker,
            revenue_growth_yoy=yoy_decimal,
            gross_margin_current=gm_current,
            gross_margin_prior_year=gm_prior,
            eps_beats_last_4q=eps_beats,
            eps_quarters_available=eps_avail,
            guidance_reliability_4q=_guidance_delivered_proxy,
            guidance_data_available=_guidance_data_available,
            forward_visibility_score=fwd_vis_score,
            net_income_ttm=net_income_ttm,
        )
        return result.model_copy(update={"data_available": av_data_available})

    # ------------------------------------------------------------------
    # Private network helpers
    # ------------------------------------------------------------------

    async def _fetch_income_statement(self, ticker: str) -> dict[str, object]:
        """Fetch quarterly income statement from AV; falls back to Polygon on failure."""
        data = await fetch_alpha_vantage_cached(
            self._client,
            api_key=self._api_key,
            function="INCOME_STATEMENT",
            symbol=ticker,
            timeout=15.0,
        )
        if data:
            return data
        logger.debug("AV INCOME_STATEMENT unavailable for %s — trying Polygon", ticker)
        return await self._fetch_income_statement_polygon(ticker)

    async def _fetch_earnings(self, ticker: str) -> dict[str, object]:
        """Fetch quarterly EPS history from AV; falls back to FMP on failure."""
        data = await fetch_alpha_vantage_cached(
            self._client,
            api_key=self._api_key,
            function="EARNINGS",
            symbol=ticker,
            timeout=15.0,
        )
        if data:
            return data
        logger.debug("AV EARNINGS unavailable for %s — trying FMP", ticker)
        return await self._fetch_earnings_fmp(ticker)

    async def _fetch_income_statement_polygon(self, ticker: str) -> dict[str, object]:
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
                    financials.get("income_statement", {}) if isinstance(financials, dict) else {}
                )
                rev_entry = income.get("revenues", {}) if isinstance(income, dict) else {}
                gp_entry = income.get("gross_profit", {}) if isinstance(income, dict) else {}
                rev_val = rev_entry.get("value") if isinstance(rev_entry, dict) else None
                gp_val = gp_entry.get("value") if isinstance(gp_entry, dict) else None
                quarterly_reports.append(
                    {
                        "totalRevenue": (str(int(rev_val)) if rev_val is not None else "None"),
                        "grossProfit": (str(int(gp_val)) if gp_val is not None else "None"),
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
                        "reportedEPS": (str(eps_actual) if eps_actual is not None else "None"),
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
                        ticker.upper(),
                        slot_year,
                        slot_quarter,
                        year,
                        quarter,
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

    @staticmethod
    def _extract_gross_margin_yoy_ratios(
        income_data: dict,  # type: ignore[type-arg]
    ) -> tuple[float | None, float | None]:
        """Return (current_quarter_gm_ratio, prior_year_same_quarter_gm_ratio).

        Compares reports[0] (most recent) with reports[4] (4 quarters prior).
        Returns (None, None) when insufficient data.

        Anomaly guard: some data providers (AV, FMP) occasionally mis-classify
        D&A as part of COGS for a single quarter, producing a grossProfit that
        is drastically lower than surrounding quarters.  If the current quarter
        GM deviates by more than 20 percentage points from the median of the 3
        preceding quarters (reports[1:4]), the current value is replaced with
        that median before computing the YoY delta.
        """
        reports: list[dict] = income_data.get("quarterlyReports", [])  # type: ignore[type-arg]

        def _gm_ratio(r: dict) -> float | None:  # type: ignore[type-arg]
            gp_raw = r.get("grossProfit", "None")
            rev_raw = r.get("totalRevenue", "None")
            if gp_raw in ("None", "N/A", "") or rev_raw in ("None", "N/A", ""):
                return None
            try:
                gp, rev = float(gp_raw), float(rev_raw)
                return gp / rev if rev != 0.0 else None
            except ValueError:
                return None

        current = _gm_ratio(reports[0]) if len(reports) >= 1 else None
        prior_year = _gm_ratio(reports[4]) if len(reports) >= 5 else None

        # Anomaly guard: replace current GM only when it drops >20pp BELOW the
        # median of the 3 preceding quarters.  This catches the specific provider
        # bug where D&A is mis-classified as part of COGS for a single quarter,
        # producing an artificially low grossProfit.  Upward deviations are left
        # untouched — genuine margin expansion (e.g. spinoffs, restructurings) is
        # a real business event, not a data error.
        if current is not None and len(reports) >= 4:
            recent = [_gm_ratio(reports[i]) for i in range(1, 4)]
            recent_valid = sorted(x for x in recent if x is not None)
            if recent_valid:
                recent_median = recent_valid[len(recent_valid) // 2]
                if recent_median - current > 0.20:
                    logger.warning(
                        "SF2 anomaly: current GM %.1f%% is >20pp below "
                        "recent median %.1f%% — using median as corrected value",
                        current * 100,
                        recent_median * 100,
                    )
                    current = recent_median

        return current, prior_year

    @staticmethod
    def _compute_net_income_ttm(
        income_data: dict,  # type: ignore[type-arg]
    ) -> float | None:
        """Sum net income over the last 4 quarters (TTM).

        Returns None when no valid data is found.
        """
        reports: list[dict] = income_data.get("quarterlyReports", [])  # type: ignore[type-arg]
        total = 0.0
        count = 0
        for r in reports[:4]:
            ni_raw = r.get("netIncome", "None")
            if ni_raw in ("None", "N/A", "", None):
                continue
            try:
                total += float(str(ni_raw))
                count += 1
            except ValueError:
                pass
        return total if count > 0 else None
