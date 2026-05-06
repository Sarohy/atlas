"""ATLAS conviction score tier classification — single source of truth.

Per ATLAS v7.3.5 Section 13.3.

ALL tier decisions in the system must call ``classify_tier()``.
Never duplicate the band boundaries or label strings elsewhere.

Score bands (inclusive lower bounds, integer comparison):
  >= 85   T1_ELITE  — Core position, LEAPS eligible, 5-10% NAV
  80-84   T1        — Core position, 2-4% NAV
  70-79   T2        — Starter position, 0.5-1.5% NAV
  50-69   T3        — Small speculative position, ≤ 0.5% NAV
   < 50   BELOW_GATE — No new capital; exit rules active
"""

from __future__ import annotations

from typing import Final, TypedDict

# ---------------------------------------------------------------------------
# Named band boundaries — the only place these numbers live
# ---------------------------------------------------------------------------

TIER_1_ELITE_MIN: Final[int] = 85  # score >= 85 → T1_ELITE
TIER_1_MIN: Final[int] = 80        # score >= 80 → T1
TIER_2_MIN: Final[int] = 70        # score >= 70 → T2
TIER_3_MIN: Final[int] = 50        # score >= 50 → T3
                                   # score <  50 → BELOW_GATE

# Tone classes for the frontend CSS (must match ACTION_TONE_CLASS map in panel)
_TONE_T1_ELITE: Final[str] = "tone-green"
_TONE_T1: Final[str] = "tone-teal"
_TONE_TIER2: Final[str] = "tone-blue"
_TONE_TIER3: Final[str] = "tone-yellow"
_TONE_BELOW_GATE: Final[str] = "tone-red"


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

    if s >= TIER_1_ELITE_MIN:
        return TierResult(
            tier="T1_ELITE",
            tier_label="T1 ELITE",
            action="LEAPS ELIGIBLE",
            action_tone=_TONE_T1_ELITE,
            score_band="85-100",
            band_min=TIER_1_ELITE_MIN,
            band_max=100,
            target_size_min=5.0,
            target_size_max=10.0,
            leaps_eligible=True,
            adds_permitted=True,
        )

    if s >= TIER_1_MIN:
        return TierResult(
            tier="T1",
            tier_label="T1",
            action="CORE POSITION",
            action_tone=_TONE_T1,
            score_band="80-84",
            band_min=TIER_1_MIN,
            band_max=84,
            target_size_min=2.0,
            target_size_max=4.0,
            leaps_eligible=False,
            adds_permitted=True,
        )

    if s >= TIER_2_MIN:
        return TierResult(
            tier="T2",
            tier_label="T2",
            action="GTC ADDS PERMITTED",
            action_tone=_TONE_TIER2,
            score_band="70-79",
            band_min=TIER_2_MIN,
            band_max=79,
            target_size_min=0.5,
            target_size_max=1.5,
            leaps_eligible=False,
            adds_permitted=True,
        )

    if s >= TIER_3_MIN:
        return TierResult(
            tier="T3",
            tier_label="T3",
            action="SMALL POSITION ONLY",
            action_tone=_TONE_TIER3,
            score_band="50-69",
            band_min=TIER_3_MIN,
            band_max=69,
            target_size_min=0.0,
            target_size_max=0.5,
            leaps_eligible=False,
            adds_permitted=True,
        )

    # score < 50 → BELOW_GATE
    return TierResult(
        tier="BELOW_GATE",
        tier_label="BELOW GATE",
        action="NO NEW CAPITAL",
        action_tone=_TONE_BELOW_GATE,
        score_band="0-49",
        band_min=0,
        band_max=49,
        target_size_min=0.0,
        target_size_max=0.0,
        leaps_eligible=False,
        adds_permitted=False,
    )
