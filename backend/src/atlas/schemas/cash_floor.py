"""Pydantic schemas for the Framework 5 Cash Floor endpoint.

Provides two response models:
  - Framework5Response : portfolio-level status (new GET /cash-floor/status endpoint)
  - CashFloorResponse  : legacy per-ticker response (kept for backward compatibility)
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Floor status enumeration
# ---------------------------------------------------------------------------


class FloorStatus(StrEnum):
    """Categorised cash floor status from most healthy to most critical."""

    HEALTHY = "HEALTHY"
    LOW_BUFFER = "LOW_BUFFER"
    AT_FLOOR = "AT_FLOOR"
    BELOW_FLOOR = "BELOW_FLOOR"
    CRITICAL_ZERO = "CRITICAL_ZERO"


# ---------------------------------------------------------------------------
# Portfolio-level response — GET /cash-floor/status
# ---------------------------------------------------------------------------


class Framework5Response(BaseModel):
    """Framework 5 — portfolio-level cash floor status.

    Derived entirely from:
      1. Framework 2 (Regime Modifier) for regime / Brent / VIX.
      2. Portfolio database for total NAV, cash balance, CLEAR transition date.
      3. Framework 13 for effective portfolio beta.
    """

    model_config = ConfigDict(from_attributes=True)

    # ── Regime context (from Framework 2) ────────────────────────────────
    regime: str = Field(
        description="Active regime: CLEAR | SOFT CAUTION | CAUTION | CRISIS HALT.",
    )
    brent_price: float | None = Field(
        description="Brent crude price in USD per barrel at evaluation time.",
    )
    vix_value: float | None = Field(
        description="CBOE VIX index level at evaluation time.",
    )

    # ── Floor percentages ─────────────────────────────────────────────────
    floor_pct: float = Field(
        description="Active floor fraction (e.g. 0.20 = 20%).",
    )
    floor_pct_display: str = Field(
        description="Human-readable floor display, e.g. '30%+' or '10% (transition — 7 days)'.",
    )

    # ── Floor USD amounts ─────────────────────────────────────────────────
    floor_amount: float = Field(
        description="Minimum cash floor in USD (floor_pct * total_nav).",
    )
    total_nav: float = Field(
        description="Total portfolio NAV in USD (invested + cash).",
    )
    total_cash: float = Field(
        description="Current cash balance in USD.",
    )
    cash_pct: float = Field(
        description="Cash as a fraction of NAV.",
    )
    buffer: float = Field(
        description="Cash above the floor in USD (0 when below floor).",
    )
    buffer_pct: float = Field(
        description="Buffer as a fraction of NAV (0 when below floor).",
    )
    available_above_floor: float = Field(
        description="Deployable cash above floor in USD.",
    )
    shortfall: float = Field(
        description="Deficit below floor in USD (0 when healthy).",
    )
    is_below_floor: bool = Field(
        description="True when total_cash < floor_amount.",
    )

    # ── Status and warnings ───────────────────────────────────────────────
    floor_status: FloorStatus = Field(
        description="Categorised floor status.",
    )
    warning_level: str = Field(
        description="NONE | AMBER | CRITICAL.",
    )
    warning_message: str | None = Field(
        description="Warning text when applicable, null when NONE.",
    )
    deployment_permitted: bool = Field(
        description="False when cash is at or below the floor.",
    )

    # ── CLEAR transition ──────────────────────────────────────────────────
    transition_active: bool = Field(
        description="True during the 2-week post-CLEAR transition period.",
    )
    transition_floor_pct: float | None = Field(
        description="Transition floor (0.10) when active, null otherwise.",
    )
    days_until_settled: int | None = Field(
        description="Days until floor drops from 10% to 8%; null when not transitioning.",
    )
    clear_transition_date: str | None = Field(
        description="ISO 8601 date when CLEAR regime started; null when not CLEAR.",
    )

    # ── Effective beta (from Framework 13) ───────────────────────────────
    effective_beta: float = Field(
        description="Portfolio weighted beta * (1 - cash_pct).",
    )
    target_beta: float = Field(
        description="Target effective beta (1.75 per ATLAS spec).",
    )
    beta_status: str = Field(
        description="NORMAL | ELEVATED | CRITICAL.",
    )

    # ── Floor breach ──────────────────────────────────────────────────────
    floor_breach_available: bool = Field(
        description="True when no breach has been used this quarter.",
    )
    breach_count_this_quarter: int = Field(
        description="Floor breaches used this quarter (0 or 1 maximum).",
    )

    # ── Human-readable rationale ──────────────────────────────────────────
    rationale: str = Field(
        description="Regime floor rationale; overridden when below floor.",
    )


# ---------------------------------------------------------------------------
# Legacy per-ticker response — GET /cash-floor/{ticker}
# ---------------------------------------------------------------------------


class CashFloorResponse(BaseModel):
    """Framework 5 cash floor guidance for a single ticker (legacy endpoint).

    Kept for backward compatibility. New integrations should use
    Framework5Response from GET /cash-floor/status instead.
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")

    # ── Regime context ────────────────────────────────────────────────────
    rule_triggered: int | None = Field(
        default=None,
        description="Framework 2 rule: 1=CRISIS HALT, 2=CAUTION, 3=SOFT CAUTION, 4=CLEAR.",
    )
    brent_price: float | None = Field(
        default=None,
        description="Brent crude price in USD per barrel at time of evaluation.",
    )
    vix_value: float | None = Field(
        default=None,
        description="CBOE VIX index level at time of evaluation.",
    )

    # ── Cash floor output ─────────────────────────────────────────────────
    condition: str = Field(
        description="Regime condition: CRISIS HALT | CAUTION | SOFT CAUTION | CLEAR | FULLY_DEPLOYED.",  # noqa: E501
    )
    rationale: str = Field(
        description="Human-readable rationale for the floor requirement.",
    )

    # Percentages expressed as fractions (0.20 = 20 %).
    floor_pct_min: float = Field(
        description="Minimum cash floor as a fraction of total NAV.",
    )
    floor_pct_max: float = Field(
        description="Maximum cash floor as a fraction of total NAV.",
    )

    # USD amounts — None when no portfolio data is available.
    position_value_usd: float | None = Field(
        default=None,
        description="Total portfolio NAV in USD (invested_value + cash_balance).",
    )
    floor_usd_min: float | None = Field(
        default=None,
        description="Minimum cash to hold in USD. None when total NAV is unavailable.",
    )
    floor_usd_max: float | None = Field(
        default=None,
        description="Maximum cash to hold in USD. None when total NAV is unavailable.",
    )
    cash_balance: float | None = Field(
        default=None,
        description="Current portfolio cash balance in USD.",
    )
