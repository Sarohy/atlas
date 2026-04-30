"""Framework 5 — Cash Floor service.

Derives a cash-reserve requirement from the active Framework 2 (Regime
Modifier) rule and the portfolio's current NAV and cash balance.

Cash floor rules (ATLAS v7.3.4 — Section 14.1):
  CRISIS HALT   → 30 %   ("30%+" — binary weekend risk, high beta protection)
  CAUTION       → 20 %   (flat)
  SOFT CAUTION  → 15 %   (flat)
  CLEAR         → 8 %    settled / 10 % first 2 weeks after transition

Regime names match those returned by RegimeModifierService._rule_name():
  "CRISIS HALT", "CAUTION", "SOFT CAUTION", "CLEAR"

Pure helpers (_floor_params_from_rule, _floor_usd_amounts, _get_floor_pct,
_evaluate_floor_status) are side-effect-free and fully unit-testable without
mocks or network calls.
"""

from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.portfolio_config import PORTFOLIO_CONFIG_ROW_ID, PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.schemas.cash_floor import CashFloorResponse, FloorStatus, Framework5Response
from atlas.schemas.regime_modifier import RegimeModifierResponse
from atlas.services.framework13_service import calculate_portfolio_beta
from atlas.services.regime_modifier_service import RegimeModifierService
from atlas.services.ticker_service import TickerService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dummy ticker used when calling Framework 2 for portfolio-level regime only.
# The regime is market-wide and does not depend on the ticker value.
# ---------------------------------------------------------------------------

_PORTFOLIO_REGIME_TICKER: Final[str] = "PORTFOLIO"

# ---------------------------------------------------------------------------
# Floor percentage constants — Section 14.1
# ---------------------------------------------------------------------------

# CRISIS HALT — Rule 1
_CRISIS_HALT_FLOOR: Final[float] = 0.30

# CAUTION — Rule 2
_CAUTION_FLOOR: Final[float] = 0.20

# SOFT CAUTION — Rule 3
_SOFT_CAUTION_FLOOR: Final[float] = 0.15

# CLEAR — Rule 4
_CLEAR_SETTLED_FLOOR: Final[float] = 0.08  # settled after 2 weeks
_CLEAR_TRANSITION_FLOOR: Final[float] = 0.10  # first 2 weeks after entering CLEAR

# Number of days before CLEAR floor drops from transition to settled value.
_CLEAR_TRANSITION_DAYS: Final[int] = 14

# FULLY_DEPLOYED / unknown — permanent minimum, never touch
_NORMAL_FLOOR: Final[float] = 0.10

# Low-buffer threshold: buffer as fraction of NAV below which we warn.
# 1 % of NAV is considered dangerously thin.
_LOW_BUFFER_THRESHOLD: Final[float] = 0.01

# ---------------------------------------------------------------------------
# Condition labels
# ---------------------------------------------------------------------------

_CONDITION_CRISIS_HALT: Final[str] = "CRISIS HALT"
_CONDITION_CAUTION: Final[str] = "CAUTION"
_CONDITION_SOFT_CAUTION: Final[str] = "SOFT CAUTION"
_CONDITION_CLEAR: Final[str] = "CLEAR"
_CONDITION_FULLY_DEPLOYED: Final[str] = "FULLY_DEPLOYED"

# ---------------------------------------------------------------------------
# Rationale strings
# ---------------------------------------------------------------------------

_RATIONALE_CRISIS_HALT: Final[str] = (
    "CRISIS HALT — Binary weekend risk, high beta protection. 30%+ floor enforced."
)
_RATIONALE_CAUTION: Final[str] = "CAUTION — Deploy T1 only. 20% minimum floor."
_RATIONALE_SOFT_CAUTION: Final[str] = "SOFT CAUTION — Selective deployment permitted. 15% floor."
_RATIONALE_CLEAR_TRANSITION: Final[str] = (
    "CLEAR (transition) — 10% floor. Drops to 8% after 2-week settlement period."
)
_RATIONALE_CLEAR_SETTLED: Final[str] = "CLEAR — 8% floor. Hedge portfolio serves as macro buffer."
_RATIONALE_NORMAL: Final[str] = "FULLY DEPLOYED — Never touch this 10% floor."


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no side effects, fully unit-testable
# ---------------------------------------------------------------------------


