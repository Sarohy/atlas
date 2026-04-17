"""Framework 3 — Position Sizing service.

Maps a Framework 1 conviction score to a human-readable position action and
instruction.  All logic lives in the pure helper ``_map_position_action`` so
it is trivially unit-testable without any I/O.

Score bands (Factor_Mapping_Guide §Framework3):
  > 90        MAXIMUM POSITION      — Add on every dip
  80 – 90     HOLD FULL             — Eligible for adds
  70 – 79     HOLD                  — No new adds
  60 – 69     REDUCE 25-50%         — Reduce 25-50%
  55 – 59     REDUCE AGGRESSIVELY   — Reduce aggressively
  < 55        EXIT                  — Exit immediately
"""

from __future__ import annotations

from typing import Final

from atlas.schemas.position_sizing import PositionSizingResponse

# ---------------------------------------------------------------------------
# Score band thresholds (inclusive lower bound unless noted)
# ---------------------------------------------------------------------------

_THRESHOLD_MAXIMUM_POSITION: Final[int] = 90  # score must be > this
_THRESHOLD_HOLD_FULL: Final[int] = 80          # score must be >= this
_THRESHOLD_HOLD: Final[int] = 70               # score must be >= this
_THRESHOLD_REDUCE: Final[int] = 60             # score must be >= this
_THRESHOLD_REDUCE_AGGRESSIVELY: Final[int] = 55  # score must be >= this
# < 55  →  EXIT


def _map_position_action(score: int) -> tuple[str, str]:
    """Map a conviction score to (action, instruction).

    Pure function — no I/O, no side effects.

    Returns
    -------
    tuple[str, str]
        ``action``      — short label for the position action.
        ``instruction`` — human-readable guidance sentence.
    """
    if score > _THRESHOLD_MAXIMUM_POSITION:
        return "MAXIMUM POSITION", "Add on every dip."
    if score >= _THRESHOLD_HOLD_FULL:
        return "HOLD FULL", "Hold full position — eligible for adds."
    if score >= _THRESHOLD_HOLD:
        return "HOLD", "Hold position — no new adds."
    if score >= _THRESHOLD_REDUCE:
        return "REDUCE 25-50%", "Reduce position by 25-50%."
    if score >= _THRESHOLD_REDUCE_AGGRESSIVELY:
        return "REDUCE AGGRESSIVELY", "Reduce aggressively."
    return "EXIT", "Exit immediately."


def compute_position_sizing(ticker: str, conviction_score: int) -> PositionSizingResponse:
    """Compute the Framework 3 position-sizing result.

    Pure function — all data is supplied by the caller; no network calls.

    Parameters
    ----------
    ticker:
        Ticker symbol (will be upper-cased).
    conviction_score:
        Framework 1 final score (0-100).
    """
    action, instruction = _map_position_action(conviction_score)
    return PositionSizingResponse(
        ticker=ticker.upper(),
        conviction_score=conviction_score,
        action=action,
        instruction=instruction,
    )
