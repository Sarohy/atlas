"""Pydantic schema for the unified Entry Gate response.

GET /api/v1/entry-gate/{ticker} returns this combined shape so the frontend
can make ONE request instead of calling /section16 and /framework12 separately.
Both evaluations share the same data snapshot — no race conditions.
"""

from __future__ import annotations

from pydantic import BaseModel

from atlas.schemas.framework12 import Framework12Result
from atlas.schemas.section16 import OverrideResult, Section16Result, TrackType


class EntryGateResult(BaseModel):
    """Combined Section 16 + Framework 12 result for a single ticker."""

    ticker: str
    track: TrackType

    # Days to earnings, extracted from Section 16 Rule 2 so both evaluations
    # use exactly the same value (no separate F7 re-fetch in Framework 12).
    dte: int | None

    section16: Section16Result
    framework12: Framework12Result

    # Convenience copy of the override block — mirrors section16.override but
    # surfaced at the top level so the frontend doesn't need to drill in.
    override: OverrideResult | None = None
