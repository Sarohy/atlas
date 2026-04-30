"""Pydantic schemas for the F4 Options Flow endpoint.

F4 has five sub-indicators with internal weights (per Factor_Mapping_Guide):
  1. Whale Block Size      — largest single premium print        (35%)
  2. Call/Put Ratio        — call premium vs put premium today   (20%)
  3. Volume vs OI          — options volume relative to OI       (20%)
  4. Dark Pool Print       — off-exchange block size             (15%)
  5. Sweep Type            — golden sweep / single / block       (10%)

F4 = (whale × 0.35) + (cp_ratio × 0.20) + (vol_oi × 0.20)
    + (dark_pool × 0.15) + (sweep × 0.10)

Collar flag: if a collar structure is detected, F4 is capped at 68.

Signal hierarchy (for display):
  GOLD   — Golden Sweep >$5M multi-exchange
  BLUE   — Whale Block  >$1M single print
  GREEN  — Repeated Hits >$500K same strike multiple times
  YELLOW — Unusual Volume >3× OI
  GREY   — Dark Pool print >$100K at key level
  WHITE  — Normal elevated call activity
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class SignalTier:
    """Named constants for F4 signal hierarchy tiers."""

    GOLD: Final[str] = "GOLD"
    BLUE: Final[str] = "BLUE"
    GREEN: Final[str] = "GREEN"
    YELLOW: Final[str] = "YELLOW"
    GREY: Final[str] = "GREY"
    WHITE: Final[str] = "WHITE"
    NONE: Final[str] = "NONE"


class F4Grade:
    """Named constants for the five F4 grade labels."""

    STRONG_BUY: Final[str] = "STRONG BUY"
    BUY: Final[str] = "BUY"
    NEUTRAL: Final[str] = "NEUTRAL"
    WEAK: Final[str] = "WEAK"
    AVOID: Final[str] = "AVOID"


# ---------------------------------------------------------------------------
# Sub-indicator schemas
# ---------------------------------------------------------------------------


class WhaleBlockIndicator(BaseModel):
    """Largest single premium print detected in today's flow.

    Scoring rule (0-100):
      >$5M → 100 (Golden Sweep) | $1-5M → 85 | $500K-1M → 70
      $100K-500K → 50 | <$100K → 30
    Weight in F4: 35%
    """

    model_config = ConfigDict(from_attributes=True)

    largest_premium: float | None = Field(
        None, description="Largest single-print premium in USD. Null when no flow data."
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.35, description="Weight in F4 formula.")


class CallPutRatioIndicator(BaseModel):
    """Call premium vs put premium ratio for today's session.

    Scoring rule (0-100):
      >3:1 → 100 | 2-3:1 → 85 | 1.5-2:1 → 70 | ~1:1 → 50 | Put heavy → 20
    Weight in F4: 20%
    """

    model_config = ConfigDict(from_attributes=True)

    call_premium: float | None = Field(None, description="Total call premium today (USD).")
    put_premium: float | None = Field(None, description="Total put premium today (USD).")
    ratio: float | None = Field(
        None, description="call_premium / put_premium. Null when no premium data."
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.20, description="Weight in F4 formula.")


class VolumeOiIndicator(BaseModel):
    """Options volume relative to open interest (call side, today).

    Scoring rule (0-100):
      >5× → 100 | 3-5× → 85 | 2-3× → 70 | 1-2× → 55 | <1× → 30
    Weight in F4: 20%
    """

    model_config = ConfigDict(from_attributes=True)

    call_volume: float | None = Field(None, description="Total call volume today.")
    call_open_interest: float | None = Field(None, description="Call open interest.")
    vol_oi_ratio: float | None = Field(
        None, description="call_volume / call_open_interest. Null when OI is zero."
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.20, description="Weight in F4 formula.")


class DarkPoolIndicator(BaseModel):
    """Off-exchange dark pool print activity for today.

    Scoring rule (0-100):
      Large block at key level → 100 | Large block off-exchange → 80
      Normal DP activity → 50 | None → 30
    Thresholds: >$5M → 100 | $1-5M → 80 | $100K-1M → 50 | <$100K or none → 30
    Weight in F4: 15%
    """

    model_config = ConfigDict(from_attributes=True)

    total_dark_pool_premium: float | None = Field(
        None, description="Sum of all dark pool print premiums today (USD)."
    )
    largest_print: float | None = Field(
        None, description="Single largest dark pool print (USD)."
    )
    print_count: int = Field(default=0, description="Number of dark pool prints today.")
    direction: str | None = Field(
        default=None,
        description=(
            "'BULLISH' | 'BEARISH' | 'NEUTRAL' — inferred from call/put premium ratio. "
            "None when premium data is unavailable."
        ),
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.15, description="Weight in F4 formula.")


class SweepTypeIndicator(BaseModel):
    """Highest sweep signal type detected in today's flow alerts.

    Scoring rule (0-100):
      Golden Sweep (multi-exchange >$5M) → 100 | Single sweep → 80
      Repeated hits → 75 | Block → 65 | Normal → 40
    Weight in F4: 10%
    """

    model_config = ConfigDict(from_attributes=True)

    has_golden_sweep: bool = Field(
        default=False, description="True if a multi-exchange sweep >$5M was detected."
    )
    has_single_sweep: bool = Field(
        default=False, description="True if any sweep was detected."
    )
    has_repeated_hits: bool = Field(
        default=False, description="True if repeated hits on same strike detected."
    )
    sweep_premium: float | None = Field(
        None, description="Premium of the largest sweep detected (USD)."
    )
    score: int = Field(ge=0, le=100, description="Raw indicator score (0-100).")
    weight: float = Field(default=0.10, description="Weight in F4 formula.")


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------


class OptionsFlowResponse(BaseModel):
    """Complete F4 Options Flow analysis for a single ticker.

    F4 = (whale_block.score × 0.35) + (call_put_ratio.score × 0.20)
       + (volume_oi.score × 0.20) + (dark_pool.score × 0.15)
       + (sweep_type.score × 0.10)

    Collar cap: score is hard-capped at 68 when collar_flag is True.
    """

    model_config = ConfigDict(from_attributes=True)

    ticker: str = Field(description="Ticker symbol (upper-case).")
    whale_block: WhaleBlockIndicator
    call_put_ratio: CallPutRatioIndicator
    volume_oi: VolumeOiIndicator
    dark_pool: DarkPoolIndicator
    sweep_type: SweepTypeIndicator
    signal_tier: str = Field(
        description="Highest signal detected: GOLD | BLUE | GREEN | YELLOW | GREY | WHITE | NONE"
    )
    collar_flag: bool = Field(
        default=False,
        description=(
            "True when a collar structure (protective puts + covered calls) is detected. "
            "Indicates hedging, not conviction buying. Caps F4 at 68."
        ),
    )
    f4_score: int = Field(
        ge=0, le=100, description="Composite F4 Options Flow score (0-100)."
    )
    f4_grade: str = Field(description="F4 grade: STRONG BUY | BUY | NEUTRAL | WEAK | AVOID")
