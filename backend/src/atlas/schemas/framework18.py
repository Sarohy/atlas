"""Pydantic schemas for Framework 18 — 4-Week Trend Gate.

These schemas are the single source of truth for all F18 response shapes.
Consuming frameworks (F6 conviction action, F4 tranche sizing, Factor 9,
F16 master sync) read Framework18SimpleResult only — never the full result.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class F18Status(StrEnum):
    """Framework 18 gate status."""

    ACTIVE = "ACTIVE"
    CLEAR = "CLEAR"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------


class Framework18Actions(BaseModel):
    """Actions applied when the 4-Week Trend Gate is active."""

    model_config = ConfigDict(from_attributes=True)

    reduce_aggressive_adds: bool = Field(
        description="True — all aggressive adds are reduced by add_reduction_pct."
    )
    add_reduction_pct: float = Field(
        description=(
            "Percentage by which add sizes are reduced (from atlas_config, "
            "not hardcoded). E.g. 50.0 means half the normal size."
        )
    )
    prioritize_quality_only: bool = Field(
        description="True — only Tier 1 (score 85+) names may receive reduced adds."
    )
    min_tier_for_new_adds: str = Field(
        description="Minimum tier label permitted for new adds when gate is active."
    )
    no_speculative_starters: bool = Field(
        description=(
            "True — no new positions on tickers not already in the portfolio, "
            "regardless of score or regime."
        )
    )
    tier3_adds_blocked: bool = Field(
        description="True — Tier 3 (score 55-69) names are blocked from any new adds."
    )


# ---------------------------------------------------------------------------
# Simple result (lightweight — for consuming frameworks)
# ---------------------------------------------------------------------------


class Framework18SimpleResult(BaseModel):
    """Lightweight F18 status snapshot consumed by F6, F4, Factor 9, and F16.

    Consuming frameworks call GET /api/v1/framework18/status/simple.
    They NEVER independently check SPY weekly trend.
    """

    model_config = ConfigDict(from_attributes=True)

    f18_status: F18Status = Field(description="ACTIVE / CLEAR / UNKNOWN.")
    f18_active: bool | None = Field(
        description=(
            "True when gate is active, False when clear, "
            "None when SPY data is unavailable (treat as UNKNOWN — block conservatively)."
        )
    )
    consecutive_weeks_down: int | None = Field(
        description="Consecutive SPY weekly price declines from most recent week. None when unavailable."
    )
    consecutive_threshold: int | None = Field(
        description="Threshold from atlas_config. Gate fires at >= this count."
    )
    add_reduction_pct: float | None = Field(
        description="Reduction percentage from atlas_config. None when config unavailable."
    )
    no_speculative_starters: bool = Field(
        description="True when f18_active is True — no new positions on non-portfolio tickers."
    )
    tier3_adds_blocked: bool = Field(
        description="True when f18_active is True — Tier 3 blocked from any new adds."
    )
    data_gap_severity: str = Field(
        description="NONE / PARTIAL / MAJOR / CRITICAL — data availability status."
    )
    spy_data_available: bool = Field(
        description="False when Polygon.io is unreachable and no cache exists."
    )


# ---------------------------------------------------------------------------
# Full result
# ---------------------------------------------------------------------------


class Framework18Result(BaseModel):
    """Full Framework 18 evaluation result.

    Returned by GET /api/v1/framework18/status.
    The simple version strips this down to fields needed by consuming frameworks.
    """

    model_config = ConfigDict(from_attributes=True)

    # ── Gate state ──────────────────────────────────────────────────────────
    f18_status: F18Status = Field(description="ACTIVE / CLEAR / UNKNOWN.")
    f18_active: bool | None = Field(
        description="True = active, False = clear, None = data unavailable."
    )
    consecutive_weeks_down: int | None = Field(
        description="Consecutive declining SPY weeks from most recent. None when data unavailable."
    )
    consecutive_threshold: int | None = Field(
        description="Threshold from atlas_config (NOT hardcoded). Gate fires at >= this."
    )
    add_reduction_pct: float | None = Field(
        description="Add size reduction percentage from atlas_config (NOT hardcoded)."
    )
    weeks_fetched: int | None = Field(
        description="Number of weekly candles fetched (threshold + 1, NOT hardcoded)."
    )

    # ── SPY price data ──────────────────────────────────────────────────────
    spy_weekly_closes: list[float] = Field(
        description=(
            "Most recent completed SPY weekly closes, newest first. "
            "Empty when data unavailable. NEVER filled with dummy data."
        )
    )
    candle_dates: list[str] = Field(
        description="ISO date of each weekly candle (Monday open). Parallel to spy_weekly_closes."
    )

    # ── Data availability ───────────────────────────────────────────────────
    spy_data_available: bool = Field(
        description="True when at least one complete weekly candle set was obtained."
    )
    spy_data_stale: bool = Field(
        description="True when data came from in-memory stale cache rather than live Polygon call."
    )
    polygon_available: bool = Field(
        description="True when live Polygon.io data was obtained for this evaluation."
    )

    # ── Actions (only when active) ──────────────────────────────────────────
    actions: Framework18Actions | None = Field(
        description="Populated only when f18_active is True. Null otherwise."
    )

    # ── Factor 9 contribution ───────────────────────────────────────────────
    factor9_contribution: str | None = Field(
        description="Human-readable Factor 9 (Regime Fit) impact text. Null when data unavailable."
    )

    # ── Data quality ────────────────────────────────────────────────────────
    data_gap_severity: str = Field(
        description="NONE / PARTIAL / MAJOR / CRITICAL."
    )
    warning_messages: list[str] = Field(
        description="Informational warnings about data availability or stale cache use."
    )

    # ── Audit fields ────────────────────────────────────────────────────────
    last_updated: str = Field(description="ISO datetime when this result was computed (UTC).")
    cache_hit: bool = Field(
        description="True when the result was served from in-memory cache without a Polygon call."
    )
