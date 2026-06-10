"""Forward Growth Score (FGS) — pure scoring engine.

FGS is a parallel axis to the ATLAS conviction score. F5 measures *survivability*
("can this company survive and compound?"); FGS measures *forward growth potential*
("can it grow much faster than the market expects if the thesis works?").

FGS is NEVER blended into the raw ATLAS score — it is a separate display + the
input to the F5 x FGS x F4 action matrix (see ``classify_bucket``). It contains no
valuation, no price/RSI/extension (that is the Entry Overlay) and no options flow /
dark pool (that is F4) — avoiding double-counting.

Phase 1 (this module) computes only the two data-grounded sub-factors:
  * G1 revenue acceleration — from quarterly revenue (Alpha Vantage),
  * G5 TAM / bottleneck status — from a curated wave lookup (Section 8 roadmap).
G2 (backlog), G3 (customer quality) and G4 (product ramp) are optional operator
overrides that default to a neutral 50 (DATA_GAP) until a Phase-2 NLP engine or
manual inputs supply them — a missing axis must not tank the score.

All functions here are pure (no I/O); the service owns the Alpha Vantage fetch.
"""

from __future__ import annotations

import re
from typing import Final

# ---------------------------------------------------------------------------
# Grades & buckets
# ---------------------------------------------------------------------------


class FgsGrade:
    ELITE: Final[str] = "ELITE"
    HIGH: Final[str] = "HIGH"
    MODERATE: Final[str] = "MODERATE"
    LOW: Final[str] = "LOW"


class GrowthBucket:
    """F5 x FGS x F4 action-matrix buckets."""

    CORE_COMPOUNDER: Final[str] = "CORE_COMPOUNDER"
    QUALITY_HOLD: Final[str] = "QUALITY_HOLD"
    GROWTH_TACTICAL: Final[str] = "GROWTH_TACTICAL"
    STORY_RISK: Final[str] = "STORY_RISK"
    AVOID: Final[str] = "AVOID"


# Neutral default for un-instrumented sub-factors (DATA_GAP).
NEUTRAL_SCORE: Final[int] = 50

# Matrix thresholds.
_F5_HIGH_MIN: Final[int] = 70      # F5 >= 70 → durable
_FGS_HIGH_MIN: Final[int] = 75     # FGS >= 75 → strong forward growth
_F4_CONFIRMING_MIN: Final[int] = 60  # F4 >= 60 → BUY/STRONG BUY confirming

# FGS grade bands.
_GRADE_ELITE_MIN: Final[int] = 85
_GRADE_HIGH_MIN: Final[int] = 70
_GRADE_MODERATE_MIN: Final[int] = 50


# ---------------------------------------------------------------------------
# G1 — Revenue acceleration
# ---------------------------------------------------------------------------


def score_revenue_acceleration(
    revenues_newest_first: list[float],
    *,
    guidance_raised: bool | None = None,
) -> tuple[int | None, float | None, bool | None]:
    """Score forward revenue momentum from quarterly revenue.

    ``revenues_newest_first`` is the quarterly revenue series, most-recent first.
    Computes year-over-year growth (this quarter vs the same quarter a year ago)
    and whether that YoY rate is *accelerating* vs the prior quarter's YoY.

    Returns ``(score, yoy_pct, accelerating)``.  Returns ``(None, None, None)``
    when fewer than 5 quarters are available (cannot compute a YoY rate).

    ``guidance_raised`` (reuse F2's guidance assessment) nudges the score +/-5.
    """
    revs = [float(r) for r in revenues_newest_first]
    if len(revs) < 5 or revs[4] <= 0:
        return None, None, None

    yoy = (revs[0] - revs[4]) / revs[4] * 100.0

    # Base score from the YoY growth band.
    if yoy > 50.0:
        base = 90
    elif yoy > 30.0:
        base = 75
    elif yoy > 15.0:
        base = 60
    elif yoy > 5.0:
        base = 45
    elif yoy >= 0.0:
        base = 35
    else:
        base = 20

    # Acceleration: is YoY growth speeding up vs the prior quarter's YoY?
    accelerating: bool | None = None
    if len(revs) >= 6 and revs[5] > 0:
        prior_yoy = (revs[1] - revs[5]) / revs[5] * 100.0
        accelerating = yoy > prior_yoy
        base += 10 if accelerating else -10

    if guidance_raised is True:
        base += 5
    elif guidance_raised is False:
        base -= 5

    return max(0, min(100, base)), round(yoy, 2), accelerating


