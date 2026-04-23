"""Framework 7 — Earnings Gate Rule service.

Applies the Earnings Gate Rule to determine whether the investor may add to
a position ahead of an upcoming earnings release.

Rules (applied in priority order when gate is active):
  1. insider_flag True              → DOUBLE BLOCKED  (F8 also active)
  2. final_score <= 80              → CLOSED           (zero adds)
  3. final_score  > 80              → 50% CAP          (50% target weight)
  4. gate not active / no earnings  → OPEN             (no restriction)

Gate close date calculation:
  Count back exactly 5 trading weekdays from the earnings date.
  Gate is active when today >= gate_close_date.

Earnings dates are fetched fresh from Alpha Vantage EARNINGS_CALENDAR (CSV)
on every request — no caching.

The final_score is fetched from Framework 1 (FrameworkScoreService) unless
the caller supplies ``provided_score`` directly (e.g. from the frontend cache)
to avoid double-fetching.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, timedelta
from typing import Final

import httpx

from atlas.schemas.framework7 import EarningsGate
from atlas.schemas.framework_score import FrameworkScoreResponse
from atlas.services.framework8_service import Framework8Service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trading days to count back from earnings date.
_GATE_DAYS: Final[int] = 5

# Score above which pre-earnings adds are permitted (50% cap).
# Strictly greater than: score > _SCORE_THRESHOLD → 50% CAP.
_SCORE_THRESHOLD: Final[int] = 80

# Status string constants — four possible values only.
_STATUS_OPEN: Final[str] = "OPEN"
_STATUS_CLOSED: Final[str] = "CLOSED"
_STATUS_CAP_50: Final[str] = "50% CAP"
_STATUS_DOUBLE_BLOCKED: Final[str] = "DOUBLE BLOCKED"

# AlphaVantage EARNINGS_CALENDAR URL.
_AV_EARNINGS_URL: Final[str] = "https://www.alphavantage.co/query"

# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def calculate_gate_close_date(earnings_date: date) -> date:
    """Count back exactly 5 trading weekdays from ``earnings_date``.

    Weekends (Saturday = 5, Sunday = 6) are skipped.
    Returns the date on which the gate closes (the 5th trading day back).

    Pure function -- no I/O.
    """
    current = earnings_date
    days_counted = 0
    while days_counted < _GATE_DAYS:
        current -= timedelta(days=1)
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            days_counted += 1
    return current


def _evaluate_gate_logic(
    *,
    ticker: str,
    today: date,
    earnings_date: date | None,
    final_score: int,
    insider_flag: bool,
) -> EarningsGate:
    """Apply Framework 7 gate rules. Pure function -- no I/O.

    Parameters
    ----------
    ticker:
        Ticker symbol (any case; stored as-is).
    today:
        The reference date for gate_active evaluation (injectable for testing).
    earnings_date:
        Next earnings date, or None when no upcoming earnings found.
    final_score:
        Regime-adjusted Framework 1 score (0-100).
    insider_flag:
        True when Framework 8 detects recent significant insider selling.

    Returns
    -------
    EarningsGate with status one of: OPEN | CLOSED | 50% CAP | DOUBLE BLOCKED
    """
    # ── No earnings date found ─────────────────────────────────────────────
    if earnings_date is None:
        return EarningsGate(
            ticker=ticker,
            earnings_date=None,
            gate_close_date=None,
            days_to_earnings=None,
            gate_active=False,
            final_score=final_score,
            insider_flag=insider_flag,
            can_add=True,
            size_cap=1.0,
            status=_STATUS_OPEN,
            message="No upcoming earnings — no gate active",
        )

    _gate_close = calculate_gate_close_date(earnings_date)
    days_to_earnings = (earnings_date - today).days
    gate_active = today >= _gate_close

    # ── Gate not yet active ────────────────────────────────────────────────
    if not gate_active:
        return EarningsGate(
            ticker=ticker,
            earnings_date=earnings_date,
            gate_close_date=_gate_close,
            days_to_earnings=days_to_earnings,
            gate_active=False,
            final_score=final_score,
            insider_flag=insider_flag,
            can_add=True,
            size_cap=1.0,
            status=_STATUS_OPEN,
            message=(
                f"Gate opens {_gate_close.isoformat()} — "
                f"{days_to_earnings} days to earnings"
            ),
        )

    # ── Gate active: priority-order rule evaluation ────────────────────────

    # Rule priority 1: insider flag overrides everything.
    if insider_flag:
        return EarningsGate(
            ticker=ticker,
            earnings_date=earnings_date,
            gate_close_date=_gate_close,
            days_to_earnings=days_to_earnings,
            gate_active=True,
            final_score=final_score,
            insider_flag=True,
            can_add=False,
            size_cap=0.0,
            status=_STATUS_DOUBLE_BLOCKED,
            message=(
                "Insider activity detected. Framework 8 also active. "
                "No adds under any condition — even if score crosses 80."
            ),
        )

    # Rule priority 2: score at or below threshold → gate closed.
    if final_score <= _SCORE_THRESHOLD:
        return EarningsGate(
            ticker=ticker,
            earnings_date=earnings_date,
            gate_close_date=_gate_close,
            days_to_earnings=days_to_earnings,
            gate_active=True,
            final_score=final_score,
            insider_flag=False,
            can_add=False,
            size_cap=0.0,
            status=_STATUS_CLOSED,
            message=(
                f"Score {final_score} is at or below 80. "
                "Gate closed. Zero position adds."
            ),
        )

    # Rule priority 3: score strictly above threshold → 50% cap.
    return EarningsGate(
        ticker=ticker,
        earnings_date=earnings_date,
        gate_close_date=_gate_close,
        days_to_earnings=days_to_earnings,
        gate_active=True,
        final_score=final_score,
        insider_flag=False,
        can_add=True,
        size_cap=0.5,
        status=_STATUS_CAP_50,
        message=(
            f"Score {final_score} above 80. "
            "Pre-earnings add permitted — capped at 50% of target weight "
            "until earnings print is confirmed."
        ),
    )


# ---------------------------------------------------------------------------
# Async I/O helpers
# ---------------------------------------------------------------------------


async def get_earnings_date(ticker: str, api_key: str) -> str | None:
    """Fetch the next earnings report date for ``ticker`` from Alpha Vantage.

    Calls the EARNINGS_CALENDAR endpoint (CSV response) fresh on every call.

    Parameters
    ----------
    ticker:
        Ticker symbol (case-insensitive).
    api_key:
        Alpha Vantage API key.

    Returns
    -------
    ISO-format date string (YYYY-MM-DD) or None when not found / API error.
    """
    ticker_upper = ticker.upper()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _AV_EARNINGS_URL,
                params={
                    "function": "EARNINGS_CALENDAR",
                    "symbol": ticker_upper,
                    "horizon": "3month",
                    "apikey": api_key,
                },
            )
            resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            if row.get("symbol", "").upper() == ticker_upper:
                return row.get("reportDate") or None

        # Ticker present in portfolio but no upcoming earnings in 3-month window.
        return None

    except Exception as exc:
        logger.warning(
            "Failed to fetch earnings date from Alpha Vantage",
            extra={"ticker": ticker_upper, "error": repr(exc)},
        )
        return None


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class Framework7Service:
    """Orchestrates the Framework 7 Earnings Gate evaluation for a ticker.

    Wires together:
      - Alpha Vantage EARNINGS_CALENDAR (earnings date fetch + 24-hour cache)
      - Framework 1 score (FrameworkScoreService or caller-supplied score)
      - Framework 8 insider flag (Framework8Service)
      - Pure gate-rule evaluation (_evaluate_gate_logic)

    Parameters
    ----------
    alphavantage_api_key:
        Required for earnings date lookup.
    polygon_api_key, transcript_api_key, benzinga_api_key,
    unusual_whales_api_key:
        Forwarded to FrameworkScoreService for F1 computation.
    sec_api_key:
        Forwarded to Framework8Service for insider flag.
    """

    def __init__(
        self,
        alphavantage_api_key: str,
        polygon_api_key: str,
        transcript_api_key: str,
        benzinga_api_key: str,
        unusual_whales_api_key: str,
        sec_api_key: str,
    ) -> None:
        self._alphavantage_api_key = alphavantage_api_key
        self._sec_api_key = sec_api_key
        self._f8_service = Framework8Service(sec_api_key=sec_api_key)

        # Framework 1 service — imported here to avoid circular imports at
        # module level; instantiated lazily only when provided_score is absent.
        from atlas.services.framework_score_service import FrameworkScoreService

        self._f1_service = FrameworkScoreService(
            polygon_api_key=polygon_api_key,
            alphavantage_api_key=alphavantage_api_key,
            transcript_api_key=transcript_api_key,
            benzinga_api_key=benzinga_api_key,
            unusual_whales_api_key=unusual_whales_api_key,
            sec_api_key=sec_api_key,
        )

    async def compute(
        self,
        ticker: str,
        provided_score: int | None = None,
    ) -> EarningsGate:
        """Evaluate the Framework 7 Earnings Gate for ``ticker``.

        Parameters
        ----------
        ticker:
            Ticker symbol (normalised to upper-case by the caller).
        provided_score:
            The regime-adjusted Framework 1 score already displayed by the
            frontend.  When supplied, skips the F1 service call.  When None,
            fetches the score from FrameworkScoreService.

        Returns
        -------
        EarningsGate with one of: OPEN | CLOSED | 50% CAP | DOUBLE BLOCKED
        """
        import asyncio

        if provided_score is not None:
            earnings_date_str = await get_earnings_date(ticker, self._alphavantage_api_key)
            final_score = provided_score
        else:
            earnings_date_str_result, f1_result = await asyncio.gather(
                get_earnings_date(ticker, self._alphavantage_api_key),
                self._f1_service.compute_framework_score(ticker),
                return_exceptions=True,
            )
            earnings_date_str = (
                earnings_date_str_result
                if isinstance(earnings_date_str_result, str)
                else None
            )
            if isinstance(f1_result, FrameworkScoreResponse):
                final_score = f1_result.final_score
            else:
                logger.error(
                    "Framework 1 score fetch failed; defaulting to 50",
                    extra={"ticker": ticker, "error": repr(f1_result)},
                )
                final_score = 50

        # Fetch insider flag from Framework 8.
        insider_flag = await self._f8_service.get_insider_flag(ticker)

        # Parse earnings date string -> date object.
        earnings_date: date | None = None
        if isinstance(earnings_date_str, str) and earnings_date_str:
            try:
                earnings_date = date.fromisoformat(earnings_date_str)
            except ValueError:
                logger.warning(
                    "Unparseable earnings date string",
                    extra={"ticker": ticker, "raw": earnings_date_str},
                )

        return _evaluate_gate_logic(
            ticker=ticker,
            today=date.today(),
            earnings_date=earnings_date,
            final_score=final_score,
            insider_flag=insider_flag,
        )
