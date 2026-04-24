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

import logging
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.models.portfolio_config import PORTFOLIO_CONFIG_ROW_ID, PortfolioConfig
from atlas.models.ticker import Ticker
from atlas.schemas.tranche_sizing import SignalDetail, TrancheSizingResponse
from atlas.services.framework13_service import is_beta_capped
from atlas.services.regime_modifier_service import get_geo_flag_current

logger = logging.getLogger(__name__)

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

# T2 Brent gate: T2 unlocks when Brent crude is below $110.
_T2_BRENT_THRESHOLD: Final[float] = 110.0

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
# In-memory T1 persistence stub (swap for Redis in production).
# Key pattern: f4_t1_fired:{TICKER}
# Default: False when key is absent — never assume T1 is fired.
# ---------------------------------------------------------------------------

_t1_fired_store: dict[str, bool] = {}


def _get_t1_fired(ticker: str) -> bool:
    """Read T1 fired state from the in-memory stub. Returns False by default."""
    return _t1_fired_store.get(f"f4_t1_fired:{ticker.upper()}", False)


def _set_t1_fired(ticker: str, value: bool) -> None:
    """Write T1 fired state to the in-memory stub."""
    _t1_fired_store[f"f4_t1_fired:{ticker.upper()}"] = value


def reset_t1_fired_store() -> None:
    """Clear the T1 fired store. Call between tests to prevent state leakage."""
    _t1_fired_store.clear()


# ---------------------------------------------------------------------------
# In-memory T2 persistence stub (swap for Redis in production).
# T2 is auto-triggered by price condition (Framework 17).
# Key pattern: f4_t2_fired:{TICKER}
# ---------------------------------------------------------------------------

_t2_fired_store: dict[str, bool] = {}


def _get_t2_fired(ticker: str) -> bool:
    """Read T2 fired state from the in-memory stub. Returns False by default."""
    return _t2_fired_store.get(f"f4_t2_fired:{ticker.upper()}", False)


def _set_t2_fired(ticker: str, value: bool) -> None:
    """Write T2 fired state to the in-memory stub."""
    _t2_fired_store[f"f4_t2_fired:{ticker.upper()}"] = value


def fire_t2_tranche(ticker: str) -> None:
    """Confirm the T2 deployment order for a ticker.

    Called by the POST /tranche-sizing/{ticker}/confirm-t2 endpoint when the
    operator confirms the auto-triggered T2 modal (Framework 17).
    """
    _set_t2_fired(ticker.strip().upper(), True)


def reset_t2_fired_store() -> None:
    """Clear the T2 fired store. Call between tests to prevent state leakage."""
    _t2_fired_store.clear()


# ---------------------------------------------------------------------------
# In-memory T3 persistence stub (swap for Redis in production).
# T3 is auto-triggered by CLEAR regime + AND gate condition (Framework 17).
# Key pattern: f4_t3_fired:{TICKER}
# ---------------------------------------------------------------------------

_t3_fired_store: dict[str, bool] = {}


def _get_t3_fired(ticker: str) -> bool:
    """Read T3 fired state from the in-memory stub. Returns False by default."""
    return _t3_fired_store.get(f"f4_t3_fired:{ticker.upper()}", False)


def _set_t3_fired(ticker: str, value: bool) -> None:
    """Write T3 fired state to the in-memory stub."""
    _t3_fired_store[f"f4_t3_fired:{ticker.upper()}"] = value


def fire_t3_tranche(ticker: str) -> None:
    """Confirm the T3 deployment order for a ticker.

    Called by the POST /tranche-sizing/{ticker}/confirm-t3 endpoint when the
    operator confirms the auto-triggered T3 modal (Framework 17).
    """
    _set_t3_fired(ticker.strip().upper(), True)


def reset_t3_fired_store() -> None:
    """Clear the T3 fired store. Call between tests to prevent state leakage."""
    _t3_fired_store.clear()


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