# ---------------------------------------------------------------------------
# G5 — TAM / bottleneck status (curated; Section 8 Bottleneck Roadmap)
# ---------------------------------------------------------------------------

# Wave → (label, status, score). Scores reflect how scarce / mission-critical the
# layer is right now. Curated and editable — refresh as the cycle moves.
_WAVE_INFO: Final[dict[str, tuple[str, str, int]]] = {
    "GPU": ("GPU / Compute", "PRICED_IN", 60),
    "MEMORY": ("Memory / HBM", "ACTIVE", 85),
    "OPTICS": ("Optics / CPO / Photonics", "ACTIVE", 95),
    "POWER": ("Power / Thermal", "FORMING", 90),
    "GRID": ("Grid / Energy", "EARLY", 80),
    "CUSTOM_SILICON": ("Custom Silicon / ASIC", "ONGOING", 75),
    "SEMICAP": ("Semicap / WFE", "ACTIVE", 85),
    "FOUNDRY": ("Foundry", "ACTIVE", 80),
}

# Curated ticker → wave map (AI-infrastructure universe). Unknown → DATA_GAP.
_TICKER_WAVE: Final[dict[str, str]] = {
    # Optics / CPO
    "LITE": "OPTICS", "COHR": "OPTICS", "CIEN": "OPTICS", "CRDO": "OPTICS",
    "AAOI": "OPTICS", "FN": "OPTICS", "POET": "OPTICS",
    # Memory / HBM
    "MU": "MEMORY", "SNDK": "MEMORY",
    # Custom silicon / ASIC
    "MRVL": "CUSTOM_SILICON", "AVGO": "CUSTOM_SILICON",
    # Power / thermal
    "VRT": "POWER", "VICR": "POWER", "NVT": "POWER", "ETN": "POWER",
    # Grid / energy / nuclear
    "GEV": "GRID", "CEG": "GRID", "OKLO": "GRID",
    # Semicap / WFE
    "AMAT": "SEMICAP", "LRCX": "SEMICAP", "KLAC": "SEMICAP", "ASML": "SEMICAP",
    # Foundry
    "TSM": "FOUNDRY", "TSEM": "FOUNDRY",
    # GPU
    "NVDA": "GPU", "AMD": "GPU",
}


# ---------------------------------------------------------------------------
# Transcript signal extraction (G2 backlog, G3 customer quality, G4 ramp)
# ---------------------------------------------------------------------------
#
# Heuristic keyword/regex scoring over the earnings-call transcript we already
# fetch from FMP. These are coarse proxies — the `source` is reported as
# "transcript" so callers know the score is heuristic, not a clean field. Each
# returns a 0-100 score, or None when no relevant signal is present (→ DATA_GAP,
# so absence of mention is treated as unknown, never as a penalty).

_RAMP_GROWTH_WORDS: Final[tuple[str, ...]] = (
    "grew", "growing", "increased", "increasing", "expand", "building",
    "design win", "design-win", "bookings", "record",
)
_BACKLOG_STRONG: Final[tuple[str, ...]] = (
    "sold out", "sold-out", "fully booked", "record backlog", "multi-year agreement",
)
_BACKLOG_MODERATE: Final[tuple[str, ...]] = (
    "backlog", "bookings", "design win", "design-win", "order book",
    "committed capacity", "contractual minimum", "purchase commitment",
)
# "$1.2 billion backlog" / "backlog of $324 million" etc.
_DOLLAR_BACKLOG_RE: Final[re.Pattern[str]] = re.compile(
    r"(\$\s?\d[\d.,]*\s?(?:billion|million|bn|m|b)?[^.\n]{0,40}\b(?:backlog|orders|bookings)\b"
    r"|\b(?:backlog|bookings|orders)\b[^.\n]{0,25}\$\s?\d)",
    re.IGNORECASE,
)

