"""API route for Framework 4 — Tranche Sizing.

GET /api/v1/tranche-sizing/{ticker}

Maps three external signals to four cash-deployment tranches (T1–T4).

Required query params
---------------------
initial_catalyst : "yes" | "no"
    Whether the entry catalyst has fired.

Optional query params
---------------------
regime_rule : str  (default: "NORMAL")
    The Framework 2 rule already held by the UI — pass this to keep
    Framework 4 in sync with the displayed regime without a second
    independent fetch.  Valid values: "CRISIS" | "CAUTION" | "CLEAR" | "NORMAL".

iran_resolution : str | None  (default: None)
    Pass "confirmed" to unlock T4.

Tranche rules
-------------
T1  "10-15% of available cash"   when initial_catalyst == yes
T2  "20-25% of available cash"   when regime_rule == CAUTION
T3  "30-40% of available cash"   when regime_rule == CLEAR
T4  "Remaining cash to floor"    when iran_resolution == confirmed
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from atlas.schemas.tranche_sizing import TrancheSizingResponse
from atlas.services.tranche_sizing_service import compute_tranche_sizing

router = APIRouter(prefix="/tranche-sizing", tags=["tranche-sizing"])

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

_VALID_CATALYST_VALUES = frozenset({"yes", "no"})


@router.get("/{ticker}", response_model=TrancheSizingResponse)
async def get_tranche_sizing(
    ticker: str,
    initial_catalyst: str,
    regime_rule: str | None = None,
    iran_resolution: str | None = None,
) -> TrancheSizingResponse:
    """Return a Framework 4 tranche-sizing recommendation for ``ticker``.

    Pass ``?regime_rule=<RULE>`` with the value already displayed in the
    Framework 2 panel to avoid a second independent computation and keep
    Framework 4 in sync with the UI.

    ``initial_catalyst`` is required and must be ``"yes"`` or ``"no"``.

    Tranche rules:

    +----+------------------------------+-------------------------------+
    | T1 | initial_catalyst == yes      | 10-15% of available cash      |
    | T2 | regime_rule == CAUTION       | 20-25% of available cash      |
    | T3 | regime_rule == CLEAR         | 30-40% of available cash      |
    | T4 | iran_resolution == confirmed | Remaining cash to floor       |
    +----+------------------------------+-------------------------------+

    Returns 422 when ``initial_catalyst`` is not ``"yes"`` or ``"no"``.
    """
    normalised_ticker = ticker.strip().upper()
    if not normalised_ticker:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    if initial_catalyst.strip().lower() not in _VALID_CATALYST_VALUES:
        raise HTTPException(
            status_code=422,
            detail="initial_catalyst must be 'yes' or 'no'.",
        )

    return compute_tranche_sizing(
        ticker=normalised_ticker,
        initial_catalyst=initial_catalyst,
        regime_rule=regime_rule if regime_rule is not None else "NORMAL",
        iran_resolution=iran_resolution,
    )
