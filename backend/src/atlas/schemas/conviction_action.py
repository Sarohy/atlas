"""Pydantic schemas for the Framework 6 Conviction Action endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConvictionActionResponse(BaseModel):
    """Framework 6 conviction-action guidance for a single ticker.

    Derives an investor action and status from the regime-adjusted Framework
    Score (Framework 1 score modified by Framework 2 Regime Modifier).
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")

    # ── Score context ─────────────────────────────────────────────────────
    base_score: int = Field(
        description="Raw Framework Score before regime adjustment (0-100).",
    )
    adjusted_score: int = Field(
        description="Framework Score after regime modifier applied (0-100). "
        "This is the score used for tier determination.",
    )
    rule: str = Field(
        description="Framework 2 regime rule: CRISIS | CAUTION | CLEAR | NORMAL.",
    )

    # ── Conviction tier ───────────────────────────────────────────────────
    tier_key: str = Field(
        description="Internal tier identifier: HOLD | READY | EARLY | RADAR | EXIT.",
    )
    status: str = Field(
        description="Human-readable status label for the conviction tier.",
    )
    actions: list[str] = Field(
        description="Ordered list of recommended action lines for this tier.",
    )
    tone: str = Field(
        description="UI tone class: green | cyan | yellow | orange | red.",
    )