_HYPERSCALER_TERMS: Final[tuple[str, ...]] = ("hyperscaler", "hyperscale")
_NAMED_CUSTOMERS: Final[tuple[str, ...]] = (
    "nvidia", "microsoft", "azure", "amazon", "aws", "google", "alphabet",
    "meta", "tesla", "apple", "broadcom", "oracle", "openai", "tsmc",
)
_CONCENTRATION_TERMS: Final[tuple[str, ...]] = (
    "10% customer", "largest customer", "customer concentration", "top customer",
)

_RAMP_INFLECTION: Final[tuple[str, ...]] = (
    "inflection", "volume ramp", "production ramp", "significantly larger ramp",
    "accelerating ramp", "steep ramp",
)
_NEXTGEN_PRODUCTS: Final[tuple[str, ...]] = (
    "1.6t", "800g", "cpo", "co-packaged", "hbm4", "hbm3e", "cowos",
    "2nm", "gaa", "blackwell", "rubin", "400g",
)


def _any(text: str, terms: tuple[str, ...]) -> bool:
    return any(t in text for t in terms)


def score_backlog_signal(transcript: str) -> int | None:
    """G2 — backlog / bookings / sold-out language from the transcript."""
    if not transcript:
        return None
    t = transcript.lower()
    if _any(t, _BACKLOG_STRONG) or _DOLLAR_BACKLOG_RE.search(transcript):
        return 90
    if "backlog" in t and _any(t, _RAMP_GROWTH_WORDS):
        return 78
    if _any(t, _BACKLOG_MODERATE):
        return 65
    return None


def score_customer_quality_signal(transcript: str) -> int | None:
    """G3 — named hyperscaler / blue-chip customer quality from the transcript."""
    if not transcript:
        return None
    t = transcript.lower()
    quality = sum(1 for n in _NAMED_CUSTOMERS if n in t) + (1 if _any(t, _HYPERSCALER_TERMS) else 0)
    if quality >= 2:
        return 90
    if quality == 1:
        return 78
    if _any(t, _CONCENTRATION_TERMS):
        return 62  # concentration acknowledged, but no named-quality signal
    return None


def score_product_ramp_signal(transcript: str) -> int | None:
    """G4 — product ramp / inflection language from the transcript."""
    if not transcript:
        return None
    t = transcript.lower()
    has_ramp = "ramp" in t
    has_nextgen = _any(t, _NEXTGEN_PRODUCTS)
    if _any(t, _RAMP_INFLECTION) or (has_ramp and has_nextgen):
        return 90
    if has_ramp:
        return 78
    if has_nextgen:
        return 65
    return None


def score_backlog_from_rpo(rpo_usd: float | None, ttm_revenue: float | None) -> int | None:
    """Score G2 from an exact remaining-performance-obligation (backlog) figure.

    Scored on backlog *coverage* — RPO as a multiple of trailing revenue:
      >= 1.0x revenue → 95   (more than a year of contracted demand booked)
      0.5-1.0x        → 85
      0.25-0.5x       → 75
      < 0.25x         → 60
    Returns None when either input is missing/zero (caller falls back).
    """
    if rpo_usd is None or rpo_usd <= 0 or ttm_revenue is None or ttm_revenue <= 0:
        return None
    coverage = rpo_usd / ttm_revenue
    if coverage >= 1.0:
        return 95
    if coverage >= 0.5:
        return 85
    if coverage >= 0.25:
        return 75
    return 60


