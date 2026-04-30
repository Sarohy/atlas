"""API routes for Framework 27 — Supply Chain Contagion Map.

GET  /api/v1/framework27/contagion              → Framework27Result (5-min cache)
GET  /api/v1/framework27/contagion/{ticker}     → single ticker contagion rules
POST /api/v1/framework27/contagion/manual-flag  → operator manual disruption confirm

Architecture note:
  /contagion/manual-flag is registered before /contagion/{ticker} so FastAPI
  does not interpret "manual-flag" as a ticker symbol.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Final

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.db.session import get_db_session
from atlas.models.decision_trace import DecisionTrace
from atlas.models.manual_contagion_flag import ManualContagionFlag
from atlas.schemas.framework27 import (
    ContagionRuleResult,
    Framework27Result,
    ManualFlagRequest,
)
from atlas.services.framework17_service import evaluate_framework17
from atlas.services.framework27_service import (
    cache_invalidate,
    evaluate_framework27,
)

router = APIRouter(prefix="/framework27", tags=["framework27"])

# Minimum override reason length.
_MIN_OVERRIDE_REASON_LEN: Final[int] = 50

# Allowed trigger types for manual flags.
_ALLOWED_MANUAL_TRIGGER_TYPES: Final[frozenset[str]] = frozenset(
    {
        "ASIA_FREIGHT_DISRUPTION_PCT",
        "METALS_DISRUPTION",
        "INDIUM_SUPPLY_DISRUPTION",
    }
)


# ---------------------------------------------------------------------------
# Read routes
# ---------------------------------------------------------------------------


@router.get("/contagion/manual-flag", response_model=Framework27Result, deprecated=True)
async def _guard() -> None:
    """Placeholder to ensure FastAPI doesn't swallow POST /contagion/manual-flag.

    This GET is unused but prevents route ordering issues.
    """
    raise HTTPException(status_code=405, detail="Use POST /contagion/manual-flag.")


@router.get("/contagion", response_model=Framework27Result)
async def get_f27_contagion(
    session: AsyncSession = Depends(get_db_session),
) -> Framework27Result:
    """Full Framework 27 contagion map evaluation (5-minute cache).

    Reads F17 state from the F17 service (never re-reads geopolitical_flag
    directly). Evaluates all active contagion rules from DB.
    """
    from atlas.services.framework27_service import _cache_get

    cached = _cache_get()
    if cached is not None:
        return Framework27Result(**{**cached.model_dump(), "cache_hit": True})

    f17_result = await evaluate_framework17(session)
    return await evaluate_framework27(f17_result, session)


@router.get("/contagion/{ticker}", response_model=list[ContagionRuleResult])
async def get_f27_ticker_contagion(
    ticker: str,
    session: AsyncSession = Depends(get_db_session),
) -> list[ContagionRuleResult]:
    """Return contagion rule results for a single ticker.

    Evaluates the full contagion map and filters to the requested ticker.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        raise HTTPException(status_code=422, detail="Ticker symbol must not be empty.")

    f17_result = await evaluate_framework17(session)
    f27_result = await evaluate_framework27(f17_result, session)

    ticker_rules = [r for r in f27_result.all_rules if r.ticker == normalised]
    return ticker_rules


# ---------------------------------------------------------------------------
# Write routes
# ---------------------------------------------------------------------------


@router.post("/contagion/manual-flag", response_model=Framework27Result, status_code=201)
async def post_f27_manual_flag(
    body: ManualFlagRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Framework27Result:
    """Operator confirms a supply chain disruption event.

    Validates trigger_type is one of the three operator-confirmed types.
    Logs to decision_trace and invalidates F27 cache.
    """
    if body.trigger_type not in _ALLOWED_MANUAL_TRIGGER_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid trigger_type '{body.trigger_type}'. "
                f"Allowed: {sorted(_ALLOWED_MANUAL_TRIGGER_TYPES)}."
            ),
        )

    if len(body.override_reason.strip()) < _MIN_OVERRIDE_REASON_LEN:
        raise HTTPException(
            status_code=422,
            detail=(
                f"override_reason must be at least {_MIN_OVERRIDE_REASON_LEN} characters."
            ),
        )

    # Write manual flag row.
    new_flag = ManualContagionFlag(
        trigger_type=body.trigger_type,
        flagged_by=body.flagged_by,
        flagged_at=datetime.now(timezone.utc),
        notes=body.notes,
        session_date=date.today(),
        active=True,
    )
    session.add(new_flag)

    # Log decision trace (append-only).
    trace = DecisionTrace(
        timestamp_utc=datetime.now(timezone.utc),
        trigger="FRAMEWORK_27",
        signal_type="MANUAL_CONTAGION_FLAG",
        ticker=None,
        human_override=True,
        override_reason=body.override_reason.strip(),
        resolution=(
            f"Operator {body.flagged_by!r} confirmed {body.trigger_type} disruption."
        ),
        visible_in_briefing=True,
    )
    session.add(trace)

    await session.flush()

    # Invalidate F27 cache so next read reflects the new flag.
    cache_invalidate()

    # Return fresh evaluation.
    f17_result = await evaluate_framework17(session)
    return await evaluate_framework27(f17_result, session)
