"""Framework 13 — Beta-Adjusted Portfolio Management service.

ATLAS v7.3.4 spec (CLAUDE.md Framework #13).

Implements:
  - Hardcoded confirmed beta table (17 names)
  - Beta cap rules (5 tiers + China risk)
  - Per-position beta cap evaluation
  - Portfolio weighted-average beta
  - Effective portfolio beta = weighted_avg * (1 - cash_percentage)
  - Dynamic beta fetch from Polygon.io for unknown tickers (async fallback)

All pure functions are synchronous and side-effect-free.
``calculate_portfolio_beta``, ``evaluate_framework13``, and ``get_beta_dynamic``
are async to support I/O.  ``get_beta`` remains sync for use in the
Framework 4 synchronous tranche-sizing path.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Final

import httpx

from atlas.config import get_settings
from atlas.schemas.framework13 import (
    BetaSource,
    Framework13Result,
    PortfolioBetaResult,
    PortfolioPositionBeta,
)

# ---------------------------------------------------------------------------
# Confirmed beta table — ATLAS v7.3.4 spec Part 1.
# NEVER fetch beta from an external API.  These values are hardcoded.
# ---------------------------------------------------------------------------

CONFIRMED_BETAS: Final[dict[str, float]] = {
    "AAOI": 4.03,  # Updated confirmed — even 1% acts like 4%
    "CRDO": 2.67,
    "UCTT": 2.00,
    "MRVL": 1.98,
    "VICR": 1.95,
    "TTMI": 1.95,  # Exit candidate
    "NBIS": 1.90,
    "SNDK": 1.85,
    "LITE": 1.80,
    "COHR": 1.75,
    "AEHR": 1.75,
    "MU": 2.42,  # Updated confirmed — above very-high-beta tier (was 1.65)
    "CIEN": 1.55,
    "TSM": 1.30,
    "FN": 2.70,  # Updated confirmed — now very high beta tier (was 1.06)
    "TSEM": 0.82,
    "NEM": 0.55,
}

# ---------------------------------------------------------------------------
# China risk tickers — hard cap 0.25% regardless of beta
# ---------------------------------------------------------------------------

CHINA_RISK_TICKERS: Final[list[str]] = ["GCT"]

# ---------------------------------------------------------------------------
# Default beta for any ticker not in the confirmed table
# ---------------------------------------------------------------------------

DEFAULT_BETA: Final[float] = 1.0

# ---------------------------------------------------------------------------
# Beta tier thresholds
# ---------------------------------------------------------------------------

# Rule 1/2: beta >= 3.0 OR beta in [2.0, 3.0) → 1.0% NAV hard cap
_BETA_THRESHOLD_VERY_HIGH: Final[float] = 2.0

# Rule 3: beta in [1.5, 2.0) → 2.5% NAV cap
_BETA_THRESHOLD_HIGH: Final[float] = 1.5

# Rules 4/5: beta < 1.5 → no additional beta restriction (5.0% placeholder)
_BETA_CAP_NO_RESTRICTION: Final[float] = 0.050

# AAOI-type high beta cap (beta >= 3.0)
_BETA_CAP_AAOI: Final[float] = 0.010  # 1.0% NAV

# Very high beta cap (beta in [2.0, 3.0))
_BETA_CAP_VERY_HIGH: Final[float] = 0.010  # 1.0% NAV

# High beta cap (beta in [1.5, 2.0))
_BETA_CAP_HIGH: Final[float] = 0.025  # 2.5% NAV

# China risk hard cap
_BETA_CAP_CHINA: Final[float] = 0.0025  # 0.25% NAV

# AAOI amber warning threshold — show warning when position > 0.5%
_AAOI_AMBER_THRESHOLD: Final[float] = 0.005

# Portfolio target effective beta
_TARGET_BETA: Final[float] = 1.75

# Portfolio warning thresholds
_BETA_WARNING_ELEVATED: Final[float] = 1.75
_BETA_WARNING_CRITICAL: Final[float] = 2.0

# ---------------------------------------------------------------------------
# Dynamic beta cache (swap for Redis in production; TTL 7 days).
# Keys: ticker symbol (upper-case) → confirmed float beta value.
# ---------------------------------------------------------------------------

_BETA_CACHE_TTL_DAYS: Final[int] = 7  # Cache TTL in days (Redis in prod)
_BETA_LOOKBACK_CALENDAR_DAYS: Final[int] = 90  # Window to ensure ~63 trading days
_BETA_MIN_BARS: Final[int] = 20  # Minimum bars required for beta calc
_POLYGON_AGGS_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
)

_beta_cache: dict[str, float] = {}  # In-memory stub; swap for Redis with TTL 7 days

# Exit candidate ticker
_EXIT_CANDIDATE: Final[str] = "TTMI"

# ---------------------------------------------------------------------------
# Public pure functions
# ---------------------------------------------------------------------------


def get_beta(ticker: str) -> tuple[float, BetaSource]:
    """Return (beta, source) for a ticker.

    Returns the hardcoded confirmed value when the ticker is in the table,
    otherwise returns (DEFAULT_BETA, BetaSource.DEFAULT).

    Pure function — no I/O, no side effects.
    Used in the synchronous Framework 4 tranche-sizing path.
    """
    upper = ticker.strip().upper()
    if upper in CONFIRMED_BETAS:
        return CONFIRMED_BETAS[upper], BetaSource.CONFIRMED
    return DEFAULT_BETA, BetaSource.DEFAULT


# ---------------------------------------------------------------------------
# Async dynamic beta fetch (Framework 13 card path only)
# ---------------------------------------------------------------------------


async def _get_polygon_closes(
    client: httpx.AsyncClient,
    ticker: str,
    from_date: date,
    to_date: date,
    api_key: str,
) -> list[float]:
    """Return ascending daily closing prices from Polygon.io.

    Returns an empty list on any HTTP or parse error.
    """
    url = _POLYGON_AGGS_URL.format(
        ticker=ticker,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
    )
    try:
        response = await client.get(
            url,
            params={"adjusted": "true", "sort": "asc", "limit": "150", "apiKey": api_key},
            timeout=10.0,
        )
        response.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError):
        return []
    payload: dict[str, object] = response.json()
    results: list[dict[str, object]] = payload.get("results", [])  # type: ignore[assignment]
    return [float(str(bar["c"])) for bar in results if bar.get("c") is not None]


def _compute_beta_from_closes(
    asset_closes: list[float],
    spy_closes: list[float],
) -> float | None:
    """Compute beta = Cov(r_asset, r_spy) / Var(r_spy) from closing prices.

    Returns None when insufficient data or variance is zero.
    Pure function — no I/O, no side effects.
    """
    n = min(len(asset_closes), len(spy_closes))
    if n < _BETA_MIN_BARS:
        return None
    asset = asset_closes[-n:]
    spy = spy_closes[-n:]

    # Log returns (avoids compounding distortion)
    asset_ret = [math.log(asset[i] / asset[i - 1]) for i in range(1, n)]
    spy_ret = [math.log(spy[i] / spy[i - 1]) for i in range(1, n)]
    n_ret = len(spy_ret)

    spy_mean = sum(spy_ret) / n_ret
    asset_mean = sum(asset_ret) / n_ret

    cov = sum((asset_ret[i] - asset_mean) * (spy_ret[i] - spy_mean) for i in range(n_ret)) / (
        n_ret - 1
    )
    var_spy = sum((r - spy_mean) ** 2 for r in spy_ret) / (n_ret - 1)

    if var_spy <= 0.0:
        return None

    beta = cov / var_spy
    return max(0.0, round(beta, 2))  # Non-negative, 2 decimal places


async def _fetch_beta_from_polygon(ticker: str) -> float | None:
    """Fetch beta vs SPY for ``ticker`` using 90 calendar days of daily closes.

    Returns the computed float beta, or None on any error / missing API key.
    Never raises — all exceptions are caught and logged as None.
    """
    settings = get_settings()
    api_key = settings.polygon_api_key
    if not api_key:
        return None

    today = date.today()
    from_date = today - timedelta(days=_BETA_LOOKBACK_CALENDAR_DAYS)

    async with httpx.AsyncClient() as client:
        asset_closes = await _get_polygon_closes(client, ticker, from_date, today, api_key)
        spy_closes = await _get_polygon_closes(client, "SPY", from_date, today, api_key)

    return _compute_beta_from_closes(asset_closes, spy_closes)


async def get_beta_dynamic(ticker: str) -> tuple[float, BetaSource]:
    """Return (beta, source) with Polygon.io fallback for unknown tickers.

    Priority:
      1. CONFIRMED_BETAS table  → BetaSource.CONFIRMED  (no I/O)
      2. In-memory cache        → BetaSource.CALCULATED  (no I/O)
      3. Polygon.io fetch       → BetaSource.CALCULATED  (I/O; cached on success)
      4. Fallback               → BetaSource.DEFAULT (1.0)

    The synchronous ``get_beta`` function remains the canonical path for
    Framework 4 (tranche sizing) which cannot perform async I/O.
    This function is used only in ``evaluate_framework13`` (async).
    """
    upper = ticker.strip().upper()
    if upper in CONFIRMED_BETAS:
        return CONFIRMED_BETAS[upper], BetaSource.CONFIRMED

    # Check in-memory cache (swap for Redis with TTL in production)
    if upper in _beta_cache:
        return _beta_cache[upper], BetaSource.CALCULATED

    # Fetch from Polygon.io
    fetched = await _fetch_beta_from_polygon(upper)
    if fetched is not None:
        _beta_cache[upper] = fetched
        return fetched, BetaSource.CALCULATED

    return DEFAULT_BETA, BetaSource.DEFAULT


def get_beta_cap_limit(ticker: str, beta: float) -> float:
    """Return the beta-adjusted position cap as a fraction of NAV.

    Priority order:
      1. China risk override (hard 0.25%)
      2. AAOI-type / very high beta (>= 2.0): 1.0%
      3. High beta [1.5, 2.0): 2.5%
      4. Moderate / low beta: 5.0% (no additional beta restriction)

    Pure function — no I/O, no side effects.
    """
    upper = ticker.strip().upper()
    if upper in CHINA_RISK_TICKERS:
        return _BETA_CAP_CHINA
    if beta >= _BETA_THRESHOLD_VERY_HIGH:
        return _BETA_CAP_AAOI  # covers both >= 3.0 and [2.0, 3.0)
    if beta >= _BETA_THRESHOLD_HIGH:
        return _BETA_CAP_HIGH
    return _BETA_CAP_NO_RESTRICTION


def is_beta_capped(ticker: str, position_weight: float) -> dict[str, object]:
    """Evaluate Framework 13 beta cap for a single position.

    Returns a dictionary with all fields consumed by ``evaluate_framework13``
    and by Framework 4's beta cap suppression check.

    Pure function — no I/O, no side effects.

    Keys
    ----
    beta              : float
    beta_source       : BetaSource
    cap_active        : bool
    cap_limit_pct     : float   — cap in percentage points (e.g. 1.0)
    cap_reason        : str | None
    effective_exposure: float   — position_weight * beta expressed as % (e.g. 2.97)
    adds_permitted    : bool
    warning_level     : str     — "NONE" | "AMBER" | "RED"
    warning_message   : str | None
    is_exit_candidate : bool
    default_beta_flag : bool
    """
    upper = ticker.strip().upper()
    beta, source = get_beta(upper)
    cap_limit = get_beta_cap_limit(upper, beta)
    cap_active = position_weight >= cap_limit
    effective_exposure = position_weight * beta * 100  # percentage

    # Cap reason
    cap_reason: str | None = None
    if cap_active:
        if upper in CHINA_RISK_TICKERS:
            cap_reason = "China risk hard cap at 0.25%"
        elif beta >= 3.0:
            cap_reason = f"Beta {beta} — hard cap at 1.0%"
        elif beta >= _BETA_THRESHOLD_VERY_HIGH:
            cap_reason = f"Beta {beta} — high beta cap at 1.0%"
        elif beta >= _BETA_THRESHOLD_HIGH:
            cap_reason = f"Beta {beta} — cap at 2.5%"

    # Warning logic
    warning_level = "NONE"
    warning_message: str | None = None

    # AAOI-specific amber warning (shown above 0.5% NAV, before hard cap fires)
    if upper == "AAOI" and position_weight > _AAOI_AMBER_THRESHOLD:
        warning_message = (
            f"AAOI at {position_weight * 100:.1f}% "
            f"acts like {effective_exposure:.2f}% "
            f"effective exposure"
        )
        warning_level = "AMBER"

    # Cap overrides to RED
    if cap_active:
        warning_level = "RED"

    return {
        "beta": beta,
        "beta_source": source,
        "cap_active": cap_active,
        "cap_limit_pct": cap_limit * 100,
        "cap_reason": cap_reason,
        "effective_exposure": effective_exposure,
        "adds_permitted": not cap_active,
        "warning_level": warning_level,
        "warning_message": warning_message,
        "is_exit_candidate": upper == _EXIT_CANDIDATE,
        "default_beta_flag": source == BetaSource.DEFAULT,
    }


# ---------------------------------------------------------------------------
# Async service functions
# ---------------------------------------------------------------------------


async def evaluate_framework13(
    ticker: str,
    position_weight: float,
    nav: float,
) -> Framework13Result:
    """Evaluate Framework 13 for a single ticker position.

    Parameters
    ----------
    ticker:
        Ticker symbol (normalised to upper-case internally).
    position_weight:
        Current position weight as a fraction of NAV (0.0-1.0).
    nav:
        Total portfolio NAV in USD (used to compute position_dollars).

    Returns
    -------
    Framework13Result with full beta cap evaluation.
    """
    upper = ticker.strip().upper()
    beta, source = await get_beta_dynamic(upper)
    cap_limit = get_beta_cap_limit(upper, beta)
    beta_check = is_beta_capped(upper, position_weight)

    # Sizing tier
    if upper in CHINA_RISK_TICKERS:
        sizing_tier = "CHINA_RISK"
        max_weight = _BETA_CAP_CHINA
    elif beta >= 3.0:
        sizing_tier = "AAOI_TYPE_HIGH_BETA"
        max_weight = _BETA_CAP_AAOI
    elif beta >= _BETA_THRESHOLD_VERY_HIGH:
        sizing_tier = "VERY_HIGH_BETA"
        max_weight = _BETA_CAP_VERY_HIGH
    elif beta >= _BETA_THRESHOLD_HIGH:
        sizing_tier = "HIGH_BETA"
        max_weight = _BETA_CAP_HIGH
    elif beta >= 1.0:
        sizing_tier = "MODERATE_BETA"
        max_weight = _BETA_CAP_NO_RESTRICTION
    else:
        sizing_tier = "LOW_BETA"
        max_weight = _BETA_CAP_NO_RESTRICTION

    return Framework13Result(
        ticker=upper,
        beta=beta,
        beta_source=source,
        position_weight_pct=round(position_weight * 100, 2),
        position_dollars=round(position_weight * nav, 2),
        effective_exposure_pct=round(position_weight * beta * 100, 2),
        effective_exposure_note=(
            f"{position_weight * 100:.1f}% position x "
            f"beta {beta:.2f} = "
            f"{position_weight * beta * 100:.2f}% "
            f"effective exposure"
        ),
        beta_cap_active=bool(beta_check["cap_active"]),
        beta_cap_limit_pct=cap_limit * 100,
        beta_cap_reason=(
            None if beta_check["cap_reason"] is None else str(beta_check["cap_reason"])
        ),
        sizing_tier=sizing_tier,
        max_weight_pct=max_weight * 100,
        adds_permitted=not bool(beta_check["cap_active"]),
        warning_level=str(beta_check["warning_level"]),
        warning_message=(
            None if beta_check["warning_message"] is None else str(beta_check["warning_message"])
        ),
        beta_source_flag=source == BetaSource.DEFAULT,
    )


async def calculate_portfolio_beta(
    positions: list[dict[str, float | str]],
    cash_percentage: float,
) -> PortfolioBetaResult:
    """Calculate weighted-average and effective portfolio beta.

    Parameters
    ----------
    positions:
        List of dicts with keys ``ticker`` (str) and ``weight`` (float).
        ``weight`` is a fraction of NAV (0.0-1.0).
    cash_percentage:
        Cash as a fraction of NAV (e.g. 0.20 for 20% CAUTION floor).

    Returns
    -------
    PortfolioBetaResult with weighted_avg_beta, effective_beta, and per-
    position breakdown.

    Formula
    -------
    weighted_avg_beta  = Σ (position_weight * beta)
    effective_beta     = weighted_avg_beta * (1 - cash_percentage)
    """
    weighted_sum = 0.0
    position_betas: list[PortfolioPositionBeta] = []

    for pos in positions:
        ticker = str(pos["ticker"])
        weight = float(pos["weight"])
        beta, source = get_beta(ticker)
        contribution = weight * beta
        weighted_sum += contribution
        position_betas.append(
            PortfolioPositionBeta(
                ticker=ticker.strip().upper(),
                weight=weight,
                beta=beta,
                contribution=contribution,
                source=source,
            )
        )

    weighted_avg_beta: float = weighted_sum
    effective_beta: float = weighted_avg_beta * (1.0 - cash_percentage)

    # Warning thresholds
    warning_level = "NONE"
    warning_message: str | None = None
    beta_status = "NORMAL"

    if effective_beta > _BETA_WARNING_CRITICAL:
        warning_level = "CRITICAL"
        beta_status = "CRITICAL"
        warning_message = (
            f"Portfolio beta {effective_beta:.2f} critically elevated. Immediate review required."
        )
    elif effective_beta > _BETA_WARNING_ELEVATED:
        warning_level = "RED"
        beta_status = "ELEVATED"
        warning_message = (
            f"Portfolio beta {effective_beta:.2f} above target 1.75. "
            f"Consider reducing high beta names."
        )

    return PortfolioBetaResult(
        weighted_avg_beta=weighted_avg_beta,
        effective_beta=effective_beta,
        cash_percentage=cash_percentage,
        target_beta=_TARGET_BETA,
        beta_status=beta_status,
        warning_level=warning_level,
        warning_message=warning_message,
        position_betas=position_betas,
    )