def concentration_quality_cap(largest_customer_pct: float | None) -> int | None:
    """Cap G3 customer quality when a single customer dominates revenue.

    A named blue-chip customer is a quality positive, but extreme single-customer
    dependence is a fragility risk that should bound the quality score:
      >= 50% one customer → cap 60
      40-50%              → cap 72
    Returns None (no cap) below 40% or when unknown.
    """
    if largest_customer_pct is None:
        return None
    if largest_customer_pct >= 50.0:
        return 60
    if largest_customer_pct >= 40.0:
        return 72
    return None


def lookup_tam_bottleneck(ticker: str) -> tuple[int, str, str]:
    """Return ``(score, wave_label, status)`` for a ticker's bottleneck wave.

    Unknown tickers return ``(NEUTRAL_SCORE, "UNCLASSIFIED", "UNKNOWN")`` so the
    caller can flag a DATA_GAP rather than penalise the name.
    """
    wave = _TICKER_WAVE.get(ticker.upper())
    if wave is None:
        return NEUTRAL_SCORE, "UNCLASSIFIED", "UNKNOWN"
    label, status, score = _WAVE_INFO[wave]
    return score, label, status


# ---------------------------------------------------------------------------
# Composite & grade
# ---------------------------------------------------------------------------


def compute_fgs(instrumented_scores: list[int]) -> int:
    """Composite over the *instrumented* sub-factors only (equal-weighted mean).

    Un-instrumented (DATA_GAP) sub-factors are EXCLUDED rather than averaged in as
    a neutral 50 — otherwise, in Phase 1 (only G1 + G5 measured), a genuine
    high-flyer's three gaps would drag the score to the middle and the score
    could never reach "high", making the action matrix useless. Excluding gaps
    means FGS reflects "of what we can measure, how strong is forward growth",
    with the ``data_gaps`` list / confidence % communicating the partial basis.

    Returns ``NEUTRAL_SCORE`` (50) when nothing is instrumented.
    """
    if not instrumented_scores:
        return NEUTRAL_SCORE
    return max(0, min(100, round(sum(instrumented_scores) / len(instrumented_scores))))


def confidence_pct(instrumented_count: int, total: int = 5) -> int:
    """Share of FGS sub-factors backed by real data (0-100)."""
    if total <= 0:
        return 0
    return round(instrumented_count / total * 100)


def fgs_grade(score: int) -> str:
    if score >= _GRADE_ELITE_MIN:
        return FgsGrade.ELITE
    if score >= _GRADE_HIGH_MIN:
        return FgsGrade.HIGH
    if score >= _GRADE_MODERATE_MIN:
        return FgsGrade.MODERATE
    return FgsGrade.LOW


# ---------------------------------------------------------------------------
# Action matrix — F5 (survivability) x FGS (growth) x F4 (flow)
# ---------------------------------------------------------------------------


def classify_bucket(
    f5_score: int | None,
    fgs_score: int,
    f4_score: int | None,
) -> tuple[str | None, str | None]:
    """Map (F5, FGS, F4) to an action bucket + plain-English action.

    Returns ``(bucket, action)``; ``(None, None)`` when F5 is unavailable (the
    matrix needs a survivability read). F4 may be None (treated as not-confirming).
    """
    if f5_score is None:
        return None, None

    f5_high = f5_score >= _F5_HIGH_MIN
    fgs_high = fgs_score >= _FGS_HIGH_MIN
    f4_confirming = f4_score is not None and f4_score >= _F4_CONFIRMING_MIN

    if f5_high and fgs_high:
        action = (
            "Best names — add on pullbacks"
            if f4_confirming
            else "Core quality — wait for flow (F4) confirmation"
        )
        return GrowthBucket.CORE_COMPOUNDER, action

    if f5_high and not fgs_high:
        return GrowthBucket.QUALITY_HOLD, "Good company, limited upside — hold"

    if not f5_high and fgs_high:
        if f4_confirming:
            return (
                GrowthBucket.GROWTH_TACTICAL,
                "High-flyer potential — tactical, size-capped (flow confirming)",
            )
        return (
            GrowthBucket.STORY_RISK,
            "Tempting but dangerous — story strong, flow not confirming; watch only",
        )

    return GrowthBucket.AVOID, "No edge — avoid"
