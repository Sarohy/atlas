"""Framework 4 - Tranche Sizing service (v7.3.4).

Maps three external signals to four cash-deployment tranches (T1-T4).

v7.3.4 changes
--------------
- T3 now requires CLEAR regime AND Framework 29 AND gate (3/5 signals).
  CLEAR alone is not sufficient; AND gate alone is not sufficient.
  Both must be true simultaneously.
- All tranches suppressed when Framework 14 concentration cap is active
  (position weight >= 8% NAV).
- AND gate also required for any CLEAR-triggered decision above $10K,
  including LEAPS entries - enforced via and_gate_passed field in response.

Framework 4 reads from (does not modify):
- Framework 14 stub: get_position_weight(ticker) - concentration cap
- Framework 29 stub: get_and_gate_signals(ticker) - capitulation signals

Tranche rules
-------------
T1  "10-15% of available cash"   when initial_catalyst == "yes"
T2  "20-25% of available cash"   when regime_rule       == "CAUTION"
T3  "30-40% of available cash"   when regime_rule       == "CLEAR" AND and_gate_passed
T4  "Remaining cash to floor"    when iran_resolution   == "confirmed"

Any gate that is not met returns "Blocked".
All tranches return None when cap_active is True.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.portfolio_config import PORTFOLIO_CONFIG_ROW_ID, PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.schemas.tranche_sizing import SignalDetail, TrancheSizingResponse

# ---------------------------------------------------------------------------
# Output constants
# ---------------------------------------------------------------------------

_BLOCKED: Final[str] = "Blocked"
_T1_VALUE: Final[str] = "10-15% of available cash"
_T2_VALUE: Final[str] = "20-25% of available cash"
_T3_VALUE: Final[str] = "30-40% of available cash"
_T4_VALUE: Final[str] = "Remaining cash to floor"

# ---------------------------------------------------------------------------
# Gate thresholds
# ---------------------------------------------------------------------------

# Concentration cap threshold per Framework 13: 8% NAV soft cap.
_CONCENTRATION_CAP_THRESHOLD: Final[float] = 0.08

# AND gate: 3 of 5 capitulation signals required per Framework 29.
_AND_GATE_THRESHOLD: Final[int] = 3

# ---------------------------------------------------------------------------
# Regime rule sentinels
# ---------------------------------------------------------------------------

_REGIME_CAUTION: Final[str] = "CAUTION"
_REGIME_CLEAR: Final[str] = "CLEAR"

# ---------------------------------------------------------------------------
# Suppression message
# ---------------------------------------------------------------------------

_CAP_SUPPRESSION_MESSAGE: Final[str] = "Adds blocked by concentration cap - tranche sizing N/A"

# ---------------------------------------------------------------------------
# AND gate signal names (Framework 29 capitulation signals)
# ---------------------------------------------------------------------------

_SIGNAL_NAMES: Final[tuple[str, ...]] = (
    "VIX touched prior regime high then declined 3 consecutive sessions",
    "Brent second consecutive close below $95 confirmed",
    "Put/call ratio reached above 1.3 then reversed direction",
    "S&P 500 stocks above 50-DMA dropped below 30% then recovered",
    "Operator geopolitical flag set to RESOLVED",
)

# ---------------------------------------------------------------------------
# In-memory Framework 29 stub - AND gate signal states per ticker
# Defaults to all unconfirmed when no state has been recorded.
# ---------------------------------------------------------------------------

_AND_GATE_SIGNAL_STATES: dict[str, list[bool]] = {}

# ---------------------------------------------------------------------------
# Framework 14 interface (read-only from Framework 4's perspective)
# ---------------------------------------------------------------------------


async def get_position_weight(ticker: str, session: AsyncSession) -> float:
    """Return position weight as a fraction of NAV by querying the live portfolio.

    Fetches the ticker's position_value, sums all position values, and adds
    cash_balance from PortfolioConfig to compute total NAV.
    Returns 0.0 when the ticker is not in the portfolio or has no price.
    """
    normalised = ticker.strip().upper()

    ticker_result = await session.execute(
        select(Ticker.position_value).where(Ticker.ticker == normalised)
    )
    position_value: Decimal | None = ticker_result.scalar_one_or_none()
    if position_value is None:
        return 0.0

    all_values_result = await session.execute(select(Ticker.position_value))
    invested: Decimal = sum(
        (v or Decimal("0")) for v in all_values_result.scalars().all()
    ) or Decimal("0")

    config = await session.get(PortfolioConfig, PORTFOLIO_CONFIG_ROW_ID)
    cash: Decimal = config.cash_balance if config is not None else Decimal("0")
    total_nav: Decimal = invested + cash

    if total_nav <= 0:
        return 0.0

    return float(position_value / total_nav)


# ---------------------------------------------------------------------------
# Framework 29 stub interface (read-only from Framework 4's perspective)
# ---------------------------------------------------------------------------


def get_and_gate_signals(ticker: str) -> list[bool]:
    """Return per-signal confirmation states from the Framework 29 stub.

    Returns a list of 5 booleans - one per capitulation signal.
    Defaults to [False, False, False, False, False] for unknown tickers.
    Pure read - no side effects.
    """
    return list(_AND_GATE_SIGNAL_STATES.get(ticker.strip().upper(), [False] * 5))


def _set_and_gate_signals(ticker: str, signals: list[bool]) -> None:
    """Mutate the Framework 29 stub (for testing only)."""
    _AND_GATE_SIGNAL_STATES[ticker.strip().upper()] = list(signals)


# ---------------------------------------------------------------------------
# Pure gate helpers
# ---------------------------------------------------------------------------


def _compute_t1(initial_catalyst: str) -> str:
    """Return T1 value when the initial catalyst is confirmed.

    Pure function - no I/O, no side effects.
    """
    return _T1_VALUE if initial_catalyst.strip().lower() == "yes" else _BLOCKED


def _compute_t2(regime_rule: str) -> str:
    """Return T2 value when the Framework 2 regime is CAUTION.

    Pure function - no I/O, no side effects.
    """
    return _T2_VALUE if regime_rule.strip().upper() == _REGIME_CAUTION else _BLOCKED


def _compute_t3(regime_rule: str, and_gate_passed: bool) -> str:
    """Return T3 value when CLEAR regime is confirmed AND the AND gate passes.

    v7.3.4: CLEAR alone is not sufficient. Both CLEAR regime and Framework 29
    AND gate (3/5 capitulation signals) must be confirmed simultaneously.

    Pure function - no I/O, no side effects.
    """
    regime_clear = regime_rule.strip().upper() == _REGIME_CLEAR
    return _T3_VALUE if (regime_clear and and_gate_passed) else _BLOCKED


def _compute_t4(iran_resolution: str | None) -> str:
    """Return T4 value when the Iran Resolution is confirmed.

    Pure function - no I/O, no side effects.
    """
    if iran_resolution is None:
        return _BLOCKED
    return _T4_VALUE if iran_resolution.strip().lower() == "confirmed" else _BLOCKED


def _build_signal_details(signals: list[bool]) -> list[SignalDetail]:
    """Build signal detail objects from a 5-element boolean list.

    Pure function - no I/O, no side effects.
    """
    return [
        SignalDetail(
            signal_index=i + 1,
            name=_SIGNAL_NAMES[i],
            confirmed=signals[i],
        )
        for i in range(len(_SIGNAL_NAMES))
    ]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_tranche_sizing(
    ticker: str,
    initial_catalyst: str,
    regime_rule: str = "NORMAL",
    iran_resolution: str | None = None,
    position_weight: float = 0.0,
    signals_count_override: int | None = None,
) -> TrancheSizingResponse:
    """Compute the Framework 4 tranche-sizing result (v7.3.4).

    Parameters
    ----------
    ticker:
        Portfolio ticker symbol (normalised to upper-case internally).
    initial_catalyst:
        ``"yes"`` or ``"no"`` - whether the entry catalyst has fired.
    regime_rule:
        The Framework 2 regime rule already held by the UI
        (``"CRISIS"`` | ``"CAUTION"`` | ``"CLEAR"`` | ``"NORMAL"``).
        Defaults to ``"NORMAL"`` (all regime gates blocked) when not supplied.
    iran_resolution:
        ``"confirmed"`` to unlock T4; anything else (including ``None``)
        keeps T4 blocked.
    position_weight:
        Position weight as a fraction of NAV (0.0-1.0). Resolved by the router
        from live portfolio data (Framework 14) before calling this function.
    signals_count_override:
        Override the count of confirmed AND gate signals. When provided, the
        first N signals are treated as confirmed and the remainder as pending.
        When ``None``, reads from the Framework 29 in-memory stub.
    """
    normalised = ticker.strip().upper()

    # Step 1: Check concentration cap (Framework 14).
    cap_active = position_weight >= _CONCENTRATION_CAP_THRESHOLD

    if cap_active:
        # Return suppressed result - skip all tranche calculation.
        return TrancheSizingResponse(
            ticker=normalised,
            cap_active=True,
            tranche_display=False,
            position_weight=position_weight,
            message=_CAP_SUPPRESSION_MESSAGE,
            and_gate_active=False,
            and_gate_passed=False,
            signals_confirmed=0,
            signals_detail=_build_signal_details([False] * 5),
            t1=None,
            t2=None,
            t3=None,
            t4=None,
        )

    # Step 2: Determine AND gate state (Framework 29).
    regime_normalised = regime_rule.strip().upper()
    and_gate_active = regime_normalised == _REGIME_CLEAR

    if and_gate_active:
        if signals_count_override is not None:
            count = min(max(int(signals_count_override), 0), 5)
            signals: list[bool] = [i < count for i in range(5)]
        else:
            signals = get_and_gate_signals(normalised)
            count = sum(1 for s in signals if s)

        and_gate_passed = count >= _AND_GATE_THRESHOLD
        signal_details = _build_signal_details(signals)
        signals_confirmed = count
    else:
        and_gate_passed = False
        signal_details = _build_signal_details([False] * 5)
        signals_confirmed = 0

    # Step 3: Calculate tranche values.
    t1 = _compute_t1(initial_catalyst)
    t2 = _compute_t2(regime_rule)
    t3 = _compute_t3(regime_rule, and_gate_passed)
    t4 = _compute_t4(iran_resolution)

    return TrancheSizingResponse(
        ticker=normalised,
        cap_active=False,
        tranche_display=True,
        position_weight=position_weight,
        message=None,
        and_gate_active=and_gate_active,
        and_gate_passed=and_gate_passed,
        signals_confirmed=signals_confirmed,
        signals_detail=signal_details,
        t1=t1,
        t2=t2,
        t3=t3,
        t4=t4,
    )
