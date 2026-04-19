"""Framework 5 — Cash Floor service.

Derives a cash-reserve requirement from the active Framework 2 (Regime
Modifier) rule and the ticker's current portfolio position value.

Cash floor rules (by Framework 2 regime):
  CRISIS        → 35 – 40 %   "Binary weekend risk, high beta protection"
  CAUTION        → 25 – 35 %   "Deploy T1 only"
  CLEAR         → 10 – 12 %   "Hedge portfolio serves as macro buffer"
  FULLY_DEPLOYED→ 10 %        "Never touch this floor"  (permanent minimum)

Pure helpers (_floor_params_from_rule, _floor_usd_amounts) are side-effect-free
and fully unit-testable without mocks or network calls.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.ticker import Ticker
from atlas.schemas.cash_floor import CashFloorResponse
from atlas.schemas.regime_modifier import RegimeModifierResponse
from atlas.services.regime_modifier_service import RegimeModifierService
from atlas.services.ticker_service import TickerService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Condition labels
# ---------------------------------------------------------------------------

_CONDITION_CRISIS: Final[str] = "CRISIS"
_CONDITION_CAUTION: Final[str] = "CAUTION"
_CONDITION_CLEAR: Final[str] = "CLEAR"
_CONDITION_FULLY_DEPLOYED: Final[str] = "FULLY_DEPLOYED"

# ---------------------------------------------------------------------------
# Floor percentage bounds (expressed as decimals — 0.35 = 35 %)
# ---------------------------------------------------------------------------

# CRISIS — Rule 1
_CRISIS_FLOOR_MIN: Final[float] = 0.35
_CRISIS_FLOOR_MAX: Final[float] = 0.40

# CAUTION — Rule 2
_CAUTION_FLOOR_MIN: Final[float] = 0.25
_CAUTION_FLOOR_MAX: Final[float] = 0.35

# CLEAR — Rule 3
_CLEAR_FLOOR_MIN: Final[float] = 0.10
_CLEAR_FLOOR_MAX: Final[float] = 0.12

# FULLY_DEPLOYED (Normal) — permanent, symmetrical floor, never touch
_NORMAL_FLOOR: Final[float] = 0.10

# ---------------------------------------------------------------------------
# Rationale strings
# ---------------------------------------------------------------------------

_RATIONALE_CRISIS: Final[str] = "Binary weekend risk, high beta protection"
_RATIONALE_CAUTION: Final[str] = "Deploy T1 only"
_RATIONALE_CLEAR: Final[str] = "Hedge portfolio serves as macro buffer"
_RATIONALE_NORMAL: Final[str] = "Never touch this floor"


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no side effects, fully unit-testable
# ---------------------------------------------------------------------------


def _floor_params_from_rule(
    rule: str,
) -> tuple[str, float, float, str]:
    """Map a Framework 2 regime rule string to cash-floor parameters.

    Parameters
    ----------
    rule:
        One of ``"CRISIS"``, ``"CAUTION"``, ``"CLEAR"``, ``"NORMAL"``.
        Any unrecognised value falls back to ``"FULLY_DEPLOYED"``.

    Returns
    -------
    tuple of (condition, floor_pct_min, floor_pct_max, rationale)

    Pure function — no I/O.
    """
    if rule == _CONDITION_CRISIS:
        return _CONDITION_CRISIS, _CRISIS_FLOOR_MIN, _CRISIS_FLOOR_MAX, _RATIONALE_CRISIS
    if rule == _CONDITION_CAUTION:
        return _CONDITION_CAUTION, _CAUTION_FLOOR_MIN, _CAUTION_FLOOR_MAX, _RATIONALE_CAUTION
    if rule == _CONDITION_CLEAR:
        return _CONDITION_CLEAR, _CLEAR_FLOOR_MIN, _CLEAR_FLOOR_MAX, _RATIONALE_CLEAR
    # NORMAL or any unknown value
    return _CONDITION_FULLY_DEPLOYED, _NORMAL_FLOOR, _NORMAL_FLOOR, _RATIONALE_NORMAL


def _floor_usd_amounts(
    position_value: Decimal | None,
    floor_pct_min: float,
    floor_pct_max: float,
) -> tuple[Decimal | None, Decimal | None]:
    """Compute USD cash-floor bounds from a portfolio position value.

    Parameters
    ----------
    position_value:
        Market value of the position in USD.  ``None`` when the ticker is
        not in the portfolio database.
    floor_pct_min / floor_pct_max:
        Cash floor fractions (e.g. 0.35 = 35 %).

    Returns
    -------
    (floor_usd_min, floor_usd_max)  — both ``None`` when position_value is None.

    Pure function — no I/O.
    """
    if position_value is None:
        return None, None
    floor_usd_min = (position_value * Decimal(str(floor_pct_min))).quantize(Decimal("0.01"))
    floor_usd_max = (position_value * Decimal(str(floor_pct_max))).quantize(Decimal("0.01"))
    return floor_usd_min, floor_usd_max


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class CashFloorService:
    """Computes the Framework 5 cash-floor guidance for a single ticker.

    Internally calls:
      1. :class:`~atlas.services.regime_modifier_service.RegimeModifierService`
         to determine the live Framework 2 regime rule.
      2. :class:`~atlas.services.ticker_service.TickerService` to retrieve the
         portfolio position value for the ticker.

    Parameters
    ----------
    polygon_api_key, alphavantage_api_key, transcript_api_key,
    benzinga_api_key, unusual_whales_api_key, sec_api_key:
        Forwarded to the internal :class:`RegimeModifierService`.
    session:
        SQLAlchemy async session used for portfolio DB lookups.
    """

    def __init__(
        self,
        polygon_api_key: str,
        alphavantage_api_key: str,
        transcript_api_key: str,
        benzinga_api_key: str,
        unusual_whales_api_key: str,
        sec_api_key: str,
        session: AsyncSession,
    ) -> None:
        self._regime_service = RegimeModifierService(
            polygon_api_key=polygon_api_key,
            alphavantage_api_key=alphavantage_api_key,
            transcript_api_key=transcript_api_key,
            benzinga_api_key=benzinga_api_key,
            unusual_whales_api_key=unusual_whales_api_key,
            sec_api_key=sec_api_key,
            session=session,
        )
        self._ticker_service = TickerService(session)

    async def compute_cash_floor(self, ticker: str) -> CashFloorResponse:
        """Return the Framework 5 cash-floor guidance for ``ticker``.

        Steps
        -----
        1. Calls Framework 2 (Regime Modifier) to determine the live regime rule
           (CRISIS / CAUTION / CLEAR / NORMAL).  ``active_war`` defaults to
           ``False``; the investor can override via the Framework 2 panel.
        2. Fetches the ticker's portfolio position value from the database.
        3. Maps the regime rule to condition, rationale, and floor percentages.
        4. Converts floor percentages to USD amounts when a position value is
           available.
        """
        # ── Step 1: determine live regime rule ────────────────────────────
        regime_result = await self._regime_service.compute_regime_modifier(
            ticker,
            active_war=False,
        )

        rule: str
        brent_price: float | None
        vix_value: float | None
        rule_triggered: int | None

        if isinstance(regime_result, RegimeModifierResponse):
            rule = regime_result.rule
            brent_price = regime_result.brent_price
            vix_value = regime_result.vix_value
            rule_triggered = regime_result.rule_triggered
        else:
            # Unexpected exception from regime service — fall back gracefully.
            logger.warning(
                "Regime modifier returned unexpected result; defaulting to NORMAL",
                extra={"error": repr(regime_result), "ticker": ticker},
            )
            rule = "NORMAL"
            brent_price = None
            vix_value = None
            rule_triggered = None

        # ── Step 2: fetch portfolio position value ─────────────────────────
        position_value: Decimal | None = None
        ticker_row: Ticker | None = await self._ticker_service.get_by_ticker(ticker)
        if ticker_row is not None and ticker_row.position_value is not None:
            position_value = ticker_row.position_value

        # ── Step 3: map regime → floor parameters ──────────────────────────
        condition, floor_pct_min, floor_pct_max, rationale = _floor_params_from_rule(rule)

        # ── Step 4: compute USD amounts ────────────────────────────────────
        floor_usd_min, floor_usd_max = _floor_usd_amounts(
            position_value, floor_pct_min, floor_pct_max
        )

        return CashFloorResponse(
            ticker=ticker,
            rule_triggered=rule_triggered,
            brent_price=brent_price,
            vix_value=vix_value,
            condition=condition,
            rationale=rationale,
            floor_pct_min=floor_pct_min,
            floor_pct_max=floor_pct_max,
            position_value_usd=float(position_value) if position_value is not None else None,
            floor_usd_min=float(floor_usd_min) if floor_usd_min is not None else None,
            floor_usd_max=float(floor_usd_max) if floor_usd_max is not None else None,
        )
