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
from atlas.services.framework11_service import get_f11_simple
from atlas.services.tranche_sizing_service import (
    compute_tranche_sizing,
    fire_t2_tranche,
    fire_t3_tranche,
    get_position_weight,
)

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
    brent_consecutive_below_95_count: int = 0,
    geopolitical_state: str | None = None,
    brent_price: float | None = None,
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

    Pass ``brent_consecutive_below_95_count`` and ``geopolitical_state`` to
    auto-detect AND gate signals 2 and 5 from live data.

    Pass ``brent_price`` to drive the T2 Brent gate (T2 unlocks when < $110).

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

    # Framework 11 — Cash Floor Gate.
    # Check F11 cache before computing tranches.  If the floor is violated or
    # data is unavailable, all tranches are blocked.  F11 is the single source
    # of truth for floor_violated; we never recalculate the floor here.
    _BLOCKED_F11 = "Blocked"
    f11 = get_f11_simple()
    if f11 is not None and f11.all_buys_blocked:
        if f11.floor_violated is True:
            cash_pct_str = f"{f11.cash_pct:.1f}%" if f11.cash_pct is not None else "unknown%"
            floor_pct_str = f"{f11.floor_pct:.0f}%" if f11.floor_pct is not None else "unknown%"
            shortfall_str = (
                f"${f11.shortfall_usd:,.0f}" if f11.shortfall_usd is not None else "unknown"
            )
            f11_msg = (
                f"Blocked \u2014 Framework 11 cash floor violated. "
                f"Cash {cash_pct_str} below {floor_pct_str} floor. "
                f"Shortfall: {shortfall_str}"
            )
        else:
            f11_msg = (
                "Unknown \u2014 Framework 11 cash floor status unavailable. "
                "No deployment until data restored."
            )
        return TrancheSizingResponse(
            ticker=normalised_ticker,
            cap_active=False,
            tranche_display=False,
            position_weight=effective_weight,
            message=f11_msg,
            and_gate_active=False,
            and_gate_passed=False,
            signals_confirmed=0,
            signals_detail=[],
            t1=_BLOCKED_F11,
            t2=_BLOCKED_F11,
            t3=_BLOCKED_F11,
            t4=_BLOCKED_F11,
            t1_fired=False,
            t2_fired=False,
            t2_pending=False,
            t3_fired=False,
            t3_pending=False,
        )

    return compute_tranche_sizing(
        ticker=normalised_ticker,
        initial_catalyst=initial_catalyst,
        regime_rule=regime_rule or "NORMAL",
        iran_resolution=iran_resolution,
        position_weight=effective_weight,
        signals_count_override=signals_count_override,
        t1_fired_override=t1_fired_override,
        brent_consecutive_below_95_count=brent_consecutive_below_95_count,
        geopolitical_state=geopolitical_state or "NONE",
        brent_price=brent_price,
    )


@router.post("/{ticker}/confirm-t2", status_code=204)
async def confirm_t2(ticker: str) -> None:
    """Confirm the operator has accepted the auto-triggered T2 deployment order.

    Called when the operator clicks [Confirm] in the Framework 17 T2 modal.
    Persists T2 fired state for the ticker so subsequent GET requests return
    ``t2_fired=true`` and ``t2_pending=false``.

    Returns 204 No Content on success.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")
    fire_t2_tranche(normalised)


@router.post("/{ticker}/confirm-t3", status_code=204)
async def confirm_t3(ticker: str) -> None:
    """Confirm the operator has accepted the auto-triggered T3 deployment order.

    Called when the operator clicks [Confirm] in the Framework 17 T3 modal.
    Persists T3 fired state for the ticker so subsequent GET requests return
    ``t3_fired=true`` and ``t3_pending=false``.

    Returns 204 No Content on success.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")
    fire_t3_tranche(normalised)
