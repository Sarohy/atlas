"""Entry Gate service — unified Section 16 + Framework 12 evaluator.

Fetches all external data ONCE and passes the same snapshot through both
Section 16 and Framework 12.  The frontend calls GET /api/v1/entry-gate/{ticker}
instead of making two separate requests.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.schemas.entry_gate import EntryGateResult
from atlas.services.framework12_service import evaluate_framework12_from_s16
from atlas.services.section16_service import evaluate_section16


async def evaluate_entry_gate(
    ticker: str,
    session: AsyncSession,
) -> EntryGateResult:
    """Run Section 16 then Framework 12 from the same S16 snapshot.

    Framework 12 receives the pre-computed Section16Result directly so it
    reads DTE from Rule 2 and does not make a redundant F7 HTTP call.
    """
    s16 = await evaluate_section16(ticker, session)

    dte: int | None = None
    if s16.rule2 is not None and isinstance(s16.rule2.days_to_earnings, int):
        dte = s16.rule2.days_to_earnings

    f12 = await evaluate_framework12_from_s16(ticker, s16, session)

    return EntryGateResult(
        ticker=ticker,
        track=s16.track,
        dte=dte,
        section16=s16,
        framework12=f12,
        override=s16.override,
    )


__all__ = ["evaluate_entry_gate"]