def _floor_params_from_rule(
    rule: str,
) -> tuple[str, float, float, str]:
    """Map a Framework 2 regime string to legacy cash-floor parameters.

    Used by the legacy ``GET /cash-floor/{ticker}`` endpoint only.
    For CLEAR, returns the conservative transition floor (10%) as a safe default.

    Parameters
    ----------
    rule:
        Regime name returned by RegimeModifierService, e.g.
        ``"CRISIS HALT"``, ``"CAUTION"``, ``"SOFT CAUTION"``, ``"CLEAR"``, ``"NORMAL"``.

    Returns
    -------
    tuple of (condition, floor_pct_min, floor_pct_max, rationale)

    Pure function — no I/O.
    """
    if rule == _CONDITION_CRISIS_HALT:
        return (
            _CONDITION_CRISIS_HALT,
            _CRISIS_HALT_FLOOR,
            _CRISIS_HALT_FLOOR,
            _RATIONALE_CRISIS_HALT,
        )
    if rule == _CONDITION_CAUTION:
        return _CONDITION_CAUTION, _CAUTION_FLOOR, _CAUTION_FLOOR, _RATIONALE_CAUTION
    if rule == _CONDITION_SOFT_CAUTION:
        return (
            _CONDITION_SOFT_CAUTION,
            _SOFT_CAUTION_FLOOR,
            _SOFT_CAUTION_FLOOR,
            _RATIONALE_SOFT_CAUTION,
        )
    if rule == _CONDITION_CLEAR:
        # Conservative default: use transition floor (10%).
        # The portfolio-level endpoint uses _get_floor_pct() for accurate transitions.
        return (
            _CONDITION_CLEAR,
            _CLEAR_TRANSITION_FLOOR,
            _CLEAR_TRANSITION_FLOOR,
            _RATIONALE_CLEAR_TRANSITION,
        )
    # NORMAL or any unrecognised value — permanent 10% minimum
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
        Market value in USD.  ``None`` when the ticker is not in the portfolio.
    floor_pct_min / floor_pct_max:
        Cash floor fractions (e.g. 0.20 = 20 %).

    Returns
    -------
    (floor_usd_min, floor_usd_max) — both ``None`` when position_value is None.

    Pure function — no I/O.
    """
    if position_value is None:
        return None, None
    floor_usd_min = (position_value * Decimal(str(floor_pct_min))).quantize(Decimal("0.01"))
    floor_usd_max = (position_value * Decimal(str(floor_pct_max))).quantize(Decimal("0.01"))
    return floor_usd_min, floor_usd_max


def _get_floor_pct(
    regime: str,
    clear_transition_date: datetime.date | None,
    today: datetime.date | None = None,
) -> tuple[float, bool, int | None]:
    """Return the active floor percentage, transition flag, and remaining days.

    Parameters
    ----------
    regime:
        Active regime string from Framework 2, e.g. ``"CLEAR"``, ``"CAUTION"``.
    clear_transition_date:
        The date stored in PortfolioConfig when CLEAR was first detected.
        ``None`` if the column has not been set yet.
    today:
        Override today's date for deterministic testing.  Defaults to
        ``datetime.date.today()`` when ``None``.

    Returns
    -------
    (floor_pct, transition_active, days_until_settled)

    Pure function — no side effects.
    """
    effective_today = today if today is not None else datetime.date.today()

    if regime == _CONDITION_CRISIS_HALT:
        return _CRISIS_HALT_FLOOR, False, None
    if regime == _CONDITION_CAUTION:
        return _CAUTION_FLOOR, False, None
    if regime == _CONDITION_SOFT_CAUTION:
        return _SOFT_CAUTION_FLOOR, False, None
    if regime == _CONDITION_CLEAR:
        if clear_transition_date is None:
            # No transition date recorded yet — assume transition just started.
            return _CLEAR_TRANSITION_FLOOR, True, _CLEAR_TRANSITION_DAYS
        days_elapsed = (effective_today - clear_transition_date).days
        if days_elapsed < _CLEAR_TRANSITION_DAYS:
            days_remaining = _CLEAR_TRANSITION_DAYS - days_elapsed
            return _CLEAR_TRANSITION_FLOOR, True, days_remaining
        return _CLEAR_SETTLED_FLOOR, False, None
    # Unknown regime — apply conservative CAUTION floor
    return _CAUTION_FLOOR, False, None


def _evaluate_floor_status(
    total_cash: float,
    floor_amount: float,
    buffer_pct: float,
) -> tuple[FloorStatus, str, str | None, bool]:
    """Classify cash position relative to the floor.

    Parameters
    ----------
    total_cash:
        Cash balance in USD.
    floor_amount:
        Minimum cash requirement in USD (floor_pct * total_nav).
    buffer_pct:
        Buffer above floor as a fraction of NAV (0 when below floor).

    Returns
    -------
    (FloorStatus, warning_level, warning_message, deployment_permitted)

    Pure function — no side effects.
    """
    if total_cash == 0.0:
        return (
            FloorStatus.CRITICAL_ZERO,
            "CRITICAL",
            (
                "CRITICAL: Zero cash held. Portfolio fully invested. "
                "No buffer against drawdown. Immediate action required."
            ),
            False,
        )
    if total_cash < floor_amount:
        shortfall = floor_amount - total_cash
        return (
            FloorStatus.BELOW_FLOOR,
            "CRITICAL",
            (
                f"CRITICAL — BELOW FLOOR. Shortfall: ${shortfall:,.2f}. "
                "No deployment permitted. Replenishment required."
            ),
            False,
        )
    if total_cash == floor_amount:
        return (
            FloorStatus.AT_FLOOR,
            "AMBER",
            "At floor — no buffer available. Any deployment would breach the floor.",
            False,
        )
    if buffer_pct < _LOW_BUFFER_THRESHOLD:
        return (
            FloorStatus.LOW_BUFFER,
            "AMBER",
            (
                f"Low buffer — only {buffer_pct * 100:.2f}% above floor. "
                "Limited deployment capacity."
            ),
            True,
        )
    return FloorStatus.HEALTHY, "NONE", None, True


def _get_floor_pct_display(
    regime: str,
    floor_pct: float,
    transition_active: bool,
    days_until_settled: int | None,
) -> str:
    """Return a human-readable floor percentage label.

    Pure function — no side effects.
    """
    if regime == _CONDITION_CRISIS_HALT:
        return "30%+"
    if transition_active:
        days_str = str(days_until_settled) if days_until_settled is not None else "14"
        return f"10% (transition — drops to 8% in {days_str} days)"
    return f"{int(floor_pct * 100)}%"


def _get_rationale(
    regime: str,
    transition_active: bool,
    days_until_settled: int | None,
    is_below_floor: bool,
    floor_amount: float,
) -> str:
    """Return the human-readable rationale string for this floor state.

    When below floor, the rationale is overridden with a no-deployment message.

    Pure function — no side effects.
    """
    if is_below_floor:
        floor_str = f"${floor_amount:,.0f}"
        return (
            f"Below floor — no deployment permitted until cash replenished "
            f"above minimum floor of {floor_str}."
        )
    if regime == _CONDITION_CRISIS_HALT:
        return _RATIONALE_CRISIS_HALT
    if regime == _CONDITION_CAUTION:
        return _RATIONALE_CAUTION
    if regime == _CONDITION_SOFT_CAUTION:
        return _RATIONALE_SOFT_CAUTION
    if regime == _CONDITION_CLEAR:
        if transition_active:
            days_str = f"{days_until_settled} days" if days_until_settled else "2 weeks"
            return f"CLEAR (transition) — 10% floor. Drops to 8% in {days_str}."
        return _RATIONALE_CLEAR_SETTLED
    return _RATIONALE_NORMAL


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class CashFloorService:
    """Computes Framework 5 cash-floor guidance.

    Provides two public methods:
      ``compute_portfolio_floor()`` — portfolio-level status (new endpoint).
      ``compute_cash_floor(ticker)`` — legacy per-ticker status.

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
        self._session = session

    # ── Portfolio-level method (new) ──────────────────────────────────────

    async def compute_portfolio_floor(self) -> Framework5Response:
        """Return the Framework 5 portfolio-level cash floor status.

        Steps
        -----
        1. Read regime from Framework 2 (never recalculates Brent/VIX directly).
        2. Load total NAV and cash balance from the portfolio database.
        3. Manage CLEAR transition date in PortfolioConfig (side-effect on CLEAR entry/exit).
        4. Calculate floor percentage via ``_get_floor_pct()``.
        5. Compute floor amounts, buffer, and shortfall.
        6. Evaluate floor status via ``_evaluate_floor_status()``.
        7. Compute effective portfolio beta via Framework 13.
        8. Build and return ``Framework5Response``.
        """
        # ── Step 1: read regime from Framework 2 ──────────────────────────
        regime_result = await self._regime_service.compute_regime_modifier(
            _PORTFOLIO_REGIME_TICKER,
            geopolitical_state="NONE",
        )

        regime: str
        brent_price: float | None
        vix_value: float | None

        if isinstance(regime_result, RegimeModifierResponse):
            regime = regime_result.rule
            brent_price = regime_result.brent_price
            vix_value = regime_result.vix_value
        else:
            logger.warning(
                "Regime modifier returned unexpected result; defaulting to CAUTION",
                extra={"error": repr(regime_result)},
            )
            regime = _CONDITION_CAUTION
            brent_price = None
            vix_value = None

        # ── Step 2: load portfolio NAV and config ──────────────────────────
        config_result = await self._session.execute(
            select(PortfolioConfig).where(PortfolioConfig.id == PORTFOLIO_CONFIG_ROW_ID)
        )
        config: PortfolioConfig | None = config_result.scalar_one_or_none()

        cash_balance: Decimal = config.cash_balance if config is not None else Decimal("0")
        clear_transition_date: datetime.date | None = (
            config.clear_transition_date if config is not None else None
        )

        tickers: list[Ticker] = await self._ticker_service.list_tickers()
        invested_value: Decimal = sum(
            (t.position_value or Decimal("0")) for t in tickers
        ) or Decimal("0")
        total_nav: Decimal = invested_value + cash_balance

        total_nav_f: float = float(total_nav)
        total_cash_f: float = float(cash_balance)

        # ── Step 3: manage CLEAR transition date ───────────────────────────
        if config is not None:
            if regime == _CONDITION_CLEAR:
                if clear_transition_date is None:
                    # First CLEAR detection — record the transition start date.
                    config.clear_transition_date = datetime.date.today()
                    clear_transition_date = config.clear_transition_date
                    await self._session.flush()
            else:
                # Left CLEAR regime — reset the transition date.
                if clear_transition_date is not None:
                    config.clear_transition_date = None
                    clear_transition_date = None
                    await self._session.flush()

        # ── Step 4: calculate floor percentage ────────────────────────────
        floor_pct, transition_active, days_until_settled = _get_floor_pct(
            regime, clear_transition_date
        )

        # ── Step 5: compute USD floor amounts ─────────────────────────────
        if total_nav_f > 0:
            floor_amount = total_nav_f * floor_pct
            buffer = max(0.0, total_cash_f - floor_amount)
            shortfall = max(0.0, floor_amount - total_cash_f)
            cash_pct = total_cash_f / total_nav_f
            buffer_pct = buffer / total_nav_f
        else:
            floor_amount = 0.0
            buffer = 0.0
            shortfall = 0.0
            cash_pct = 0.0
            buffer_pct = 0.0

        # ── Step 6: evaluate floor status ─────────────────────────────────
        floor_status, warning_level, warning_message, deployment_permitted = _evaluate_floor_status(
            total_cash_f, floor_amount, buffer_pct
        )
        is_below_floor = total_cash_f < floor_amount

        # ── Step 7: compute effective portfolio beta via Framework 13 ──────
        effective_beta, target_beta, beta_status = await self._compute_effective_beta(
            tickers, cash_pct, total_nav_f
        )

        # ── Step 8: build display strings ─────────────────────────────────
        rationale = _get_rationale(
            regime, transition_active, days_until_settled, is_below_floor, floor_amount
        )
        floor_pct_display = _get_floor_pct_display(
            regime, floor_pct, transition_active, days_until_settled
        )

        return Framework5Response(
            regime=regime,
            brent_price=brent_price,
            vix_value=vix_value,
            floor_pct=floor_pct,
            floor_pct_display=floor_pct_display,
            floor_amount=floor_amount,
            total_nav=total_nav_f,
            total_cash=total_cash_f,
            cash_pct=cash_pct,
            buffer=buffer,
            buffer_pct=buffer_pct,
            available_above_floor=buffer,
            shortfall=shortfall,
            is_below_floor=is_below_floor,
            floor_status=floor_status,
            warning_level=warning_level,
            warning_message=warning_message,
            deployment_permitted=deployment_permitted,
            transition_active=transition_active,
            transition_floor_pct=_CLEAR_TRANSITION_FLOOR if transition_active else None,
            days_until_settled=days_until_settled,
            clear_transition_date=(
                clear_transition_date.isoformat() if clear_transition_date else None
            ),
            effective_beta=effective_beta,
            target_beta=target_beta,
            beta_status=beta_status,
            floor_breach_available=True,  # breach tracking not yet implemented
            breach_count_this_quarter=0,
            rationale=rationale,
        )

    # ── Legacy per-ticker method ──────────────────────────────────────────

    async def compute_cash_floor(self, ticker: str) -> CashFloorResponse:
        """Return Framework 5 cash-floor guidance for ``ticker`` (legacy endpoint).

        Steps
        -----
        1. Calls Framework 2 (Regime Modifier) to determine the live regime rule.
        2. Fetches total portfolio NAV and cash balance from the database.
        3. Maps the regime rule to condition, rationale, and floor percentages.
        4. Converts floor percentages to USD amounts when portfolio data is available.
        """
        # ── Step 1: determine live regime rule ────────────────────────────
        regime_result = await self._regime_service.compute_regime_modifier(
            ticker,
            geopolitical_state="NONE",
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
            logger.warning(
                "Regime modifier returned unexpected result; defaulting to NORMAL",
                extra={"error": repr(regime_result), "ticker": ticker},
            )
            rule = "NORMAL"
            brent_price = None
            vix_value = None
            rule_triggered = None

        # ── Step 2: fetch total portfolio NAV and cash balance ────────────
        tickers: list[Ticker] = await self._ticker_service.list_tickers()
        invested_value: Decimal = sum(
            (t.position_value or Decimal("0")) for t in tickers
        ) or Decimal("0")

        cash_config_result = await self._session.execute(
            select(PortfolioConfig.cash_balance).where(
                PortfolioConfig.id == PORTFOLIO_CONFIG_ROW_ID
            )
        )
        cash_balance: Decimal = cash_config_result.scalar_one_or_none() or Decimal("0")
        total_nav: Decimal = invested_value + cash_balance

        total_nav_value: Decimal | None = total_nav if total_nav > 0 else None

        # ── Step 3: map regime → floor parameters ──────────────────────────
        condition, floor_pct_min, floor_pct_max, rationale = _floor_params_from_rule(rule)

        # ── Step 4: compute USD amounts ────────────────────────────────────
        floor_usd_min, floor_usd_max = _floor_usd_amounts(
            total_nav_value, floor_pct_min, floor_pct_max
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
            position_value_usd=float(total_nav_value) if total_nav_value is not None else None,
            floor_usd_min=float(floor_usd_min) if floor_usd_min is not None else None,
            floor_usd_max=float(floor_usd_max) if floor_usd_max is not None else None,
            cash_balance=float(cash_balance),
        )

    # ── Private helpers ───────────────────────────────────────────────────

    async def _compute_effective_beta(
        self,
        tickers: list[Ticker],
        cash_pct: float,
        total_nav: float,
    ) -> tuple[float, float, str]:
        """Compute effective portfolio beta via Framework 13.

        Returns (effective_beta, target_beta, beta_status).
        Defaults to (1.0, 1.75, "NORMAL") when no tickers or NAV is zero.
        """
        if not tickers or total_nav == 0.0:
            return 1.0, 1.75, "NORMAL"

        positions: list[dict[str, float | str]] = [
            {
                "ticker": t.ticker,
                "weight": float(t.position_value or Decimal("0")) / total_nav,
            }
            for t in tickers
            if t.position_value is not None and float(t.position_value) > 0
        ]

        if not positions:
            return 1.0, 1.75, "NORMAL"

        result = await calculate_portfolio_beta(positions, cash_pct)
        return result.effective_beta, result.target_beta, result.beta_status
