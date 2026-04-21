"""Framework 3 — Score Action Map v7.3.4.

Maps a Framework 1 conviction score to a position-sizing action.
All band logic lives in the pure helper ``score_to_action`` so it is
trivially unit-testable without any I/O.

Score bands (v7.3.4):
  >= 85       TIER_1         - Core position, LEAPS eligible
  78 - 84     TIER_2_GREY    - Grey zone, 3-model consensus required
  70 - 77     TIER_2         - GTC adds permitted
  55 - 69     TIER_3         - Small position only
  < 55        WATCHLIST      - Exit rules active (see Framework 16)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from atlas.schemas.position_sizing import PositionSizingResponse

# ---------------------------------------------------------------------------
# Score band thresholds (inclusive lower bounds)
# ---------------------------------------------------------------------------

_THRESHOLD_TIER_1: Final[int] = 85  # score must be >= this
_THRESHOLD_TIER_2_GREY_LOW: Final[int] = 78  # 78 - 84 inclusive
_THRESHOLD_TIER_2_LOW: Final[int] = 70  # 70 - 77 inclusive
_THRESHOLD_TIER_3_LOW: Final[int] = 55  # 55 - 69 inclusive
# < 55  ->  WATCHLIST

# ---------------------------------------------------------------------------
# Consensus store (in-memory; swap for Redis in production)
# Key pattern: f3_consensus:{TICKER}
# ---------------------------------------------------------------------------

_consensus_store: dict[str, bool] = {}


def _set_consensus(ticker: str, value: bool) -> None:
    """Test/admin helper — write a consensus value for ``ticker``."""
    _consensus_store[f"f3_consensus:{ticker.upper()}"] = value


def _get_consensus(ticker: str) -> bool:
    """Return stored consensus flag; defaults to False when absent."""
    return _consensus_store.get(f"f3_consensus:{ticker.upper()}", False)


# ---------------------------------------------------------------------------
# ScoreAction dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScoreAction:
    """Immutable result of ``score_to_action``.

    All fields are set by the pure mapping function; no I/O is performed.
    """

    tier: str
    action: str
    grey_zone: bool
    consensus_required: bool
    trigger_exit_rules: bool
    adds_permitted: bool
    leaps_eligible: bool
    display_message: str


# ---------------------------------------------------------------------------
# Pure mapping function
# ---------------------------------------------------------------------------


def score_to_action(
    final_score: float,
    concentration_cap_active: bool = False,
) -> ScoreAction:
    """Map a conviction score to a ``ScoreAction``.

    Pure function — no I/O, no side effects.

    Parameters
    ----------
    final_score:
        Framework 1 conviction score (0-100).
    concentration_cap_active:
        When ``True`` and score falls in TIER_1, adds are blocked by the
        Framework 14 concentration cap.  The tier label is unchanged.
    """
    if final_score >= _THRESHOLD_TIER_1:
        if concentration_cap_active:
            return ScoreAction(
                tier="TIER_1",
                action="CORE — LEAPS ELIGIBLE",
                grey_zone=False,
                consensus_required=False,
                trigger_exit_rules=False,
                adds_permitted=False,
                leaps_eligible=True,
                display_message=(
                    "Adds blocked by concentration cap — consensus gate not applicable."
                ),
            )
        return ScoreAction(
            tier="TIER_1",
            action="CORE — LEAPS ELIGIBLE",
            grey_zone=False,
            consensus_required=False,
            trigger_exit_rules=False,
            adds_permitted=True,
            leaps_eligible=True,
            display_message="Core position — LEAPS eligible.",
        )

    if final_score >= _THRESHOLD_TIER_2_GREY_LOW:
        return ScoreAction(
            tier="TIER_2_GREY",
            action="GREY ZONE",
            grey_zone=True,
            consensus_required=True,
            trigger_exit_rules=False,
            adds_permitted=False,  # overridden by consensus gate in compute_position_sizing
            leaps_eligible=False,
            display_message="Grey zone — 3-model consensus required before adding.",
        )

    if final_score >= _THRESHOLD_TIER_2_LOW:
        return ScoreAction(
            tier="TIER_2",
            action="GTC ADDS PERMITTED",
            grey_zone=False,
            consensus_required=False,
            trigger_exit_rules=False,
            adds_permitted=True,
            leaps_eligible=False,
            display_message="GTC adds permitted.",
        )

    if final_score >= _THRESHOLD_TIER_3_LOW:
        return ScoreAction(
            tier="TIER_3",
            action="SMALL POSITION ONLY",
            grey_zone=False,
            consensus_required=False,
            trigger_exit_rules=False,
            adds_permitted=False,
            leaps_eligible=False,
            display_message="Small position only — monitor for improvement.",
        )

    # < 55 → WATCHLIST
    return ScoreAction(
        tier="WATCHLIST",
        action="WATCHLIST",
        grey_zone=False,
        consensus_required=False,
        trigger_exit_rules=True,
        adds_permitted=False,
        leaps_eligible=False,
        display_message="Watchlist — exit rules active. See Framework 16.",
    )


# ---------------------------------------------------------------------------
# Public composite function
# ---------------------------------------------------------------------------


def compute_position_sizing(
    ticker: str,
    conviction_score: int,
    concentration_cap_active: bool = False,
) -> PositionSizingResponse:
    """Compute the Framework 3 position-sizing result.

    Applies the consensus gate for TIER_2_GREY positions on top of the pure
    ``score_to_action`` mapping.

    Parameters
    ----------
    ticker:
        Ticker symbol (will be upper-cased).
    conviction_score:
        Framework 1 final score (0-100); clamped to [0, 100].
    concentration_cap_active:
        Passed from Framework 14; blocks Tier 1 adds when ``True``.
    """
    clamped = max(0, min(100, conviction_score))
    upper_ticker = ticker.upper()

    score_action = score_to_action(float(clamped), concentration_cap_active)

    # Apply consensus gate: grey zone adds are permitted only when confirmed.
    consensus_confirmed = _get_consensus(upper_ticker) if score_action.grey_zone else False
    adds_permitted = score_action.adds_permitted
    display_message = score_action.display_message

    if score_action.grey_zone and consensus_confirmed:
        adds_permitted = True
        display_message = "Grey zone cleared by consensus — adds permitted."

    return PositionSizingResponse(
        ticker=upper_ticker,
        conviction_score=clamped,
        tier=score_action.tier,
        action=score_action.action,
        grey_zone=score_action.grey_zone,
        consensus_required=score_action.consensus_required,
        trigger_exit_rules=score_action.trigger_exit_rules,
        adds_permitted=adds_permitted,
        leaps_eligible=score_action.leaps_eligible,
        display_message=display_message,
        consensus_confirmed=consensus_confirmed,
    )
