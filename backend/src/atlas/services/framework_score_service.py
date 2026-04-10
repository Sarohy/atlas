"""Framework Score service — aggregates F1-F5 into a single conviction score.

Formula (Factor_Mapping_Guide §Final Score):
  Raw Total   = (F1 x 0.20) + (F2 x 0.25) + (F3 x 0.15) + (F4 x 0.15) + (F5 x 0.20)
  Final Score = round(Raw Total), clamped [0, 100]

  Maximum raw total = 95 (all factors at 100, weights sum to 0.95).

All pure helpers (_map_action, _compute_raw_total, _compute_final_score) are
side-effect-free and unit-testable without mocks.

The ``FrameworkScoreService`` class orchestrates all five sub-services
concurrently via ``asyncio.gather``.  Any sub-service failure (missing key,
network error) falls back to a neutral factor score of 50 and records a flag
message rather than aborting the entire request.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import httpx

from atlas.schemas.analyst import AnalystResponse
from atlas.schemas.earnings import EarningsResponse
from atlas.schemas.framework_score import (
    FactorBreakdown,
    FrameworkScoreResponse,
)
from atlas.schemas.fundamental import FundamentalResponse
from atlas.schemas.momentum import MomentumResponse
from atlas.schemas.options_flow import OptionsFlowResponse
from atlas.services.analyst_service import AnalystService
from atlas.services.earnings_service import EarningsService
from atlas.services.fundamental_service import FundamentalService
from atlas.services.momentum_service import MomentumService
from atlas.services.options_flow_service import OptionsFlowService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Framework-level weights (Factor_Mapping_Guide §Final Score)
# ---------------------------------------------------------------------------

# Each factor is scored 0-100; multiplied by its weight to contribute to the
# raw total.  Weights sum to 0.95 (maximum raw total = 95).
_W_F1: Final[float] = 0.20  # Momentum
_W_F2: Final[float] = 0.25  # Earnings Quality
_W_F3: Final[float] = 0.15  # Analyst Sentiment
_W_F4: Final[float] = 0.15  # Options Flow
_W_F5: Final[float] = 0.20  # Fundamental Quality

# Score thresholds for action map (inclusive lower bound).
_ACTION_MAX_MIN: Final[int] = 90
_ACTION_HOLD_ADD_MIN: Final[int] = 80
_ACTION_HOLD_MIN: Final[int] = 70
_ACTION_REDUCE_MIN: Final[int] = 60
_ACTION_REDUCE_FURTHER_MIN: Final[int] = 55

# Neutral fallback score when a factor service is unavailable.
_NEUTRAL_SCORE: Final[int] = 50


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no side effects
# ---------------------------------------------------------------------------


def _map_action(final_score: int) -> tuple[str, str]:
    """Map a final conviction score to (action_string, tone_class).

    Pure function — no I/O.

    Score -> Action map (Factor_Mapping_Guide §Score-Action):
      90-100  MAXIMUM POSITION  tone-green
      80-89   HOLD / ADD        tone-cyan
      70-79   HOLD              tone-yellow
      60-69   REDUCE            tone-orange
      55-59   REDUCE FURTHER    tone-red
      <  55   EXIT              tone-dark-red
    """
    if final_score >= _ACTION_MAX_MIN:
        return "MAXIMUM POSITION", "tone-green"
    if final_score >= _ACTION_HOLD_ADD_MIN:
        return "HOLD / ADD", "tone-cyan"
    if final_score >= _ACTION_HOLD_MIN:
        return "HOLD", "tone-yellow"
    if final_score >= _ACTION_REDUCE_MIN:
        return "REDUCE", "tone-orange"
    if final_score >= _ACTION_REDUCE_FURTHER_MIN:
        return "REDUCE FURTHER", "tone-red"
    return "EXIT", "tone-dark-red"


def _compute_raw_total(f1: int, f2: int, f3: int, f4: int, f5: int) -> float:
    """Return the weighted sum of the five factor scores (max = 95.0).

    Pure function — no I/O.
    """
    return f1 * _W_F1 + f2 * _W_F2 + f3 * _W_F3 + f4 * _W_F4 + f5 * _W_F5


def _compute_final_score(raw_total: float) -> int:
    """Clamp the raw total to [0, 100].

    Pure function — no I/O.
    """
    return max(0, min(100, round(raw_total)))


# ---------------------------------------------------------------------------
# Service class — orchestrates F1-F5 + regime concurrently
# ---------------------------------------------------------------------------


class FrameworkScoreService:
    """Computes the complete ATLAS Framework Score for a single ticker.

    Calls all five factor services concurrently (``asyncio.gather``).
    Any sub-service that fails (missing API key, network error) falls back
    to a neutral score of 50 and appends a descriptive flag.

    Parameters
    ----------
    polygon_api_key:
        Polygon.io key — used by MomentumService and Brent crude fetch.
    alphavantage_api_key:
        Alpha Vantage key — used by EarningsService and FundamentalService.
    transcript_api_key:
        FMP key — used by EarningsService for earnings call transcripts.
    benzinga_api_key:
        Benzinga key — used by AnalystService.
    unusual_whales_api_key:
        Unusual Whales key — used by OptionsFlowService.
    sec_api_key:
        sec-api.io key — used by FundamentalService.
    """

    def __init__(
        self,
        polygon_api_key: str,
        alphavantage_api_key: str,
        transcript_api_key: str,
        benzinga_api_key: str,
        unusual_whales_api_key: str,
        sec_api_key: str,
    ) -> None:
        self._polygon_key = polygon_api_key
        self._alphavantage_key = alphavantage_api_key
        self._transcript_key = transcript_api_key
        self._benzinga_key = benzinga_api_key
        self._unusual_whales_key = unusual_whales_api_key
        self._sec_key = sec_api_key

    async def compute_framework_score(self, ticker: str) -> FrameworkScoreResponse:
        """Compute the Framework Score for ``ticker`` asynchronously.

        All six concurrent tasks (F1-F5 + Brent price) are launched via
        ``asyncio.gather(return_exceptions=True)`` to ensure one failure
        does not cancel the others.
        """
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                self._fetch_f1(ticker, client),
                self._fetch_f2(ticker, client),
                self._fetch_f3(ticker),
                self._fetch_f4(ticker),
                self._fetch_f5(ticker),
                return_exceptions=True,
            )

        f1_result, f2_result, f3_result, f4_result, f5_result = results

        flags: list[str] = []

        # --- Extract factor scores with graceful fallback ---
        f1_score, f1_grade, f1_ok = self._extract_factor(
            f1_result, "f1_score", "f1_grade", "F1 Momentum", flags
        )
        f2_score, f2_grade, f2_ok = self._extract_factor(
            f2_result, "f2_score", "f2_grade", "F2 Earnings Quality", flags
        )
        f3_score, f3_grade, f3_ok = self._extract_factor(
            f3_result, "f3_score", "f3_grade", "F3 Analyst Sentiment", flags
        )
        f4_score, f4_grade, f4_ok = self._extract_factor(
            f4_result, "f4_score", "f4_grade", "F4 Options Flow", flags
        )
        f5_score, f5_grade, f5_ok = self._extract_factor(
            f5_result, "f5_score", "f5_grade", "F5 Fundamental Quality", flags
        )

        # --- F5 block detection ---
        f5_blocked = False
        if isinstance(f5_result, FundamentalResponse) and getattr(f5_result, "f5_blocked", False):
            f5_blocked = True
            flags.append("F5 HARD BLOCK: Altman Z-Score below 1.8 — no new capital.")

        # --- Assemble factor breakdowns ---
        factor_meta: list[tuple[str, str, int, float, str, bool]] = [
            ("f1", "Momentum", f1_score, _W_F1, f1_grade, f1_ok),
            ("f2", "Earnings Quality", f2_score, _W_F2, f2_grade, f2_ok),
            ("f3", "Analyst Sentiment", f3_score, _W_F3, f3_grade, f3_ok),
            ("f4", "Options Flow", f4_score, _W_F4, f4_grade, f4_ok),
            ("f5", "Fundamental Quality", f5_score, _W_F5, f5_grade, f5_ok),
        ]
        factors = [
            FactorBreakdown(
                key=key,
                name=name,
                score=score,
                weight=weight,
                contribution=round(score * weight, 4),
                grade=grade,
                available=available,
            )
            for key, name, score, weight, grade, available in factor_meta
        ]

        # --- Final calculation ---
        raw_total = round(_compute_raw_total(f1_score, f2_score, f3_score, f4_score, f5_score), 4)
        final_score = _compute_final_score(raw_total)
        action, action_tone = _map_action(final_score)

        return FrameworkScoreResponse(
            ticker=ticker.upper(),
            factors=factors,
            raw_total=raw_total,
            final_score=final_score,
            action=action,
            action_tone=action_tone,
            f5_blocked=f5_blocked,
            flags=flags,
        )

    # ------------------------------------------------------------------
    # Private — factor fetch wrappers
    # ------------------------------------------------------------------

    async def _fetch_f1(
        self,
        ticker: str,
        client: httpx.AsyncClient,
    ) -> MomentumResponse:
        """Fetch F1 Momentum score."""
        service = MomentumService(api_key=self._polygon_key, client=client)
        return await service.compute_momentum(ticker)

    async def _fetch_f2(
        self,
        ticker: str,
        client: httpx.AsyncClient,
    ) -> EarningsResponse:
        """Fetch F2 Earnings Quality score."""
        service = EarningsService(
            api_key=self._alphavantage_key,
            transcript_api_key=self._transcript_key,
            client=client,
        )
        return await service.compute_earnings(ticker)

    async def _fetch_f3(self, ticker: str) -> AnalystResponse:
        """Fetch F3 Analyst Sentiment score."""
        service = AnalystService(
            benzinga_api_key=self._benzinga_key,
            polygon_api_key=self._polygon_key,
        )
        return await service.compute_analyst(ticker)

    async def _fetch_f4(self, ticker: str) -> OptionsFlowResponse:
        """Fetch F4 Options Flow score."""
        service = OptionsFlowService(api_key=self._unusual_whales_key)
        return await service.compute_options_flow(ticker)

    async def _fetch_f5(self, ticker: str) -> FundamentalResponse:
        """Fetch F5 Fundamental Quality score."""
        service = FundamentalService(
            sec_api_key=self._sec_key,
            alphavantage_key=self._alphavantage_key,
        )
        return await service.compute_fundamental(ticker)

    # ------------------------------------------------------------------
    # Private — score extraction with fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_factor(
        result: object,
        score_field: str,
        grade_field: str,
        label: str,
        flags: list[str],
    ) -> tuple[int, str, bool]:
        """Extract (score, grade, available) from a factor result.

        On any failure returns (_NEUTRAL_SCORE, "NEUTRAL", False) and appends
        a descriptive flag.
        """
        if isinstance(result, Exception):
            flags.append(f"{label}: unavailable ({type(result).__name__}). Using neutral score.")
            return _NEUTRAL_SCORE, "NEUTRAL", False
        try:
            score = int(getattr(result, score_field))
            grade = str(getattr(result, grade_field))
            return score, grade, True
        except (AttributeError, TypeError, ValueError):
            flags.append(f"{label}: score extraction failed. Using neutral score.")
            return _NEUTRAL_SCORE, "NEUTRAL", False
