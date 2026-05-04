"""Framework 3 — Score Action Map v7.3.5.

Maps a Framework 1 conviction score to a position-sizing action.
All band logic delegates to ``atlas.core.scoring.classify_tier`` — the single
source of truth for v7.3.5 tier boundaries.

Score bands (v7.3.5):
  >= 85       T1_ELITE    - Core position, LEAPS eligible, 5-10% NAV
  80-84       T1          - Core position, 2-4% NAV
  70-79       T2          - GTC adds permitted, 0.5-1.5% NAV
  50-69       T3          - Small speculative position, 0-0.5% NAV
  < 50        BELOW_GATE  - Exit rules active (see Framework 16)
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.core.scoring import classify_tier
from atlas.schemas.position_sizing import PositionSizingResponse

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

    Delegates to ``atlas.core.scoring.classify_tier`` — the single source of
    truth for v7.3.3 tier boundaries.

    Pure function — no I/O, no side effects.

    Parameters
    ----------
    final_score:
        Framework 1 conviction score (0-100).
    concentration_cap_active:
        When ``True`` and score falls in T1_ELITE, adds are blocked by the
        Framework 14 concentration cap.  The tier label is unchanged.
    """
    tier_data = classify_tier(final_score)
    tier = tier_data["tier"]

    if tier == "T1_ELITE":
        if concentration_cap_active:
            return ScoreAction(
                tier="T1_ELITE",
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
            tier="T1_ELITE",
            action="CORE — LEAPS ELIGIBLE",
            grey_zone=False,
            consensus_required=False,
            trigger_exit_rules=False,
            adds_permitted=True,
            leaps_eligible=True,
            display_message="Core position — LEAPS eligible.",
        )

    if tier == "T1":
        return ScoreAction(
            tier="T1",
            action="CORE POSITION",
            grey_zone=False,
            consensus_required=False,
            trigger_exit_rules=False,
            adds_permitted=True,
            leaps_eligible=False,
            display_message="Core position — GTC adds permitted.",
        )

    if tier == "T2":
        return ScoreAction(
            tier="T2",
            action="GTC ADDS PERMITTED",
            grey_zone=False,
            consensus_required=False,
            trigger_exit_rules=False,
            adds_permitted=True,
            leaps_eligible=False,
            display_message="GTC adds permitted.",
        )

    if tier == "T3":
        return ScoreAction(
            tier="T3",
            action="SMALL POSITION ONLY",
            grey_zone=False,
            consensus_required=False,
            trigger_exit_rules=False,
            adds_permitted=False,
            leaps_eligible=False,
            display_message="Small speculative position only — monitor for improvement.",
        )

    # BELOW_GATE (score < 50)
    return ScoreAction(
        tier="BELOW_GATE",
        action="BELOW GATE",
        grey_zone=False,
        consensus_required=False,
        trigger_exit_rules=True,
        adds_permitted=False,
        leaps_eligible=False,
        display_message="Below gate — exit rules active. See Framework 16.",
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

    Parameters
    ----------
    ticker:
        Ticker symbol (will be upper-cased).
    conviction_score:
        Framework 1 final score (0-100); clamped to [0, 100].
    concentration_cap_active:
        Passed from Framework 14; blocks T1 Elite adds when ``True``.
    """
    clamped = max(0, min(100, conviction_score))
    upper_ticker = ticker.upper()

    score_action = score_to_action(float(clamped), concentration_cap_active)

    return PositionSizingResponse(
        ticker=upper_ticker,
        conviction_score=clamped,
        tier=score_action.tier,
        action=score_action.action,
        grey_zone=False,
        consensus_required=False,
        trigger_exit_rules=score_action.trigger_exit_rules,
        adds_permitted=score_action.adds_permitted,
        leaps_eligible=score_action.leaps_eligible,
        display_message=score_action.display_message,
        consensus_confirmed=False,
    )
