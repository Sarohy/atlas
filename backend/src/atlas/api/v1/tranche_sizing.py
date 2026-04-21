"""API route for Framework 4 - Tranche Sizing (v7.3.4).

GET /api/v1/tranche-sizing/{ticker}

Maps three external signals to four cash-deployment tranches (T1-T4).

Required query params
---------------------
initial_catalyst : "yes" | "no"
    Whether the entry catalyst has fired.

Optional query params
---------------------
regime_rule : str  (default: "NORMAL")
    The Framework 2 rule already held by the UI - pass this to keep
    Framework 4 in sync with the displayed regime without a second
    independent fetch.  Valid values: "CRISIS" | "CAUTION" | "CLEAR" | "NORMAL".

iran_resolution : str | None  (default: None)
    Pass "confirmed" to unlock T4.

position_weight_override : float | None  (default: None)
    Override the position weight used for concentration cap evaluation.
    When None, reads from the Framework 14 in-memory stub (known positions).
    Useful for testing cap boundary cases (e.g. exactly 8.0% or 7.9%).

signals_count_override : int | None  (default: None)
    Override the number of AND gate signals treated as confirmed.
    When None, reads from the Framework 29 in-memory stub.
    Useful for testing AND gate scenarios (e.g. 2/5 or 3/5).

Tranche rules (v7.3.4)
-----------------------
T1  "10-15% of available cash"   when initial_catalyst == yes
T2  "20-25% of available cash"   when regime_rule == CAUTION
T3  "30-40% of available cash"   when regime_rule == CLEAR AND and_gate passes
T4  "Remaining cash to floor"    when iran_resolution == confirmed
All None when concentration cap is active (position >= 8% NAV).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.schemas.tranche_sizing import TrancheSizingResponse
from atlas.services.tranche_sizing_service import compute_tranche_sizing, get_position_weight

router = APIRouter(prefix="/tranche-sizing", tags=["tranche-sizing"])

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

_VALID_CATALYST_VALUES = frozenset({"yes", "no"})


@router.get("/{ticker}", response_model=TrancheSizingResponse)
async def get_tranche_sizing(
    ticker: str,
    initial_catalyst: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    regime_rule: str | None = None,
    iran_resolution: str | None = None,
    position_weight_override: float | None = None,
    signals_count_override: int | None = None,
    t1_fired_override: bool | None = None,
) -> TrancheSizingResponse:
    """Return a Framework 4 tranche-sizing recommendation for ``ticker``.

    Pass ``?regime_rule=<RULE>`` with the value already displayed in the
    Framework 2 panel to avoid a second independent computation and keep
    Framework 4 in sync with the UI.

    ``initial_catalyst`` is required and must be ``"yes"`` or ``"no"``.

    Pass ``position_weight_override`` to test concentration cap behaviour
    at specific weight thresholds (e.g. 0.08 for exactly 8% NAV). When
    omitted, the position weight is read live from the portfolio database.

    Pass ``signals_count_override`` to test AND gate scenarios (e.g. 3 to
    simulate 3/5 signals confirmed).

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

    if position_weight_override is not None:
        effective_weight = float(position_weight_override)
    else:
        effective_weight = await get_position_weight(normalised_ticker, session)

    return compute_tranche_sizing(
        ticker=normalised_ticker,
        initial_catalyst=initial_catalyst,
        regime_rule=regime_rule or "NORMAL",
        iran_resolution=iran_resolution,
        position_weight=effective_weight,
        signals_count_override=signals_count_override,
        t1_fired_override=t1_fired_override,
    )
