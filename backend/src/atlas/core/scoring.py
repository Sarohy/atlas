"""ATLAS conviction score tier classification — single source of truth.

Per ATLAS v7.3.3 Section 13.3.

ALL tier decisions in the system must call ``classify_tier()``.
Never duplicate the band boundaries or label strings elsewhere.

Score bands (inclusive lower bounds, integer comparison):
  >= 85   TIER_1_CORE  — Core position, LEAPS eligible
  78-84   GREY_ZONE    — 3-AI consensus required before any add
  70-77   TIER_2       — GTC adds permitted
  55-69   TIER_3       — Small position only
   < 55   WATCHLIST    — No new capital; exit rules active
"""

from __future__ import annotations

from typing import Final, TypedDict

# ---------------------------------------------------------------------------
# Named band boundaries — the only place these numbers live
# ---------------------------------------------------------------------------

TIER_1_MIN: Final[int] = 85   # score >= 85 → TIER_1_CORE
GREY_ZONE_MIN: Final[int] = 78  # score >= 78 → GREY_ZONE
TIER_2_MIN: Final[int] = 70   # score >= 70 → TIER_2
TIER_3_MIN: Final[int] = 55   # score >= 55 → TIER_3
                               # score <  55 → WATCHLIST

# Tone classes for the frontend CSS (must match ACTION_TONE_CLASS map in panel)
_TONE_TIER1: Final[str] = "tone-green"
_TONE_GREY: Final[str] = "tone-purple"
_TONE_TIER2: Final[str] = "tone-blue"
_TONE_TIER3: Final[str] = "tone-yellow"
_TONE_WATCHLIST: Final[str] = "tone-red"


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


class TierResult(TypedDict):
    """Full tier result returned by ``classify_tier()``.

    All callers receive this dict and should use its fields — never re-derive
    tier logic from the score independently.
    """

    tier: str             # machine-readable key, e.g. "TIER_1_CORE"
    tier_label: str       # display label, e.g. "TIER 1 CORE"
    action: str           # short action text for the panel pill
    action_tone: str      # CSS tone class used by the frontend
    score_band: str       # human-readable band, e.g. "85-100"
    band_min: int         # inclusive lower bound
    band_max: int         # inclusive upper bound (999 = no ceiling)
    target_size_min: float  # % of NAV minimum target (0.0-1.0 fraction)
    target_size_max: float  # % of NAV maximum target (0.0-1.0 fraction)
    leaps_eligible: bool
    adds_permitted: bool


# ---------------------------------------------------------------------------
# Single source of truth
# ---------------------------------------------------------------------------


def classify_tier(score: float) -> TierResult:
    """Map a conviction score to a full tier result.

    Uses ``int(score)`` for comparison so floating-point boundary values such
    as 69.9 are treated as 69 (Tier 3), never as 70 (Tier 2).

    Pure function — no I/O, no side effects.

    Parameters
    ----------
    score:
        Regime-adjusted (or pre-regime) Framework 1 conviction score [0-100].
        The caller is responsible for passing the correct score.
    """
    # Integer conversion first — spec uses integer bands (Rule 4).
    s: int = int(score)

    if s >= TIER_1_MIN:
        return TierResult(
            tier="TIER_1_CORE",
            tier_label="TIER 1 CORE",
            action="LEAPS ELIGIBLE",
            action_tone=_TONE_TIER1,
            score_band="85-100",
            band_min=TIER_1_MIN,
            band_max=100,
            target_size_min=2.0,
            target_size_max=5.0,
            leaps_eligible=True,
            adds_permitted=True,
        )

    if s >= GREY_ZONE_MIN:
        return TierResult(
            tier="GREY_ZONE",
            tier_label="GREY ZONE",
            action="3-AI CONSENSUS REQUIRED",
            action_tone=_TONE_GREY,
            score_band="78-84",
            band_min=GREY_ZONE_MIN,
            band_max=84,
            target_size_min=1.5,
            target_size_max=2.0,
            leaps_eligible=False,
            adds_permitted=True,
        )

    if s >= TIER_2_MIN:
        return TierResult(
            tier="TIER_2",
            tier_label="TIER 2",
            action="GTC ADDS PERMITTED",
            action_tone=_TONE_TIER2,
            score_band="70-77",
            band_min=TIER_2_MIN,
            band_max=77,
            target_size_min=0.5,
            target_size_max=1.5,
            leaps_eligible=False,
            adds_permitted=True,
        )

    if s >= TIER_3_MIN:
        return TierResult(
            tier="TIER_3",
            tier_label="TIER 3",
            action="SMALL POSITION ONLY",
            action_tone=_TONE_TIER3,
            score_band="55-69",
            band_min=TIER_3_MIN,
            band_max=69,
            target_size_min=0.25,
            target_size_max=0.5,
            leaps_eligible=False,
            adds_permitted=True,
        )

    # score < 55 → WATCHLIST
    return TierResult(
        tier="WATCHLIST",
        tier_label="WATCHLIST",
        action="NO NEW CAPITAL",
        action_tone=_TONE_WATCHLIST,
        score_band="0-54",
        band_min=0,
        band_max=54,
        target_size_min=0.0,
        target_size_max=0.0,
        leaps_eligible=False,
        adds_permitted=False,
    )
