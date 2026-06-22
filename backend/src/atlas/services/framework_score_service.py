"""Framework Score service — aggregates F1-F5 into a single conviction score.

Formula (Factor_Mapping_Guide §Final Score):
  Raw Total   = (F1 x 0.20) + (F2 x 0.25) + (F3 x 0.15) + (F4 x 0.15) + (F5 x 0.25)
  Final Score = round(Raw Total), clamped [0, 100]

  Maximum raw total = 100 (all factors at 100, weights sum to 1.00).

All pure helpers (_map_action, _compute_raw_total, _compute_final_score) are
side-effect-free and unit-testable without mocks.

The ``FrameworkScoreService`` class orchestrates all five sub-services
concurrently via ``asyncio.gather``.  Any sub-service failure (missing key,
network error) falls back to a neutral factor score of 50 and records a flag
message rather than aborting the entire request.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

import httpx

from atlas.core.scoring import classify_tier
from atlas.schemas.analyst import AnalystResponse
from atlas.schemas.earnings import EarningsResponse
from atlas.schemas.framework9 import Framework9Result
from atlas.schemas.framework_score import (
    EtfBranchComponent,
    EtfBranchMetadata,
    EtfConstituent,
    EtfHedgeInputs,
    FactorBreakdown,
    FrameworkScoreResponse,
    IntlBranchMetadata,
    IntlDataTask,
    IntlFactor,
)
from atlas.schemas.fundamental import FundamentalResponse
from atlas.schemas.momentum import MomentumResponse
from atlas.services.analyst_service import AnalystService
from atlas.services.earnings_service import EarningsService
from atlas.services.framework8_service import Framework8Service
from atlas.services.framework9_service import evaluate_framework9
from atlas.services.fundamental_service import FundamentalService
from atlas.services.intl_data_service import IntlData, IntlDataService, IntlFactorData
from atlas.services.momentum_service import MomentumService
from atlas.services.options_flow_service import f4_framework_row_label
from atlas.services.provider_response_cache import fetch_alpha_vantage_cached

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Framework-level weights (Factor_Mapping_Guide §Final Score)
# ---------------------------------------------------------------------------

# Each factor is scored 0-100; multiplied by its weight to contribute to the
# raw total.  Weights sum to 1.00 (maximum raw total = 100).
_W_F1: Final[float] = 0.20  # Momentum
_W_F2: Final[float] = 0.25  # Earnings Quality
_W_F3: Final[float] = 0.15  # Analyst Sentiment
_W_F4: Final[float] = 0.15  # Options Flow Persistence (SPEC v2.2 rename; math unchanged)
_W_F5: Final[float] = 0.25  # Fundamental Quality

# Neutral fallback score when a factor service is unavailable.
_NEUTRAL_SCORE: Final[int] = 50

_NON_OPERATING_ASSET_TYPES: Final[set[str]] = {
    "ETF",
    "ETN",
    "FUND",
    "MUTUAL FUND",
    "TRUST",
    "INDEX",
}
_POLYGON_TICKER_DETAILS_URL: Final[str] = "https://api.polygon.io/v3/reference/tickers/{ticker}"

_ETF_MOMENTUM_FACTOR_TICKERS: Final[set[str]] = {"SPMO"}
_ETF_LEVERAGED_TACTICAL_TICKERS: Final[set[str]] = {"SOXL", "TQQQ", "NVDL"}
_ETF_HEDGE_PROTECTIVE_TICKERS: Final[set[str]] = {"SOXS", "SQQQ", "PSQ", "SH"}

_ETF_ROUTE_THEMATIC: Final[str] = "THEMATIC_PROXY_ETF"
_ETF_ROUTE_MOMENTUM: Final[str] = "MOMENTUM_FACTOR_ETF"
_ETF_ROUTE_HEDGE: Final[str] = "HEDGE_PROTECTIVE_ETF"
_ETF_ROUTE_LEVERAGED: Final[str] = "LEVERAGED_TACTICAL_ETF"
_ROUTE_EQUITY: Final[str] = "OPERATING_EQUITY"
_ROUTE_INTL: Final[str] = "INTL_OPERATING"

# International / ADR / OTC operating-company routing (INTL-3F). These names must
# NOT be forced through domestic F1-F5: a missing U.S. data feed is a coverage
# gap, not a bad company. Known foreign/OTC operating names that route to INTL-3F
# even when U.S. provider data is empty (so they never fall back to AVOID).
_INTL_KNOWN_TICKERS: Final[set[str]] = {
    "LPKFF",
    "SIVEF",
    "AIXXF",
    "LSRCF",
    "SLOIF",
    "HMDPF",
    "KXIAY",
}
# Polygon types that denote an ADR (foreign company listed in the U.S. via depositary receipt).
_INTL_ADR_TYPES: Final[set[str]] = {"ADRC", "ADRP", "ADRR", "ADRW"}

# INTL-3F factor weights (renormalized over whatever coverage is available).
_INTL_W_I1: Final[float] = 0.50  # Business / forward fundamentals
_INTL_W_I2: Final[float] = 0.30  # Market / momentum / liquidity
_INTL_W_I3: Final[float] = 0.20  # External confirmation

# INTL AVOID gate: only a genuinely weak FUNDAMENTAL read (I1) with real data
# earns an AVOID. A low blended composite from missing flow / thin momentum /
# data gaps caps sizing — it never creates an AVOID label.
_INTL_WEAK_FUNDAMENTAL_MAX: Final[int] = 45

# INTL coverage / status labels (handoff §Required labels).
_INTL_LABEL_OK: Final[str] = "INTL-OK"
_INTL_LABEL_PARTIAL: Final[str] = "INTL-PARTIAL"
_INTL_LABEL_DATA_GAP: Final[str] = "INTL-DATA-GAP"
_INTL_LABEL_OTC_LIQ: Final[str] = "OTC-LIQUIDITY-RISK"
_INTL_LABEL_NO_US_FLOW: Final[str] = "NO-US-FLOW"
_INTL_LABEL_FOREIGN_SRC: Final[str] = "FOREIGN-SOURCE-NEEDED"

_ETF_BRANCH_NON_HEDGE_MIN_SCORE: Final[int] = 50
_ETF_BRANCH_RAW_TOTAL_MAX: Final[float] = 95.0

# Thematic/proxy branch weights (DRAM/SMH/SOXX-style baskets)
_ETF_THEMATIC_W_LOOKTHROUGH: Final[float] = 0.45
_ETF_THEMATIC_W_THEME_CYCLE: Final[float] = 0.25
_ETF_THEMATIC_W_MOMENTUM: Final[float] = 0.10
_ETF_THEMATIC_W_F4_TIMING: Final[float] = 0.10
_ETF_THEMATIC_W_CONFIDENCE: Final[float] = 0.10

# Momentum/factor branch weights (SPMO-style)
_ETF_MOMENTUM_W_MOMENTUM: Final[float] = 0.35
_ETF_MOMENTUM_W_FACTOR_REGIME: Final[float] = 0.25
_ETF_MOMENTUM_W_LOOKTHROUGH_QUALITY: Final[float] = 0.20
_ETF_MOMENTUM_W_F4_TIMING: Final[float] = 0.10
_ETF_MOMENTUM_W_LIQUIDITY: Final[float] = 0.10

# Hedge/protective branch component weights
_ETF_HEDGE_W_EXPOSURE_COVERAGE: Final[float] = 0.30
_ETF_HEDGE_W_UNDERLYING_TREND: Final[float] = 0.20
_ETF_HEDGE_W_VOL_COST: Final[float] = 0.20
_ETF_HEDGE_W_DELTA_DURATION: Final[float] = 0.15
_ETF_HEDGE_W_CORRELATION: Final[float] = 0.10
_ETF_HEDGE_W_MAX_HOLD_DISCIPLINE: Final[float] = 0.05

# Leveraged branch weights
_ETF_LEVERAGED_W_UNDERLYING_SCORE: Final[float] = 0.40
_ETF_LEVERAGED_W_TREND: Final[float] = 0.25
_ETF_LEVERAGED_W_DECAY_PENALTY: Final[float] = 0.15
_ETF_LEVERAGED_W_LIQUIDITY: Final[float] = 0.10
_ETF_LEVERAGED_W_MAX_HOLD_DISCIPLINE: Final[float] = 0.10

_THEMATIC_LABELS: Final[dict[str, str]] = {
    "DRAM": "Memory / HBM proxy basket",
    "SMH": "Semiconductor proxy basket",
    "SOXX": "Semiconductor proxy basket",
}

_THEMATIC_HOLDINGS_DRIVERS: Final[dict[str, str]] = {
    "DRAM": "MU, SNDK, SK Hynix, Samsung, STX, WDC, Kioxia",
}

# Curated look-through constituents per thematic basket: (symbol, approx weight %,
# scored). ``scored`` is True for US-listed operating companies ATLAS can run
# F1-F5 on; False for foreign-listed names (KRX/TSE) the engine does not directly
# score. Weights are approximate/curated — the whole proxy model is curated per
# the ATLAS spec — and are used only to express scored-coverage of the basket.
_THEMATIC_CONSTITUENTS: Final[dict[str, list[tuple[str, float, bool]]]] = {
    "DRAM": [
        ("MU", 20.0, True),
        ("SK Hynix", 18.0, False),
        ("Samsung", 16.0, False),
        ("SNDK", 12.0, True),
        ("STX", 12.0, True),
        ("WDC", 12.0, True),
        ("Kioxia", 10.0, False),
    ],
}

_THEMATIC_LOOKTHROUGH_SCORE_BY_TICKER: Final[dict[str, int]] = {
    # DRAM branch requirement: bullish proxy from memory/HBM holdings basket.
    "DRAM": 76,
    "SMH": 68,
    "SOXX": 67,
}

_LEVERAGED_UNDERLYING_PROXY_SCORE: Final[dict[str, int]] = {
    "SOXL": 70,
    "TQQQ": 68,
    "NVDL": 71,
}

_HEDGE_PROFILE_BY_TICKER: Final[dict[str, tuple[str, str, list[str]]]] = {
    "SOXS": (
        "Protect semiconductor/AI sleeve",
        "SMH",
        ["NVDA", "AVGO", "MU", "MRVL", "ASML", "LRCX", "AMAT"],
    ),
    "SQQQ": (
        "Protect Nasdaq growth sleeve",
        "QQQ",
        ["QQQ", "NVDA", "MSFT", "AAPL", "AMZN", "META", "GOOGL"],
    ),
    "PSQ": (
        "Protect Nasdaq growth sleeve",
        "QQQ",
        ["QQQ", "NVDA", "MSFT", "AAPL", "AMZN", "META", "GOOGL"],
    ),
    "SH": (
        "Protect broad market sleeve",
        "SPY",
        ["SPY", "MSFT", "AAPL", "NVDA", "AMZN", "GOOGL", "META"],
    ),
}


def _clamp_score_0_100(score: float) -> int:
    return max(0, min(100, round(score)))


def _clamp_raw_total(score: float) -> float:
    return max(0.0, min(_ETF_BRANCH_RAW_TOTAL_MAX, round(score, 4)))


def _weighted_score(components: list[tuple[int, float]]) -> int:
    total = sum(component * weight for component, weight in components)
    return _clamp_score_0_100(total)


def _confidence_liquidity_score(momentum_score: int, f4_score: int) -> int:
    # When fundamentals are intentionally N/A for ETFs, use liquid/timing
    # stability proxy to avoid accidental bearish penalties from missing data.
    return _clamp_score_0_100(momentum_score * 0.6 + f4_score * 0.4)


def _thematic_lookthrough_score(ticker: str) -> int:
    return _THEMATIC_LOOKTHROUGH_SCORE_BY_TICKER.get(ticker.upper(), 60)


def _thematic_cycle_score(lookthrough_score: int, momentum_score: int) -> int:
    return _clamp_score_0_100(lookthrough_score * 0.6 + momentum_score * 0.4)


def _thematic_coverage(
    ticker: str,
) -> tuple[list[EtfConstituent], float | None, str | None]:
    """Return (constituents, scored_coverage_pct, note) for a thematic basket.

    Coverage = share of total (curated) basket weight made up of names ATLAS
    directly scores. Returns ([], None, None) when no curated table exists.
    Pure function — no I/O.
    """
    rows = _THEMATIC_CONSTITUENTS.get(ticker.upper())
    if not rows:
        return [], None, None

    constituents = [
        EtfConstituent(
            symbol=symbol,
            weight_pct=weight,
            scored=scored,
            note=None if scored else "foreign-listed — not directly scored",
        )
        for symbol, weight, scored in rows
    ]
    total_weight = sum(weight for _, weight, _ in rows)
    if total_weight <= 0:
        return constituents, None, None
    scored_weight = sum(weight for _, weight, scored in rows if scored)
    coverage_pct = round(scored_weight / total_weight * 100.0, 1)

    scored_names = [symbol for symbol, _, scored in rows if scored]
    unscored_names = [symbol for symbol, _, scored in rows if not scored]
    note = (
        f"Scored coverage ~{coverage_pct:.0f}% of basket weight: "
        f"{', '.join(scored_names)} are ATLAS-scored"
    )
    if unscored_names:
        note += f"; {', '.join(unscored_names)} are foreign-listed and not directly scored"
    note += ". Weights are approximate / curated."
    return constituents, coverage_pct, note


def _hedge_profile_for_ticker(ticker: str) -> tuple[str, str, list[str]]:
    symbol = ticker.upper().strip()
    return _HEDGE_PROFILE_BY_TICKER.get(
        symbol,
        ("Protect portfolio exposure", "SPY", ["SPY"]),
    )


def _prefer_route_name(primary_name: str, secondary_name: str) -> str:
    primary = primary_name.strip()
    secondary = secondary_name.strip()
    if not primary and secondary:
        return secondary
    if not secondary:
        return primary
    if len(secondary) > len(primary):
        return secondary
    return primary


def _build_etf_branch_decision(
    ticker: str,
    instrument_route: str,
    momentum_score: int,
    f4_score: int,
) -> tuple[float, int, str, str, list[str], EtfBranchMetadata]:
    symbol = ticker.upper().strip()

    if instrument_route == _ETF_ROUTE_THEMATIC:
        lookthrough_score = _thematic_lookthrough_score(symbol)
        theme_cycle_score = _thematic_cycle_score(lookthrough_score, momentum_score)
        confidence_score = _confidence_liquidity_score(momentum_score, f4_score)
        components = [
            EtfBranchComponent(
                name="Constituent look-through score",
                weight=_ETF_THEMATIC_W_LOOKTHROUGH,
                score=lookthrough_score,
            ),
            EtfBranchComponent(
                name="Theme / cycle score",
                weight=_ETF_THEMATIC_W_THEME_CYCLE,
                score=theme_cycle_score,
            ),
            EtfBranchComponent(
                name="ETF momentum",
                weight=_ETF_THEMATIC_W_MOMENTUM,
                score=momentum_score,
            ),
            EtfBranchComponent(
                name="ETF F4 / options timing",
                weight=_ETF_THEMATIC_W_F4_TIMING,
                score=f4_score,
            ),
            EtfBranchComponent(
                name="Data confidence / liquidity",
                weight=_ETF_THEMATIC_W_CONFIDENCE,
                score=confidence_score,
            ),
        ]
        score = _weighted_score(
            [
                (lookthrough_score, _ETF_THEMATIC_W_LOOKTHROUGH),
                (theme_cycle_score, _ETF_THEMATIC_W_THEME_CYCLE),
                (momentum_score, _ETF_THEMATIC_W_MOMENTUM),
                (f4_score, _ETF_THEMATIC_W_F4_TIMING),
                (confidence_score, _ETF_THEMATIC_W_CONFIDENCE),
            ]
        )
        score = max(score, _ETF_BRANCH_NON_HEDGE_MIN_SCORE)
        label = _THEMATIC_LABELS.get(symbol, "Thematic equity proxy basket")
        flags = [f"{symbol} - {label}"]
        drivers = _THEMATIC_HOLDINGS_DRIVERS.get(symbol)
        if drivers:
            flags.append(f"Holdings driver: {drivers}")
        if score >= 68:
            action = (
                "BULLISH PROXY - add on reset / flow confirmation; size smaller than "
                "direct single-name exposure."
            )
            tone = "tone-blue"
        else:
            action = (
                "PROXY WATCH - thematic look-through mixed; wait for reset / flow "
                "confirmation."
            )
            tone = "tone-yellow"
        constituents, coverage_pct, coverage_note = _thematic_coverage(symbol)
        if coverage_note:
            flags.append(coverage_note)
        metadata = EtfBranchMetadata(
            route=instrument_route,
            label=label,
            headline_label=action,
            timing_overlay_role="F4 is supportive timing only; not independent add authorization.",
            holdings_driver=drivers,
            components=components,
            constituents=constituents,
            scored_coverage_pct=coverage_pct,
            coverage_note=coverage_note,
        )
        return _clamp_raw_total(float(score)), score, action, tone, flags, metadata

    if instrument_route == _ETF_ROUTE_MOMENTUM:
        factor_regime_score = _clamp_score_0_100(momentum_score * 0.7 + f4_score * 0.3)
        holdings_quality_score = 66 if symbol == "SPMO" else 58
        liquidity_score = _confidence_liquidity_score(momentum_score, f4_score)
        components = [
            EtfBranchComponent(
                name="ETF momentum / trend",
                weight=_ETF_MOMENTUM_W_MOMENTUM,
                score=momentum_score,
            ),
            EtfBranchComponent(
                name="Factor regime strength",
                weight=_ETF_MOMENTUM_W_FACTOR_REGIME,
                score=factor_regime_score,
            ),
            EtfBranchComponent(
                name="Top-holdings look-through quality",
                weight=_ETF_MOMENTUM_W_LOOKTHROUGH_QUALITY,
                score=holdings_quality_score,
            ),
            EtfBranchComponent(
                name="ETF flow / options timing",
                weight=_ETF_MOMENTUM_W_F4_TIMING,
                score=f4_score,
            ),
            EtfBranchComponent(
                name="Liquidity / concentration",
                weight=_ETF_MOMENTUM_W_LIQUIDITY,
                score=liquidity_score,
            ),
        ]
        score = _weighted_score(
            [
                (momentum_score, _ETF_MOMENTUM_W_MOMENTUM),
                (factor_regime_score, _ETF_MOMENTUM_W_FACTOR_REGIME),
                (holdings_quality_score, _ETF_MOMENTUM_W_LOOKTHROUGH_QUALITY),
                (f4_score, _ETF_MOMENTUM_W_F4_TIMING),
                (liquidity_score, _ETF_MOMENTUM_W_LIQUIDITY),
            ]
        )
        score = max(score, _ETF_BRANCH_NON_HEDGE_MIN_SCORE)
        flags = [
            "Momentum factor ETF - trend/factor framework active.",
            "Equity F1-F5 operating-company semantics not applicable.",
        ]
        if score >= 66:
            action = (
                "CONSTRUCTIVE MOMENTUM ETF - factor trend supportive. Use as broad "
                "momentum exposure, not single-name conviction."
            )
            tone = "tone-blue"
        else:
            action = (
                "MOMENTUM FACTOR ETF WATCH - trend/factor setup mixed; wait for "
                "stronger momentum confirmation."
            )
            tone = "tone-yellow"
        metadata = EtfBranchMetadata(
            route=instrument_route,
            label="Momentum factor ETF",
            headline_label=action,
            timing_overlay_role="F4 is supportive timing only; not independent add authorization.",
            holdings_driver=(
                "Top-holdings quality and concentration monitored; not a direct company "
                "conviction model."
            ),
            components=components,
        )
        return _clamp_raw_total(float(score)), score, action, tone, flags, metadata

    if instrument_route == _ETF_ROUTE_HEDGE:
        hedge_purpose, hedge_underlying, hedge_beta_covered = _hedge_profile_for_ticker(symbol)
        coverage_score = 72
        underlying_trend_score = _clamp_score_0_100(100 - momentum_score)
        vol_cost_score = _clamp_score_0_100(100 - f4_score * 0.5)
        delta_duration_score = 62
        correlation_score = 70
        max_hold_discipline_score = 65
        components = [
            EtfBranchComponent(
                name="Portfolio exposure being hedged",
                weight=_ETF_HEDGE_W_EXPOSURE_COVERAGE,
                score=coverage_score,
            ),
            EtfBranchComponent(
                name="Underlying trend timing",
                weight=_ETF_HEDGE_W_UNDERLYING_TREND,
                score=underlying_trend_score,
            ),
            EtfBranchComponent(
                name="Volatility / hedge cost",
                weight=_ETF_HEDGE_W_VOL_COST,
                score=vol_cost_score,
            ),
            EtfBranchComponent(
                name="Delta / duration efficiency",
                weight=_ETF_HEDGE_W_DELTA_DURATION,
                score=delta_duration_score,
            ),
            EtfBranchComponent(
                name="Correlation to holdings",
                weight=_ETF_HEDGE_W_CORRELATION,
                score=correlation_score,
            ),
            EtfBranchComponent(
                name="Max-hold discipline",
                weight=_ETF_HEDGE_W_MAX_HOLD_DISCIPLINE,
                score=max_hold_discipline_score,
            ),
        ]
        score = _weighted_score(
            [
                (coverage_score, _ETF_HEDGE_W_EXPOSURE_COVERAGE),
                (underlying_trend_score, _ETF_HEDGE_W_UNDERLYING_TREND),
                (vol_cost_score, _ETF_HEDGE_W_VOL_COST),
                (delta_duration_score, _ETF_HEDGE_W_DELTA_DURATION),
                (correlation_score, _ETF_HEDGE_W_CORRELATION),
                (max_hold_discipline_score, _ETF_HEDGE_W_MAX_HOLD_DISCIPLINE),
            ]
        )
        flags = [
            "Hedge instrument - tactical protection only. No fundamental ownership score.",
            "Evaluate hedge cost/IV rank, delta, expiry, and portfolio beta coverage.",
        ]
        action = "HEDGE ACTIVE - tactical protection only. Not an ownership signal."
        tone = "tone-orange"
        if score < 55:
            action = "HEDGE WATCH - tactical protection setup not yet efficient."
            tone = "tone-yellow"
        metadata = EtfBranchMetadata(
            route=instrument_route,
            label="Hedge / protective instrument",
            headline_label=action,
            timing_overlay_role=(
                "F4 and trend are hedge timing overlays only; not ownership conviction."
            ),
            components=components,
            hedge_inputs=EtfHedgeInputs(
                purpose=hedge_purpose,
                underlying=hedge_underlying,
                portfolio_beta_covered=hedge_beta_covered,
                iv_rank=None,
                delta=None,
                expiry_days=None,
                max_hold_days=15,
            ),
        )
        return _clamp_raw_total(float(score)), score, action, tone, flags, metadata

    underlying_score = _LEVERAGED_UNDERLYING_PROXY_SCORE.get(symbol, momentum_score)
    trend_score = momentum_score
    decay_penalty_score = 45
    liquidity_score = _confidence_liquidity_score(momentum_score, f4_score)
    max_hold_discipline_score = 55
    score = _weighted_score(
        [
            (underlying_score, _ETF_LEVERAGED_W_UNDERLYING_SCORE),
            (trend_score, _ETF_LEVERAGED_W_TREND),
            (decay_penalty_score, _ETF_LEVERAGED_W_DECAY_PENALTY),
            (liquidity_score, _ETF_LEVERAGED_W_LIQUIDITY),
            (max_hold_discipline_score, _ETF_LEVERAGED_W_MAX_HOLD_DISCIPLINE),
        ]
    )
    score = max(score, _ETF_BRANCH_NON_HEDGE_MIN_SCORE)
    flags = [
        "Leveraged tactical instrument - not core ownership.",
        "Use constrained sizing and max-hold discipline due to decay risk.",
    ]
    if score >= 66:
        action = (
            "BULLISH TACTICAL - leveraged exposure, size and holding period constrained."
        )
        tone = "tone-teal"
    else:
        action = (
            "LEVERAGED TACTICAL WATCH - not core ownership; size and holding period "
            "constrained."
        )
        tone = "tone-yellow"
    metadata = EtfBranchMetadata(
        route=instrument_route,
        label="Leveraged tactical instrument",
        headline_label=action,
        timing_overlay_role=(
            "F4 is timing overlay only; leverage sizing and hold-period limits dominate."
        ),
        components=[
            EtfBranchComponent(
                name="Underlying ETF/sector score",
                weight=_ETF_LEVERAGED_W_UNDERLYING_SCORE,
                score=underlying_score,
            ),
            EtfBranchComponent(
                name="Trend/momentum",
                weight=_ETF_LEVERAGED_W_TREND,
                score=trend_score,
            ),
            EtfBranchComponent(
                name="Volatility decay penalty",
                weight=_ETF_LEVERAGED_W_DECAY_PENALTY,
                score=decay_penalty_score,
            ),
            EtfBranchComponent(
                name="Liquidity/spread",
                weight=_ETF_LEVERAGED_W_LIQUIDITY,
                score=liquidity_score,
            ),
            EtfBranchComponent(
                name="Max-hold risk",
                weight=_ETF_LEVERAGED_W_MAX_HOLD_DISCIPLINE,
                score=max_hold_discipline_score,
            ),
        ],
    )
    return _clamp_raw_total(float(score)), score, action, tone, flags, metadata


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no side effects
# ---------------------------------------------------------------------------


def _map_action(final_score: int) -> tuple[str, str]:
    """Map a final conviction score to (action_string, tone_class).

    Delegates to ``atlas.core.scoring.classify_tier`` — the single source
    of truth for v7.3.3 tier boundaries.

    Pure function — no I/O.
    """
    result = classify_tier(final_score)
    return result["action"], result["action_tone"]


def _compute_raw_total(f1: int, f2: int, f3: int, f4: int, f5: int) -> float:
    """Return the weighted sum of the five factor scores (max = 95.0).

    Pure function — no I/O.
    """
    return f1 * _W_F1 + f2 * _W_F2 + f3 * _W_F3 + f4 * _W_F4 + f5 * _W_F5


def _compute_final_score(raw_total: float) -> int:
    """Clamp the raw total to [0, 100].

    Pure function — no I/O.
    """
    return max(0, min(100, round(raw_total)))


def _is_non_operating_asset(overview_payload: dict[str, Any]) -> bool:
    """Return True when OVERVIEW describes a fund/proxy instrument."""
    asset_type = str(overview_payload.get("AssetType", "")).strip().upper()
    if asset_type in _NON_OPERATING_ASSET_TYPES:
        return True

    name = str(overview_payload.get("Name", "")).strip().upper()
    if not name:
        return False
    return any(token in name for token in (" ETF", " FUND", " TRUST", " INDEX"))


def _f1_is_low_confidence(result: object) -> bool:
    """Detect F1 outputs built from insufficient history fallbacks."""
    if not isinstance(result, MomentumResponse):
        return False
    return result.ma_alignment.label == "INSUFFICIENT_DATA"


def _f3_has_no_coverage(result: object) -> bool:
    """Detect F3 responses with no analyst coverage score."""
    return isinstance(result, AnalystResponse) and result.f3_score is None


def _classify_etf_route(ticker: str, instrument_name: str) -> str:
    """Return branch route for ETF/fund/proxy instruments."""
    symbol = ticker.upper().strip()
    name = instrument_name.upper().strip()

    if symbol in _ETF_HEDGE_PROTECTIVE_TICKERS or any(
        token in name for token in (" INVERSE", " SHORT", " BEAR", " HEDGE")
    ):
        return _ETF_ROUTE_HEDGE

    if symbol in _ETF_LEVERAGED_TACTICAL_TICKERS or any(
        token in name for token in ("2X", "3X", " LEVERAGED", " ULTRA")
    ):
        return _ETF_ROUTE_LEVERAGED

    if symbol in _ETF_MOMENTUM_FACTOR_TICKERS or any(
        token in name for token in (" MOMENTUM", " FACTOR")
    ):
        return _ETF_ROUTE_MOMENTUM

    return _ETF_ROUTE_THEMATIC


def _looks_like_foreign_otc_symbol(ticker: str) -> bool:
    """Heuristic: 5-letter OTC foreign ordinary (…F) or ADR (…Y) convention.

    Used only as a fallback when provider data is missing — a 5-char symbol
    ending in F (foreign ordinary, e.g. LPKFF/SIVEF) or Y (ADR, e.g. KXIAY).
    """
    symbol = ticker.upper().strip()
    return len(symbol) == 5 and symbol.isalpha() and symbol[-1] in ("F", "Y")


def _is_international_operating(
    ticker: str,
    *,
    polygon_type: str,
    polygon_market: str,
    polygon_locale: str,
    overview_payload: dict[str, Any],
    polygon_resolved: bool,
) -> bool:
    """Return True when *ticker* is a foreign/ADR/OTC operating company (INTL-3F).

    Detection precedence: explicit known set → Polygon ADR type / OTC market /
    non-US locale → foreign Exchange in OVERVIEW → (only when provider data is
    absent) the 5-char F/Y symbol convention. ETF/fund detection runs earlier,
    so this is reached only for operating instruments.
    """
    symbol = ticker.upper().strip()
    if symbol in _INTL_KNOWN_TICKERS:
        return True
    if polygon_type in _INTL_ADR_TYPES:
        return True
    if polygon_market == "OTC":
        return True
    if polygon_locale and polygon_locale not in ("US", "USA"):
        return True

    exchange = str(overview_payload.get("Exchange", "")).strip().upper()
    country = str(overview_payload.get("Country", "")).strip().upper()
    if exchange in ("OTC", "PINK", "OTC MARKETS"):
        return True
    if country and country not in ("USA", "US", "UNITED STATES", ""):
        return True

    # Fallback only when neither provider resolved any data for this symbol.
    overview_empty = not overview_payload
    return not polygon_resolved and overview_empty and _looks_like_foreign_otc_symbol(symbol)


def _intl_instrument_kind(ticker: str, *, polygon_type: str, polygon_market: str) -> str:
    """Classify the international instrument kind for display."""
    symbol = ticker.upper().strip()
    if polygon_type in _INTL_ADR_TYPES or symbol.endswith("Y"):
        return "ADR"
    if polygon_market == "OTC" or symbol.endswith("F"):
        return "OTC foreign ordinary"
    return "Foreign operating company"


def _intl_is_otc(ticker: str, *, polygon_market: str) -> bool:
    """True when the listing is OTC (liquidity caps apply)."""
    return polygon_market == "OTC" or ticker.upper().strip().endswith("F")


def _intl_axis(
    resolved: IntlFactorData | None,
    fallback: tuple[int, bool, str],
) -> tuple[int, bool, str]:
    """Pick the foreign-capable INTL feed when it has data, else the fallback.

    ``resolved`` is the provider-sourced factor (Polygon/FMP); ``fallback`` is
    the (score, available, source) derived from any domestic factor that
    happened to resolve. Pure function — no I/O.
    """
    if resolved is not None and resolved.available:
        return resolved.score, True, resolved.source
    return fallback


def _build_intl_branch_decision(
    ticker: str,
    *,
    instrument_kind: str,
    is_otc: bool,
    i1: tuple[int, bool, str],
    i2: tuple[int, bool, str],
    i3: tuple[int, bool, str],
) -> tuple[float, int, str, str, list[str], IntlBranchMetadata]:
    """Score an international operating company on the INTL-3F model.

    I1 Business/Forward Fundamentals, I2 Market/Momentum/Liquidity, I3 External
    Confirmation — each passed in as a resolved ``(score, available, source)``
    triple from foreign-capable feeds (Polygon OTC bars + FMP), with U.S.-fed
    fallbacks applied by the caller. Scored only over factors with real data;
    missing U.S. flow is NEVER bearish, and missing data NEVER triggers a bare
    AVOID — only genuinely weak *present* data does. Mirrors the ETF branch
    tuple contract: (raw_total, final_score, action, tone, flags, metadata).
    """
    i1_score, i1_available, i1_source = i1
    i2_score, i2_available, i2_source = i2
    i3_score, i3_available, i3_source = i3

    factors = [
        IntlFactor(key="i1", name="Business / Forward Fundamentals", score=i1_score,
                   available=i1_available, source=i1_source),
        IntlFactor(key="i2", name="Market / Momentum / Liquidity", score=i2_score,
                   available=i2_available, source=i2_source),
        IntlFactor(key="i3", name="External Confirmation", score=i3_score,
                   available=i3_available, source=i3_source),
    ]

    available = [
        (i1_score, _INTL_W_I1, i1_available),
        (i2_score, _INTL_W_I2, i2_available),
        (i3_score, _INTL_W_I3, i3_available),
    ]
    coverage_count = sum(1 for _, _, ok in available if ok)
    weight_sum = sum(w for _, w, ok in available if ok)
    if coverage_count > 0 and weight_sum > 0:
        composite = _clamp_score_0_100(
            sum(score * w for score, w, ok in available if ok) / weight_sum
        )
    else:
        composite = _NEUTRAL_SCORE

    if coverage_count == 3:
        coverage_label = _INTL_LABEL_OK
    elif coverage_count >= 1:
        coverage_label = _INTL_LABEL_PARTIAL
    else:
        coverage_label = _INTL_LABEL_DATA_GAP

    rank_pending = coverage_label != _INTL_LABEL_OK
    size_capped = is_otc or rank_pending

    # --- Action: missing data / partial coverage → size-capped watch, NEVER
    #     AVOID. AVOID requires the fundamentals axis (I1) to be present AND
    #     genuinely weak — bad fundamentals, not a thin/absent feed. ---
    cap_suffix = "; size capped" if size_capped else ""
    i1_weak = i1_available and i1_score < _INTL_WEAK_FUNDAMENTAL_MAX
    if coverage_label == _INTL_LABEL_DATA_GAP:
        action = (
            "INTL-3F — DATA GAP / RANK PENDING — small starter only; size capped"
        )
        tone = "tone-yellow"
    elif coverage_label == _INTL_LABEL_PARTIAL:
        action = "INTL PARTIAL — no fresh add until local data confirms; size capped"
        tone = "tone-yellow"
    elif i1_weak:
        action = "INTL-3F — WEAK FUNDAMENTAL SETUP / avoid (confirmed on local data)"
        tone = "tone-red"
    elif composite >= 70:
        action = f"INTL-3F — CONSTRUCTIVE / international operating company{cap_suffix}"
        tone = "tone-blue"
    else:
        action = f"INTL-3F — NEUTRAL / small starter only{cap_suffix}"
        tone = "tone-yellow"

    labels = [coverage_label, _INTL_LABEL_NO_US_FLOW]
    if rank_pending:
        labels.append(_INTL_LABEL_FOREIGN_SRC)
    if is_otc:
        labels.append(_INTL_LABEL_OTC_LIQ)

    data_tasks: list[IntlDataTask] = []
    if not i1_available:
        data_tasks.append(IntlDataTask(item="local financials", status="MISSING"))
    if not i3_available:
        data_tasks.append(IntlDataTask(item="local analyst estimates", status="MISSING"))
    if not i2_available:
        data_tasks.append(IntlDataTask(item="local price history", status="MISSING"))
    data_tasks.append(IntlDataTask(item="local exchange mapping", status="MISSING"))
    if is_otc:
        data_tasks.append(IntlDataTask(item="liquidity", status="PARTIAL"))
    data_tasks.append(IntlDataTask(item="options / flow availability (U.S.)", status="MISSING"))

    flags = [
        "INTL router active: domestic F1–F5 not applicable; INTL-3F model drives action.",
        f"INTL-3F coverage: {coverage_label}.",
        "F4 N/A — no U.S. flow coverage (unavailable, not bearish).",
    ]
    if rank_pending:
        flags.append("Rank pending / manual review — missing international data, not a bad setup.")

    metadata = IntlBranchMetadata(
        route=_ROUTE_INTL,
        label="INTL-3F — International Operating Company",
        headline_label=action,
        instrument_kind=instrument_kind,
        coverage_label=coverage_label,
        rank_pending=rank_pending,
        size_capped=size_capped,
        factors=factors,
        labels=labels,
        data_tasks=data_tasks,
    )
    final_score = composite
    raw_total = _clamp_raw_total(float(composite))
    return raw_total, final_score, action, tone, flags, metadata


# ---------------------------------------------------------------------------
# Service class — orchestrates F1-F5 + regime concurrently
# ---------------------------------------------------------------------------


class FrameworkScoreService:
    """Computes the complete ATLAS Framework Score for a single ticker.

    Calls all five factor services concurrently (``asyncio.gather``).
    Any sub-service that fails (missing API key, network error) falls back
    to a neutral score of 50 and appends a descriptive flag.

    Parameters
    ----------
    polygon_api_key:
        Polygon.io key — used by MomentumService and Brent crude fetch.
    alphavantage_api_key:
        Alpha Vantage key — used by EarningsService and FundamentalService.
    transcript_api_key:
        FMP key — used by EarningsService for earnings call transcripts.
    benzinga_api_key:
        Benzinga key — used by AnalystService.
    unusual_whales_api_key:
        Unusual Whales key — used by OptionsFlowService.
    sec_api_key:
        sec-api.io key — used by FundamentalService.
    """

    def __init__(
        self,
        polygon_api_key: str,
        alphavantage_api_key: str,
        transcript_api_key: str,
        benzinga_api_key: str,
        unusual_whales_api_key: str,
        sec_api_key: str,
    ) -> None:
        self._polygon_key = polygon_api_key
        self._alphavantage_key = alphavantage_api_key
        self._transcript_key = transcript_api_key
        self._benzinga_key = benzinga_api_key
        self._unusual_whales_key = unusual_whales_api_key
        self._sec_key = sec_api_key

    async def compute_framework_score(self, ticker: str) -> FrameworkScoreResponse:
        """Compute the Framework Score for ``ticker`` asynchronously.

        INCOME_STATEMENT and OVERVIEW are each used by two factor services
        (F2+F5 and F3+F5 respectively).  We create shared asyncio Tasks for
        them before the gather so both tasks start immediately; F2, F3, and F5
        await the same Task objects instead of making duplicate HTTP calls.
        Each Task executes the fetch exactly once regardless of how many
        services await it.
        """
        async with httpx.AsyncClient() as client:
            # Shared AV pre-fetches — started before the gather so they are
            # already in-flight when F2 / F3 / F5 coroutines begin.
            income_task: asyncio.Task[dict[str, Any]] = asyncio.create_task(
                self._fetch_av_raw(client, ticker, "INCOME_STATEMENT")
            )
            overview_task: asyncio.Task[dict[str, Any]] = asyncio.create_task(
                self._fetch_av_raw(client, ticker, "OVERVIEW")
            )
            route_task: asyncio.Task[tuple[bool, str]] = asyncio.create_task(
                self._instrument_route_for_ticker(client, ticker, overview_task)
            )

            f1_result, f2_result, f3_result, f4_result, f5_result, f8_data = await asyncio.gather(
                self._fetch_f1(ticker, client),
                self._fetch_f2(ticker, client, income_task),
                self._fetch_f3(ticker, overview_task),
                self._fetch_f4(ticker),
                self._fetch_f5(ticker, income_task, overview_task),
                self._fetch_f8(ticker),
                return_exceptions=True,
            )
            non_operating_asset, instrument_route = await route_task

            # International / ADR / OTC operating names get their I1/I2/I3 from
            # foreign-capable feeds (Polygon OTC bars + FMP), fetched only on the
            # INTL route so domestic names pay no extra cost.
            intl_data: IntlData | None = None
            if (not non_operating_asset) and instrument_route == _ROUTE_INTL:
                intl_data = await self._fetch_intl(client, ticker)

        flags: list[str] = []

        # --- Extract factor scores with graceful fallback ---
        f1_score, f1_grade, f1_ok = self._extract_factor(
            f1_result, "f1_score", "f1_grade", "F1 Momentum", flags
        )
        f2_score, f2_grade, f2_ok = self._extract_factor(
            f2_result, "f2_score", "f2_grade", "F2 Earnings Quality", flags
        )
        f3_score, f3_grade, f3_ok = self._extract_factor(
            f3_result, "f3_score", "f3_grade", "F3 Analyst Sentiment", flags
        )
        f4_score, f4_grade, f4_ok = self._extract_factor(
            f4_result, "f4_score", "f4_grade", "F4 Options Flow Persistence", flags
        )
        # F4 row uses the F4b band vocabulary, NOT the legacy BUY/STRONG BUY grade
        # (F4 Implementation Audit): the Framework panel must not imply an add from
        # F4 alone — the Flow Monitor is the action gate. f4_grade is still kept on
        # the raw F4 response for back-compat; only the displayed factor row changes.
        f4_flow_monitor: str | None = None
        if f4_ok:
            f4_grade = f4_framework_row_label(f4_score)
            f4_flow_monitor = getattr(f4_result, "flow_monitor_action", None)
        f5_score, f5_grade, f5_ok = self._extract_factor(
            f5_result, "f5_score", "f5_grade", "F5 Fundamental Quality", flags
        )
        f5_raw_score = f5_score  # preserve pre-cap value for response metadata

        branch_raw_total: float | None = None
        branch_final_score: int | None = None
        branch_action: str | None = None
        branch_action_tone: str | None = None
        etf_branch_metadata: EtfBranchMetadata | None = None
        intl_branch_metadata: IntlBranchMetadata | None = None
        is_intl = (not non_operating_asset) and instrument_route == _ROUTE_INTL

        # Preserve pre-router scores so branch models can still consume ETF-level
        # momentum/timing signals even while direct company factors are shown as N/A.
        pre_router_f1_score = f1_score
        pre_router_f4_score = f4_score

        f1_low_confidence = _f1_is_low_confidence(f1_result)
        f3_no_coverage = _f3_has_no_coverage(f3_result)

        if non_operating_asset:
            # Universal ETF router: do not run operating-company factor semantics
            # on ETF/fund/proxy instruments.
            f1_score, f1_grade, f1_ok = _NEUTRAL_SCORE, "N/A", False
            f2_score, f2_grade, f2_ok = _NEUTRAL_SCORE, "N/A", False
            f3_score, f3_grade, f3_ok = _NEUTRAL_SCORE, "NO COVERAGE", False
            f5_score, f5_grade, f5_ok = _NEUTRAL_SCORE, "N/A", False

            flags.append(
                "ETF router active: operating-company F1/F2/F3/F5 disabled; "
                "ETF branch model + timing overlays drive action."
            )
            if instrument_route == _ETF_ROUTE_THEMATIC:
                flags.append("ETF branch: thematic equity proxy basket (look-through model).")
            elif instrument_route == _ETF_ROUTE_MOMENTUM:
                flags.append("ETF branch: momentum/factor ETF model.")
            elif instrument_route == _ETF_ROUTE_HEDGE:
                flags.append("ETF branch: hedge/protective instrument model.")
            elif instrument_route == _ETF_ROUTE_LEVERAGED:
                flags.append("ETF branch: leveraged tactical ETF model.")

            (
                branch_raw_total,
                branch_final_score,
                branch_action,
                branch_action_tone,
                branch_flags,
                etf_branch_metadata,
            ) = _build_etf_branch_decision(
                ticker=ticker,
                instrument_route=instrument_route,
                momentum_score=pre_router_f1_score,
                f4_score=pre_router_f4_score,
            )
            flags.extend(branch_flags)

        elif is_intl:
            # INTL-3F router: foreign / ADR / OTC operating company. Score on the
            # INTL-3F model from whatever real data exists, then suppress the
            # domestic F1-F5 display. Missing U.S. flow is N/A, never bearish, and
            # missing data never triggers a bare AVOID.
            f2_data_available = not (
                isinstance(f2_result, EarningsResponse) and not f2_result.data_available
            )
            f5_data_available = not (
                isinstance(f5_result, FundamentalResponse) and not f5_result.data_available
            )
            # Prefer the foreign-capable INTL feeds; fall back to any domestic
            # factor that happened to resolve. Missing → unavailable (not bearish).
            if f5_ok and f2_data_available and f2_ok:
                i1_fallback_score = _clamp_score_0_100(f5_score * 0.6 + f2_score * 0.4)
                i1_fallback = (i1_fallback_score, True, "fundamental+earnings (US fallback)")
            elif f5_ok and f5_data_available:
                i1_fallback = (f5_score, True, "fundamental (US fallback)")
            elif f2_ok and f2_data_available:
                i1_fallback = (f2_score, True, "earnings (US fallback)")
            else:
                i1_fallback = (_NEUTRAL_SCORE, False, "DATA_GAP")
            i2_fallback = (
                (pre_router_f1_score, True, "momentum (US fallback)")
                if (f1_ok and not f1_low_confidence)
                else (_NEUTRAL_SCORE, False, "DATA_GAP")
            )
            i3_fallback = (
                (f3_score, True, "analyst (US fallback)")
                if (f3_ok and not f3_no_coverage)
                else (_NEUTRAL_SCORE, False, "DATA_GAP")
            )

            i1_triple = _intl_axis(intl_data.i1 if intl_data else None, i1_fallback)
            i2_triple = _intl_axis(intl_data.i2 if intl_data else None, i2_fallback)
            i3_triple = _intl_axis(intl_data.i3 if intl_data else None, i3_fallback)

            (
                branch_raw_total,
                branch_final_score,
                branch_action,
                branch_action_tone,
                branch_flags,
                intl_branch_metadata,
            ) = _build_intl_branch_decision(
                ticker=ticker,
                instrument_kind=_intl_instrument_kind(ticker, polygon_type="", polygon_market=""),
                is_otc=_intl_is_otc(ticker, polygon_market=""),
                i1=i1_triple,
                i2=i2_triple,
                i3=i3_triple,
            )
            # Suppress domestic factors for display — they do not apply.
            f1_score, f1_grade, f1_ok = _NEUTRAL_SCORE, "N/A", False
            f2_score, f2_grade, f2_ok = _NEUTRAL_SCORE, "N/A", False
            f3_score, f3_grade, f3_ok = _NEUTRAL_SCORE, "N/A", False
            f4_score, f4_grade, f4_ok = _NEUTRAL_SCORE, "N/A (NO U.S. FLOW)", False
            f5_score, f5_grade, f5_ok = _NEUTRAL_SCORE, "N/A", False
            f4_flow_monitor = None
            flags.extend(branch_flags)

        elif f1_low_confidence:
            f1_score, f1_grade, f1_ok = _NEUTRAL_SCORE, "N/A", False
            flags.append(
                "F1 Momentum low-confidence (insufficient history) - "
                "neutral fallback used in composite."
            )

        if f3_no_coverage and not non_operating_asset and not is_intl:
            f3_score, f3_grade, f3_ok = _NEUTRAL_SCORE, "NO COVERAGE", False
            flags.append(
                "F3 Analyst Sentiment has no analyst coverage - neutral fallback used in composite."
            )

        # --- Framework 8 insider buying bonus ---
        # F8 is fetched fresh in parallel above — never cached here.
        if isinstance(f8_data, Exception):
            f8_data = {}

        f8_buying_bonus: int = (
            int(f8_data.get("buying_bonus", 0)) if isinstance(f8_data, dict) else 0
        )
        f8_clustered_selling_note: str | None = (
            f8_data.get("clustered_selling_note") if isinstance(f8_data, dict) else None
        )

        # --- F5 block detection ---
        f5_blocked = False
        if isinstance(f5_result, FundamentalResponse) and getattr(f5_result, "f5_blocked", False):
            f5_blocked = True
            flags.append("F5 HARD BLOCK: Altman Z-Score below 1.8 — no new capital.")

        # --- Assemble factor breakdowns ---
        # available=False when either score extraction failed OR the underlying
        # data source reported data_available=False (the latter drives degraded=True).
        f2_data_ok = not (isinstance(f2_result, EarningsResponse) and not f2_result.data_available)
        f5_data_ok = not (
            isinstance(f5_result, FundamentalResponse) and not f5_result.data_available
        )
        if non_operating_asset or is_intl:
            f2_data_ok = False
            f5_data_ok = False

        factor_meta: list[tuple[str, str, int, float, str, bool]] = [
            ("f1", "Momentum", f1_score, _W_F1, f1_grade, f1_ok),
            ("f2", "Earnings Quality", f2_score, _W_F2, f2_grade, f2_ok and f2_data_ok),
            ("f3", "Analyst Sentiment", f3_score, _W_F3, f3_grade, f3_ok),
            ("f4", "Options Flow Persistence", f4_score, _W_F4, f4_grade, f4_ok),
            ("f5", "Fundamental Quality", f5_score, _W_F5, f5_grade, f5_ok and f5_data_ok),
        ]
        factors = [
            FactorBreakdown(
                key=key,
                name=name,
                score=score,
                weight=weight,
                contribution=round(score * weight, 4),
                grade=grade,
                available=available,
                flow_monitor_action=(f4_flow_monitor if key == "f4" else None),
            )
            for key, name, score, weight, grade, available in factor_meta
        ]

        # --- Final calculation ---
        if (
            (non_operating_asset or is_intl)
            and branch_raw_total is not None
            and branch_final_score is not None
        ):
            raw_total = branch_raw_total
            # INTL names are foreign — F8 (U.S. SEC Form 4) does not apply, so the
            # bonus is left out of the INTL composite.
            bonus = 0 if is_intl else f8_buying_bonus
            final_score = _compute_final_score(raw_total + bonus)
            action = branch_action if branch_action is not None else "SMALL POSITION ONLY"
            action_tone = branch_action_tone if branch_action_tone is not None else "tone-yellow"
        else:
            raw_total = round(
                _compute_raw_total(f1_score, f2_score, f3_score, f4_score, f5_score),
                4,
            )
            # Apply F8 buying bonus additively before clamping to final score.
            final_score = _compute_final_score(raw_total + f8_buying_bonus)
            action, action_tone = _map_action(final_score)

        return FrameworkScoreResponse(
            ticker=ticker.upper(),
            factors=factors,
            raw_total=raw_total,
            final_score=final_score,
            action=action,
            action_tone=action_tone,
            f5_blocked=f5_blocked,
            flags=flags,
            degraded=(
                not is_intl
                and (
                    non_operating_asset
                    or f1_low_confidence
                    or f3_no_coverage
                    or (isinstance(f2_result, EarningsResponse) and not f2_result.data_available)
                    or (isinstance(f5_result, FundamentalResponse) and not f5_result.data_available)
                )
            ),
            f4_data_gap_badge=(
                f4_result.f1_propagation_badge
                if hasattr(f4_result, "f1_propagation_badge")
                else None
            ),
            f4_data_gap_message=(
                f4_result.f1_propagation_message
                if hasattr(f4_result, "f1_propagation_message")
                else None
            ),
            f4_data_gap_tooltip=(
                f4_result.f1_propagation_tooltip
                if hasattr(f4_result, "f1_propagation_tooltip")
                else None
            ),
            f5_raw_score=f5_raw_score,
            f8_buying_bonus=f8_buying_bonus,
            f8_clustered_selling_note=f8_clustered_selling_note,
            f5_debug_bridge=(
                f5_result.f5_debug_bridge
                if isinstance(f5_result, FundamentalResponse)
                else None
            ),
            etf_branch=etf_branch_metadata,
            intl_branch=intl_branch_metadata,
        )

    # ------------------------------------------------------------------
    # Private — factor fetch wrappers
    # ------------------------------------------------------------------

    async def _fetch_f1(
        self,
        ticker: str,
        client: httpx.AsyncClient,
    ) -> MomentumResponse:
        """Fetch F1 Momentum score."""
        service = MomentumService(api_key=self._polygon_key, client=client)
        return await service.compute_momentum(ticker)

    async def _fetch_av_raw(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        function: str,
    ) -> dict[str, Any]:
        """Fetch one Alpha Vantage endpoint; returns {} on rate-limit or error.

        Used to create shared Tasks so the same endpoint is never fetched more
        than once per framework-score request regardless of how many factor
        services need it.
        """
        return await fetch_alpha_vantage_cached(
            client,
            api_key=self._alphavantage_key,
            function=function,
            symbol=ticker,
            timeout=15.0,
        )

    async def _instrument_route_for_ticker(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        overview_task: asyncio.Task[dict[str, Any]],
    ) -> tuple[bool, str]:
        """Return (is_non_operating, route_label) for the universal router."""
        overview_payload = await overview_task
        overview_name = str(overview_payload.get("Name", "")).strip()
        overview_non_operating = _is_non_operating_asset(overview_payload)

        try:
            response = await client.get(
                _POLYGON_TICKER_DETAILS_URL.format(ticker=ticker),
                params={"apiKey": self._polygon_key},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", {}) if isinstance(payload, dict) else {}
            p_type = str(results.get("type", "")).strip().upper()
            p_name = str(results.get("name", "")).strip()
            p_market = str(results.get("market", "")).strip().upper()
            p_locale = str(results.get("locale", "")).strip().upper()
            route_name = _prefer_route_name(overview_name, p_name)
            route_name_upper = route_name.upper()
            if p_type in _NON_OPERATING_ASSET_TYPES:
                return True, _classify_etf_route(ticker, route_name_upper)
            if any(
                token in route_name_upper for token in (" ETF", " FUND", " TRUST", " INDEX")
            ):
                return True, _classify_etf_route(ticker, route_name_upper)
            if overview_non_operating:
                return True, _classify_etf_route(ticker, overview_name)
            if _is_international_operating(
                ticker,
                polygon_type=p_type,
                polygon_market=p_market,
                polygon_locale=p_locale,
                overview_payload=overview_payload,
                polygon_resolved=bool(results),
            ):
                return False, _ROUTE_INTL
            return False, _ROUTE_EQUITY
        except (httpx.HTTPError, ValueError, TypeError):
            if overview_non_operating:
                return True, _classify_etf_route(ticker, overview_name)
            if _is_international_operating(
                ticker,
                polygon_type="",
                polygon_market="",
                polygon_locale="",
                overview_payload=overview_payload,
                polygon_resolved=False,
            ):
                return False, _ROUTE_INTL
            return False, _ROUTE_EQUITY

    async def _fetch_intl(
        self, client: httpx.AsyncClient, ticker: str
    ) -> IntlData | None:
        """Resolve INTL-3F I1/I2/I3 from foreign-capable feeds (Polygon + FMP).

        Returns None on any unexpected failure so the INTL branch falls back to
        whatever domestic factors resolved (and to a clean data-gap otherwise).
        """
        try:
            service = IntlDataService(
                polygon_api_key=self._polygon_key,
                fmp_api_key=self._transcript_key,
            )
            return await service.compute_intl(client, ticker)
        except Exception as exc:  # never let INTL enrichment break the score
            logger.warning(
                "INTL data fetch failed - falling back to domestic factors",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return None

    async def _fetch_f2(
        self,
        ticker: str,
        client: httpx.AsyncClient,
        income_task: asyncio.Task[dict[str, Any]],
    ) -> EarningsResponse:
        """Fetch F2 Earnings Quality score (shares pre-fetched INCOME_STATEMENT)."""
        service = EarningsService(
            api_key=self._alphavantage_key,
            transcript_api_key=self._transcript_key,
            polygon_api_key=self._polygon_key,
            client=client,
        )
        return await service.compute_earnings(ticker, income_task=income_task)

    async def _fetch_f3(
        self,
        ticker: str,
        overview_task: asyncio.Task[dict[str, Any]],
    ) -> AnalystResponse:
        """Fetch F3 Analyst Sentiment score (shares pre-fetched OVERVIEW)."""
        service = AnalystService(
            benzinga_api_key=self._benzinga_key,
            polygon_api_key=self._polygon_key,
            alphavantage_api_key=self._alphavantage_key,
            fmp_api_key=self._transcript_key,
        )
        return await service.compute_analyst(ticker, overview_task=overview_task)

    async def _fetch_f4(self, ticker: str) -> Framework9Result:
        """Fetch F4 Options Flow score via Framework 9.

        Framework 9 wraps OptionsFlowService and applies pre-earnings timing
        modifiers (-25% reduction or +10% Exceptional Conviction premium).
        Framework 1 must consume the *adjusted* score so timing risk is
        reflected in the final conviction score.
        """
        return await evaluate_framework9(
            ticker,
            uw_api_key=self._unusual_whales_key,
            polygon_api_key=self._polygon_key,
            av_api_key=self._alphavantage_key,
        )

    async def _fetch_f5(
        self,
        ticker: str,
        income_task: asyncio.Task[dict[str, Any]],
        overview_task: asyncio.Task[dict[str, Any]],
    ) -> FundamentalResponse:
        """Fetch F5 Fundamental Quality score (shares pre-fetched INCOME_STATEMENT + OVERVIEW)."""
        service = FundamentalService(
            sec_api_key=self._sec_key,
            alphavantage_key=self._alphavantage_key,
        )
        return await service.compute_fundamental(
            ticker, income_task=income_task, overview_task=overview_task
        )

    async def _fetch_f8(self, ticker: str) -> dict[str, Any]:
        """Fetch Framework 8 insider buying bonus for *ticker*.

        Called fresh on every evaluation — no caching at this layer.
        On any failure returns an empty dict so the caller applies zero bonus.
        """
        try:
            service = Framework8Service(sec_api_key=self._sec_key)
            result = await service.compute(ticker)
            return {
                "buying_bonus": result.buying_bonus,
                "clustered_selling_note": result.clustered_selling_note,
            }
        except Exception as exc:
            logger.warning(
                "Framework 8 fetch failed - buying bonus will be zero",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return {}

    # ------------------------------------------------------------------
    # Private — score extraction with fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_factor(
        result: object,
        score_field: str,
        grade_field: str,
        label: str,
        flags: list[str],
    ) -> tuple[int, str, bool]:
        """Extract (score, grade, available) from a factor result.

        On any failure returns (_NEUTRAL_SCORE, "NEUTRAL", False) and appends
        a descriptive flag.
        """
        if isinstance(result, Exception):
            flags.append(f"{label}: unavailable ({type(result).__name__}). Using neutral score.")
            return _NEUTRAL_SCORE, "NEUTRAL", False
        try:
            score = int(getattr(result, score_field))
            grade = str(getattr(result, grade_field))
            return score, grade, True
        except (AttributeError, TypeError, ValueError):
            flags.append(f"{label}: score extraction failed. Using neutral score.")
            return _NEUTRAL_SCORE, "NEUTRAL", False
