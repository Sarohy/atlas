"""Framework 14 — Position Sizing Rules service.

ATLAS v7.3.4 spec (CLAUDE.md Framework #13):
  Single-position concentration caps:
    Soft cap:    >= 8% NAV → no new adds
    Hard review: >= 10% NAV → consider trimming
  Grandfathered positions hold special status until weight breaches expiry.
  Cluster thresholds limit correlated exposure.

All pure functions are fully synchronous and side-effect-free.
Async functions query the live database for NAV and position weights.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.portfolio_config import PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.schemas.framework14 import (
    ClusterStatus,
    ConcentrationStatus,
    Framework14Result,
    SizingTier,
)

# ---------------------------------------------------------------------------
# Grandfathered positions (April 2026)
# Each entry: {"current": float, "expires_at": float}
# "expires_at" is the weight fraction at which grandfathered status ends.
# ---------------------------------------------------------------------------

GRANDFATHERED_POSITIONS: Final[dict[str, dict[str, float]]] = {
    "MU": {"current": 0.136, "expires_at": 0.170},
    "TSM": {"current": 0.117, "expires_at": 0.146},
    "COHR": {"current": 0.095, "expires_at": 0.119},
}

# ---------------------------------------------------------------------------
# Cluster memberships
# ---------------------------------------------------------------------------

TICKER_CLUSTER_MAP: Final[dict[str, str]] = {
    "LITE": "AI Optics",
    "COHR": "AI Optics",
    "AAOI": "AI Optics",
    "CRDO": "AI Optics",
    "CIEN": "AI Optics",
    "FN": "AI Optics",
    "MU": "AI Memory",
    "SNDK": "AI Memory",
    "TSM": "Foundry",
    "TSEM": "Foundry",
    "VRT": "AI Power/Thermal",
    "VICR": "AI Power/Thermal",
    "AVGO": "AI Custom Silicon",
    "MRVL": "AI Custom Silicon",
    "NBIS": "AI Infrastructure",
    "CLS": "AI Infrastructure",
    "UCTT": "AI Infrastructure",
}

# ---------------------------------------------------------------------------
# Cluster thresholds: yellow and red as fraction of NAV
# ---------------------------------------------------------------------------

CLUSTER_THRESHOLDS: Final[dict[str, dict[str, float]]] = {
    "AI Optics": {"yellow": 0.27, "red": 0.30},
    "AI Memory": {"yellow": 0.22, "red": 0.25},
    "Foundry": {"yellow": 0.17, "red": 0.20},
    "AI Power/Thermal": {"yellow": 0.12, "red": 0.15},
    "AI Custom Silicon": {"yellow": 0.12, "red": 0.15},
    "AI Infrastructure": {"yellow": 0.12, "red": 0.15},
}

# ---------------------------------------------------------------------------
# Sizing tier mapping
# ---------------------------------------------------------------------------

_TICKER_TIER_MAP: Final[dict[str, SizingTier]] = {
    # Core Anchor: 3-5% NAV
    "MU": SizingTier.CORE_ANCHOR,
    "AVGO": SizingTier.CORE_ANCHOR,
    "MRVL": SizingTier.CORE_ANCHOR,
    # High Conviction T2: 1.5-2.5% NAV
    "LITE": SizingTier.HIGH_CONVICTION_T2,
    "CRDO": SizingTier.HIGH_CONVICTION_T2,
    "CIEN": SizingTier.HIGH_CONVICTION_T2,
    "FN": SizingTier.HIGH_CONVICTION_T2,
    "VRT": SizingTier.HIGH_CONVICTION_T2,
    "VICR": SizingTier.HIGH_CONVICTION_T2,
    "NBIS": SizingTier.HIGH_CONVICTION_T2,
    # Standard T2: 0.5-1.0% NAV
    "COHR": SizingTier.STANDARD_T2,
    "TSM": SizingTier.STANDARD_T2,
    "SNDK": SizingTier.STANDARD_T2,
    "TSEM": SizingTier.STANDARD_T2,
    "CLS": SizingTier.STANDARD_T2,
    "UCTT": SizingTier.STANDARD_T2,
    # High Beta: 0.5-1.0% NAV (same range, explicit cap applies)
    "AAOI": SizingTier.HIGH_BETA,
}

# ---------------------------------------------------------------------------
# Sizing tier target weights: (min, max) as fraction of NAV
# ---------------------------------------------------------------------------

TIER_TARGET_WEIGHTS: Final[dict[SizingTier, tuple[float, float]]] = {
    SizingTier.CORE_ANCHOR: (0.03, 0.05),
    SizingTier.HIGH_CONVICTION_T2: (0.015, 0.025),
    SizingTier.STANDARD_T2: (0.005, 0.010),
    SizingTier.T3_SATELLITE: (0.0025, 0.005),
    SizingTier.CHINA_RISK: (0.0, 0.0025),
    SizingTier.HIGH_BETA: (0.005, 0.010),
}

# ---------------------------------------------------------------------------
# Concentration thresholds
# ---------------------------------------------------------------------------

# 8% NAV — soft cap; no new adds permitted above this
_SOFT_CAP: Final[float] = 0.08

# 10% NAV — hard review; trimming strongly considered
_HARD_REVIEW_THRESHOLD: Final[float] = 0.10

# Grandfathered expiry "near" when within this fraction of the expiry threshold
_EXPIRY_NEAR_DELTA: Final[float] = 0.02

# Score display cap applied when soft cap is breached (display-only, not a scoring change)
_SCORE_DISPLAY_CAP: Final[int] = 85

# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def get_sizing_tier(ticker: str) -> SizingTier:
    """Return the sizing tier for *ticker*.

    Normalises the ticker to upper-case before lookup.
    Unknown tickers default to STANDARD_T2.
    """
    return _TICKER_TIER_MAP.get(ticker.upper(), SizingTier.STANDARD_T2)


def get_target_weight(tier: SizingTier) -> tuple[float, float]:
    """Return the (min, max) target weight fraction for the given tier."""
    return TIER_TARGET_WEIGHTS[tier]


def evaluate_concentration(ticker: str, position_weight: float) -> dict[str, object]:
    """Evaluate single-position concentration caps.

    Pure function — no I/O.

    Returns a dict with all concentration-related fields consumed by
    ``evaluate_framework14``. Keys mirror ``Framework14Result`` fields.
    """
    upper = ticker.upper()
    grandfathered_info = GRANDFATHERED_POSITIONS.get(upper)

    soft_cap_breached = position_weight >= _SOFT_CAP
    hard_review_triggered = position_weight >= _HARD_REVIEW_THRESHOLD

    # Determine grandfathered status
    is_grandfathered = (
        grandfathered_info is not None and position_weight <= grandfathered_info["expires_at"]
    )

    # Grandfathered expiry is "near" when weight is within _EXPIRY_NEAR_DELTA
    expiry_near = False
    expires_at: float | None = None
    if grandfathered_info is not None:
        expires_at = grandfathered_info["expires_at"]
        if is_grandfathered:
            expiry_near = abs(position_weight - expires_at) <= _EXPIRY_NEAR_DELTA

    # Concentration status priority: GRANDFATHERED > HARD_REVIEW > SOFT_CAP > NORMAL
    if is_grandfathered:
        status = ConcentrationStatus.GRANDFATHERED
    elif hard_review_triggered:
        status = ConcentrationStatus.HARD_REVIEW
    elif soft_cap_breached:
        status = ConcentrationStatus.SOFT_CAP
    else:
        status = ConcentrationStatus.NORMAL

    cap_active = soft_cap_breached
    adds_permitted = not (soft_cap_breached or is_grandfathered)
    score_display_cap: int | None = _SCORE_DISPLAY_CAP if soft_cap_breached else None
    trim_recommended = hard_review_triggered

    return {
        "concentration_status": status,
        "cap_active": cap_active,
        "soft_cap_breached": soft_cap_breached,
        "hard_review_triggered": hard_review_triggered,
        "grandfathered": is_grandfathered,
        "grandfathered_expires_at": expires_at,
        "grandfathered_expiry_near": expiry_near,
        "score_display_cap": score_display_cap,
        "adds_permitted": adds_permitted,
        "trim_recommended": trim_recommended,
    }


def evaluate_cluster(ticker: str, cluster_weight: float) -> dict[str, object]:
    """Evaluate cluster-level concentration.

    Pure function — no I/O.

    Returns a dict with all cluster-related fields consumed by
    ``evaluate_framework14``. Keys mirror ``Framework14Result`` fields.
    """
    upper = ticker.upper()
    cluster = TICKER_CLUSTER_MAP.get(upper, "Unknown")
    thresholds = CLUSTER_THRESHOLDS.get(cluster, {"yellow": 0.0, "red": 0.0})

    yellow = thresholds["yellow"]
    red = thresholds["red"]

    if cluster_weight >= red:
        cluster_status = ClusterStatus.RED_ZONE
    elif cluster_weight >= yellow:
        cluster_status = ClusterStatus.YELLOW_ZONE
    else:
        cluster_status = ClusterStatus.NORMAL

    trim_recommended = cluster_status == ClusterStatus.RED_ZONE

    return {
        "cluster": cluster,
        "cluster_status": cluster_status,
        "cluster_yellow_threshold": yellow,
        "cluster_red_threshold": red,
        "trim_recommended": trim_recommended,
    }


def _build_message(
    concentration_status: ConcentrationStatus,
    cluster_status: ClusterStatus,
    adds_permitted: bool,
    trim_recommended: bool,
    ticker: str,
) -> str:
    """Generate a human-readable guidance message. Pure function."""
    if concentration_status == ConcentrationStatus.GRANDFATHERED:
        return (
            f"{ticker} is grandfathered above the 8% soft cap. "
            "No new adds. Monitor expiry threshold."
        )
    if concentration_status == ConcentrationStatus.HARD_REVIEW:
        return f"{ticker} exceeds the 10% hard review threshold. Trim review recommended."
    if concentration_status == ConcentrationStatus.SOFT_CAP:
        return f"{ticker} has reached the 8% soft cap. No new adds permitted."
    if cluster_status == ClusterStatus.RED_ZONE:
        return f"{ticker}: cluster in red zone. Trim to reduce correlated exposure."
    if cluster_status == ClusterStatus.YELLOW_ZONE:
        return f"{ticker}: cluster in yellow zone. Monitor closely."
    if adds_permitted:
        return f"{ticker}: concentration normal. Adds permitted per tier rules."
    return f"{ticker}: position under review."


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------


async def get_position_weight_and_nav(
    ticker: str,
    session: AsyncSession,
) -> tuple[float, float, float]:
    """Return (weight_fraction, position_dollars, total_nav_dollars).

    Queries the live DB for all tickers and the portfolio cash balance.
    If ticker is not found the position weight is 0.0 and position_dollars is 0.0.
    """
    # Sum all position values for invested NAV
    total_invested_result = await session.execute(select(func.sum(Ticker.position_value)))
    total_invested: float = float(total_invested_result.scalar() or 0.0)

    # Cash balance from portfolio_config
    cash_result = await session.execute(select(PortfolioConfig.cash_balance).limit(1))
    cash_balance: float = float(cash_result.scalar() or 0.0)

    total_nav = total_invested + cash_balance
    if total_nav == 0.0:
        return (0.0, 0.0, 0.0)

    # Individual position value
    ticker_result = await session.execute(
        select(Ticker.position_value).where(Ticker.ticker == ticker.upper())
    )
    position_value: float = float(ticker_result.scalar() or 0.0)

    weight = position_value / total_nav
    return (weight, position_value, total_nav)


async def get_cluster_weight(
    cluster: str,
    session: AsyncSession,
) -> float:
    """Return the total cluster weight as a fraction of NAV.

    Sums position values for all tickers in *cluster*, then divides by
    total NAV (invested + cash).
    """
    cluster_tickers = [t for t, c in TICKER_CLUSTER_MAP.items() if c == cluster]
    if not cluster_tickers:
        return 0.0

    # Sum invested for cluster members
    cluster_result = await session.execute(
        select(func.sum(Ticker.position_value)).where(Ticker.ticker.in_(cluster_tickers))
    )
    cluster_invested: float = float(cluster_result.scalar() or 0.0)

    # Total NAV
    total_invested_result = await session.execute(select(func.sum(Ticker.position_value)))
    total_invested: float = float(total_invested_result.scalar() or 0.0)

    cash_result = await session.execute(select(PortfolioConfig.cash_balance).limit(1))
    cash_balance: float = float(cash_result.scalar() or 0.0)

    total_nav = total_invested + cash_balance
    if total_nav == 0.0:
        return 0.0

    return cluster_invested / total_nav


# ---------------------------------------------------------------------------
# Async orchestrator
# ---------------------------------------------------------------------------


async def evaluate_framework14(
    ticker: str,
    session: AsyncSession,
    position_weight_override: float | None = None,
    cluster_weight_override: float | None = None,
) -> Framework14Result:
    """Compute the full Framework 14 result for *ticker*.

    Uses live DB unless overrides are supplied (useful for testing).
    """
    upper = ticker.upper()

    if position_weight_override is not None:
        weight = position_weight_override
        position_dollars = 0.0
        nav_dollars = 0.0
    else:
        weight, position_dollars, nav_dollars = await get_position_weight_and_nav(upper, session)

    cluster = TICKER_CLUSTER_MAP.get(upper, "Unknown")

    if cluster_weight_override is not None:
        cluster_weight = cluster_weight_override
    else:
        cluster_weight = await get_cluster_weight(cluster, session)

    # Evaluate concentration
    conc = evaluate_concentration(upper, weight)

    # Evaluate cluster
    clust = evaluate_cluster(upper, cluster_weight)

    # Merge trim_recommended — either concentration or cluster trigger
    trim_recommended = bool(conc["trim_recommended"]) or bool(clust["trim_recommended"])

    # adds_permitted: spec blocks only on concentration, not cluster status
    adds_permitted = bool(conc["adds_permitted"])

    tier = get_sizing_tier(upper)
    target_min, target_max = get_target_weight(tier)

    message = _build_message(
        concentration_status=conc["concentration_status"],  # type: ignore[arg-type]
        cluster_status=clust["cluster_status"],  # type: ignore[arg-type]
        adds_permitted=adds_permitted,
        trim_recommended=trim_recommended,
        ticker=upper,
    )

    return Framework14Result(
        ticker=upper,
        position_weight_pct=round(weight * 100, 4),
        nav_dollars=nav_dollars,
        position_dollars=position_dollars,
        sizing_tier=tier,
        target_weight_min=target_min,
        target_weight_max=target_max,
        concentration_status=conc["concentration_status"],  # type: ignore[arg-type]
        cap_active=bool(conc["cap_active"]),
        soft_cap_breached=bool(conc["soft_cap_breached"]),
        hard_review_triggered=bool(conc["hard_review_triggered"]),
        grandfathered=bool(conc["grandfathered"]),
        grandfathered_expires_at=conc["grandfathered_expires_at"],  # type: ignore[arg-type]
        grandfathered_expiry_near=bool(conc["grandfathered_expiry_near"]),
        score_display_cap=conc["score_display_cap"],  # type: ignore[arg-type]
        cluster=clust["cluster"],  # type: ignore[arg-type]
        cluster_weight_pct=round(cluster_weight * 100, 4),
        cluster_status=clust["cluster_status"],  # type: ignore[arg-type]
        cluster_yellow_threshold=float(clust["cluster_yellow_threshold"]),  # type: ignore[arg-type]
        cluster_red_threshold=float(clust["cluster_red_threshold"]),  # type: ignore[arg-type]
        adds_permitted=adds_permitted,
        trim_recommended=trim_recommended,
        message=message,
    )
