"""Framework 6 — Conviction Action service.

Derives an investor action and status from the regime-adjusted Framework Score
(Framework 1 combined score, modified by Framework 2 Regime Modifier rule).

Conviction tiers (evaluated against the adjusted score):
  score > 80  → HOLD  : "You already own this stock"
                          ["Hold everything", "Buy more on every dip"]
  72 ≤ score ≤ 80 → READY : "Ready to buy"
                             ["Deploy T2 and T3 tranches", "Serious capital"]
  65 ≤ score < 72 → EARLY : "Early thesis developing"
                             ["Small positions only", "Buy options not shares"]
  60 ≤ score < 65 → RADAR : "On radar, unconfirmed"
                             ["Zero capital deployed", "Monitor every Sunday only"]
  score < 60  → EXIT  : "EXIT"
                         ["Sell on Next bounce"]

Pure helper (_tier_from_score) is side-effect-free and fully unit-testable
without mocks or network calls.
"""

from __future__ import annotations

import logging
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.schemas.conviction_action import ConvictionActionResponse
from atlas.schemas.regime_modifier import RegimeModifierResponse
from atlas.services.regime_modifier_service import RegimeModifierService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier score thresholds (inclusive lower bounds)
# ---------------------------------------------------------------------------

# score strictly greater than this → HOLD tier
_THRESHOLD_HOLD: Final[int] = 80

# score ≥ this → READY tier  (if not already HOLD)
_THRESHOLD_READY: Final[int] = 72

# score ≥ this → EARLY tier  (if not HOLD or READY)
_THRESHOLD_EARLY: Final[int] = 65

# score ≥ this → RADAR tier  (if not above)
_THRESHOLD_RADAR: Final[int] = 60

# score below RADAR threshold → EXIT tier

# ---------------------------------------------------------------------------
# Pure helper — no I/O, no side effects, fully unit-testable
# ---------------------------------------------------------------------------


def _tier_from_score(score: int) -> tuple[str, str, list[str], str]:
    """Map a regime-adjusted score to a conviction tier.

    Parameters
    ----------
    score:
        Regime-adjusted framework score (0-100).

    Returns
    -------
    tuple of (tier_key, status, actions, tone)

    Pure function — no I/O.
    """
    if score > _THRESHOLD_HOLD:
        return (
            "HOLD",
            "Hold full — add on dips",
            ["Hold full — add on dips"],
            "green",
        )
    if score >= _THRESHOLD_READY:
        return (
            "READY",
            "Deploy T2/T3",
            ["Deploy T2/T3"],
            "cyan",
        )
    if score >= _THRESHOLD_EARLY:
        return (
            "EARLY",
            "Small positions, options preferred",
            ["Small positions, options preferred"],
            "yellow",
        )
    if score >= _THRESHOLD_RADAR:
        return (
            "RADAR",
            "No deployment — monitor",
            ["No deployment — monitor"],
            "orange",
        )
    return (
        "EXIT",
        "Sell on next bounce",
        ["Sell on next bounce"],
        "red",
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class ConvictionActionService:
    """Computes the Framework 6 conviction-action guidance for a single ticker.

    Internally calls :class:`~atlas.services.regime_modifier_service.RegimeModifierService`
    to obtain the regime-adjusted Framework Score, then maps it to a conviction
    tier via :func:`_tier_from_score`.

    Parameters
    ----------
    polygon_api_key, alphavantage_api_key, transcript_api_key,
    benzinga_api_key, unusual_whales_api_key, sec_api_key:
        Forwarded to the internal :class:`RegimeModifierService`.
    session:
        SQLAlchemy async session (required by RegimeModifierService for
        portfolio position lookups; not used directly here).
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

    async def compute_conviction_action(
        self,
        ticker: str,
        provided_base_score: int | None = None,
        provided_adjusted_score: int | None = None,
    ) -> ConvictionActionResponse:
        """Return the Framework 6 conviction-action guidance for ``ticker``.

        When ``provided_adjusted_score`` is given (the score already displayed
        by the F1 panel, which has the regime modifier applied client-side),
        the regime service is skipped entirely — no double-penalty.

        When only ``provided_base_score`` is given, the regime service is
        called with that value to avoid a second independent F1 fetch but
        the regime delta is still applied once.

        When neither is given, a full independent F1 + regime fetch is made.
        """
        # Fast path: caller already supplies the fully-adjusted score
        # (same number displayed on the F1 panel).
        if provided_adjusted_score is not None:
            adjusted_score = max(0, min(100, provided_adjusted_score))
            tier_key, status, actions, tone = _tier_from_score(adjusted_score)
            return ConvictionActionResponse(
                ticker=ticker,
                base_score=provided_base_score if provided_base_score is not None else adjusted_score,
                adjusted_score=adjusted_score,
                rule="N/A",
                tier_key=tier_key,
                status=status,
                actions=actions,
                tone=tone,
            )

        # Slow path: call Framework 2 to obtain the regime-adjusted score.
        regime_result = await self._regime_service.compute_regime_modifier(
            ticker,
            geopolitical_state="NONE",
            provided_base_score=provided_base_score,
        )

        slow_adjusted_score: int
        slow_base_score: int
        slow_rule: str

        if isinstance(regime_result, RegimeModifierResponse):
            slow_adjusted_score = regime_result.adjusted_score
            slow_base_score = regime_result.base_score
            slow_rule = regime_result.rule
        else:
            logger.warning(
                "Regime modifier returned unexpected result; defaulting scores to 50",
                extra={"error": repr(regime_result), "ticker": ticker},
            )
            slow_adjusted_score = 50
            slow_base_score = 50
            slow_rule = "NORMAL"

        tier_key, status, actions, tone = _tier_from_score(slow_adjusted_score)

        return ConvictionActionResponse(
            ticker=ticker,
            base_score=slow_base_score,
            adjusted_score=slow_adjusted_score,
            rule=slow_rule,
            tier_key=tier_key,
            status=status,
            actions=actions,
            tone=tone,
        )