def _compute_t2(brent_price: float | None) -> str:
    """Return T2 value when Brent crude is below $110 (T2 Brent gate).

    Pure function - no I/O, no side effects.
    """
    if brent_price is None:
        return _BLOCKED
    return _T2_VALUE if brent_price < _T2_BRENT_THRESHOLD else _BLOCKED


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
    t1_fired_override: bool | None = None,
    brent_consecutive_below_95_count: int = 0,
    geopolitical_state: str = "NONE",
    brent_price: float | None = None,
) -> TrancheSizingResponse:
    """Compute the Framework 4 tranche-sizing result (v7.4).

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
        When ``None``, reads from the Framework 29 in-memory stub and
        auto-detects signals 2 and 5 from live data.
    t1_fired_override:
        Override the T1 fired state from the persistence store. When provided,
        the store is not consulted or modified. Intended for testing only.
    brent_consecutive_below_95_count:
        Number of consecutive Brent closes below $95. Used to auto-detect
        signal 2 of the AND gate (>= 2 closes confirms the signal).
    geopolitical_state:
        Current geopolitical state string (e.g. ``"RESOLVED"``). Used to
        auto-detect signal 5 of the AND gate.
    brent_price:
        Current Brent crude price in USD per barrel. T2 unlocks when
        ``brent_price < 110`` and T1 has already fired.
    """
    normalised = ticker.strip().upper()

    # Persist T1 fired state when catalyst is confirmed and no override is in use.
    # Persistence happens before the cap check so confirmations survive cap suppression.
    if t1_fired_override is None and initial_catalyst.strip().lower() == "yes":
        _set_t1_fired(normalised, True)

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
            t1_fired=False,
            t2_fired=False,
            t2_pending=False,
            t3_fired=False,
            t3_pending=False,
        )

    # Step 2: Check Framework 13 beta cap.
    beta_check = is_beta_capped(normalised, position_weight)
    if beta_check["cap_active"]:
        beta_val: float = beta_check["beta"]  # type: ignore[assignment]
        cap_limit_pct: float = beta_check["cap_limit_pct"]  # type: ignore[assignment]
        effective_exp: float = beta_check["effective_exposure"]  # type: ignore[assignment]
        beta_msg = (
            f"Adds blocked by beta cap — tranche sizing N/A\n"
            f"Beta: {beta_val} | Max: {cap_limit_pct:.1f}% NAV\n"
            f"Effective exposure: {effective_exp:.2f}%"
        )
        return TrancheSizingResponse(
            ticker=normalised,
            cap_active=False,
            beta_cap_active=True,
            beta_cap_reason=str(beta_check["cap_reason"]),
            tranche_display=False,
            position_weight=position_weight,
            message=beta_msg,
            and_gate_active=False,
            and_gate_passed=False,
            signals_confirmed=0,
            signals_detail=_build_signal_details([False] * 5),
            t1=None,
            t2=None,
            t3=None,
            t4=None,
            t1_fired=False,
            t2_fired=False,
            t2_pending=False,
            t3_fired=False,
            t3_pending=False,
        )

    # Step 3a: Check Framework 15 VIX session halt.
    from atlas.services.framework15_service import get_f15_simple as _get_f15_simple

    _f15 = _get_f15_simple()
    if _f15 is not None and _f15.f15_active is True:
        _f15_msg = "Paused \u2014 F15 VIX session halt"
        return TrancheSizingResponse(
            ticker=normalised,
            cap_active=False,
            beta_cap_active=False,
            tranche_display=False,
            position_weight=position_weight,
            message=_f15_msg,
            and_gate_active=False,
            and_gate_passed=False,
            signals_confirmed=0,
            signals_detail=_build_signal_details([False] * 5),
            t1=None,
            t2=None,
            t3=None,
            t4=None,
            t1_fired=False,
            t2_fired=False,
            t2_pending=False,
            t3_fired=False,
            t3_pending=False,
        )
    if _f15 is not None and _f15.f15_active is None:
        _f15_unknown_msg = "Unknown \u2014 F15 VIX data unavailable"
        return TrancheSizingResponse(
            ticker=normalised,
            cap_active=False,
            beta_cap_active=False,
            tranche_display=False,
            position_weight=position_weight,
            message=_f15_unknown_msg,
            and_gate_active=False,
            and_gate_passed=False,
            signals_confirmed=0,
            signals_detail=_build_signal_details([False] * 5),
            t1=None,
            t2=None,
            t3=None,
            t4=None,
            t1_fired=False,
            t2_fired=False,
            t2_pending=False,
            t3_fired=False,
            t3_pending=False,
        )

    # Step 3: Determine AND gate state (Framework 29).
    regime_normalised = regime_rule.strip().upper()
    and_gate_active = regime_normalised == _REGIME_CLEAR

    if and_gate_active:
        if signals_count_override is not None:
            count = min(max(int(signals_count_override), 0), 5)
            signals: list[bool] = [i < count for i in range(5)]
        else:
            signals = get_and_gate_signals(normalised)
            # Auto-detect signal 2: Brent second consecutive close below $95
            signals[1] = brent_consecutive_below_95_count >= 2
            # Auto-detect signal 5: geopolitical flag = RESOLVED.
            # Priority: query param → in-memory store written by Framework 2.
            # Bytes are already decoded (string param); strip + uppercase guard.
            geo_upper = geopolitical_state.strip().upper()
            if geo_upper == "NONE":
                # Fall back to the shared store set by Framework 2's regime eval.
                stored = get_geo_flag_current()
                if stored != "NONE":
                    geo_upper = stored
            signals[4] = geo_upper == "RESOLVED"
            logger.debug(
                "signal_5_detection",
                extra={
                    "geo_param": geopolitical_state,
                    "geo_normalised": geo_upper,
                    "signal_5_confirmed": signals[4],
                    "brent_consecutive": brent_consecutive_below_95_count,
                    "signal_2_confirmed": signals[1],
                },
            )
            count = sum(1 for s in signals if s)

        and_gate_passed = count >= _AND_GATE_THRESHOLD
        signal_details = _build_signal_details(signals)
        signals_confirmed = count
    else:
        and_gate_passed = False
        signal_details = _build_signal_details([False] * 5)
        signals_confirmed = 0

    # Step 3: Determine T1 fired state, then apply sequential gate.
    # The override takes precedence over the persistence store (testing only).
    t1_fired = t1_fired_override if t1_fired_override is not None else _get_t1_fired(normalised)

    # T1 is always derived from the fired state (not re-evaluated from catalyst).
    t1 = _T1_VALUE if t1_fired else _BLOCKED

    # Sequential gate: T2/T3/T4 are blocked until T1 fires.
    if t1_fired:
        t2 = _compute_t2(brent_price)
        t3 = _compute_t3(regime_rule, and_gate_passed)
        t4 = _compute_t4(iran_resolution)
    else:
        t2 = _BLOCKED
        t3 = _BLOCKED
        t4 = _BLOCKED

    # Step 4: Determine T2/T3 auto-trigger pending and fired states (Framework 17).
    # T2 and T3 are auto-triggered — the operator confirms the order, not the trigger.
    t2_fired = _get_t2_fired(normalised)
    t2_conditions_met = t2 == _T2_VALUE
    t2_pending = t2_conditions_met and not t2_fired

    t3_fired = _get_t3_fired(normalised)
    t3_conditions_met = t3 == _T3_VALUE
    t3_pending = t3_conditions_met and not t3_fired

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
        t1_fired=t1_fired,
        t2_fired=t2_fired,
        t2_pending=t2_pending,
        t3_fired=t3_fired,
        t3_pending=t3_pending,
        catalyst_confirmed=t1_fired,
    )
