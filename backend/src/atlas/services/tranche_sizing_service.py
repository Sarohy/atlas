"""Framework 4 — Tranche Sizing service.

Maps three external signals to four cash-deployment tranches (T1–T4).
All logic lives in pure helpers (_compute_t1 through _compute_t4) so the
business rules are unit-testable without any I/O.

Tranche rules
-------------
T1  "10-15% of available cash"   when initial_catalyst == "yes"
T2  "20-25% of available cash"   when regime_rule       == "CAUTION"
T3  "30-40% of available cash"   when regime_rule       == "CLEAR"
T4  "Remaining cash to floor"    when iran_resolution   == "confirmed"

Any gate that is not met returns "Blocked".

``regime_rule`` should be passed from the UI's already-fetched Framework 2
value to keep Framework 4 in sync with the displayed regime — the same
pattern as the ``base_score`` parameter in Framework 3.
"""

from __future__ import annotations

from typing import Final

from atlas.schemas.tranche_sizing import TrancheSizingResponse

# ---------------------------------------------------------------------------
# Output constants
# ---------------------------------------------------------------------------

_BLOCKED: Final[str] = "Blocked"
_T1_VALUE: Final[str] = "10-15% of available cash"
_T2_VALUE: Final[str] = "20-25% of available cash"
_T3_VALUE: Final[str] = "30-40% of available cash"
_T4_VALUE: Final[str] = "Remaining cash to floor"

# ---------------------------------------------------------------------------
# Regime rule sentinels
# ---------------------------------------------------------------------------

_REGIME_CAUTION: Final[str] = "CAUTION"
_REGIME_CLEAR: Final[str] = "CLEAR"

# ---------------------------------------------------------------------------
# Pure gate helpers
# ---------------------------------------------------------------------------


def _compute_t1(initial_catalyst: str) -> str:
    """Return T1 value when the initial catalyst is confirmed.

    Pure function — no I/O, no side effects.
    """
    return _T1_VALUE if initial_catalyst.strip().lower() == "yes" else _BLOCKED


def _compute_t2(regime_rule: str) -> str:
    """Return T2 value when the Framework 2 regime is CAUTION.

    Pure function — no I/O, no side effects.
    """
    return _T2_VALUE if regime_rule.strip().upper() == _REGIME_CAUTION else _BLOCKED


def _compute_t3(regime_rule: str) -> str:
    """Return T3 value when the Framework 2 regime is CLEAR.

    Pure function — no I/O, no side effects.
    """
    return _T3_VALUE if regime_rule.strip().upper() == _REGIME_CLEAR else _BLOCKED


def _compute_t4(iran_resolution: str | None) -> str:
    """Return T4 value when the Iran Resolution is confirmed.

    Pure function — no I/O, no side effects.
    """
    if iran_resolution is None:
        return _BLOCKED
    return _T4_VALUE if iran_resolution.strip().lower() == "confirmed" else _BLOCKED


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_tranche_sizing(
    ticker: str,
    initial_catalyst: str,
    regime_rule: str = "NORMAL",
    iran_resolution: str | None = None,
) -> TrancheSizingResponse:
    """Compute the Framework 4 tranche-sizing result.

    Parameters
    ----------
    ticker:
        Portfolio ticker symbol (normalised to upper-case internally).
    initial_catalyst:
        ``"yes"`` or ``"no"`` — whether the entry catalyst has fired.
    regime_rule:
        The Framework 2 regime rule already held by the UI
        (``"CRISIS"`` | ``"CAUTION"`` | ``"CLEAR"`` | ``"NORMAL"``).
        Defaults to ``"NORMAL"`` (all gates blocked) when not supplied.
    iran_resolution:
        ``"confirmed"`` to unlock T4; anything else (including ``None``)
        keeps T4 blocked.
    """
    return TrancheSizingResponse(
        ticker=ticker.strip().upper(),
        t1=_compute_t1(initial_catalyst),
        t2=_compute_t2(regime_rule),
        t3=_compute_t3(regime_rule),
        t4=_compute_t4(iran_resolution),
    )
