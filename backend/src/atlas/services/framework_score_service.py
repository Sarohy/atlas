"""Framework Score service — aggregates F1-F5 into a single conviction score.

Formula (Factor_Mapping_Guide §Final Score):
  Raw Total   = (F1 x 0.15) + (F2 x 0.25) + (F3 x 0.15) + (F4 x 0.15) + (F5 x 0.30)
  Final Score = round(Raw Total), clamped [0, 100]

  Maximum raw total = 100 (all factors at 100, weights sum to 1.00).

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
from typing import Any, Final

import httpx

from atlas.core.scoring import classify_tier
from atlas.schemas.analyst import AnalystResponse
from atlas.schemas.earnings import EarningsResponse
from atlas.schemas.framework9 import Framework9Result
from atlas.schemas.framework_score import (
    FactorBreakdown,
    FrameworkScoreResponse,
)
from atlas.schemas.fundamental import FundamentalResponse
from atlas.schemas.momentum import MomentumResponse
from atlas.services.analyst_service import AnalystService
from atlas.services.earnings_service import EarningsService
from atlas.services.framework8_service import Framework8Service
from atlas.services.framework9_service import evaluate_framework9
from atlas.services.fundamental_service import FundamentalService
from atlas.services.momentum_service import MomentumService

logger = logging.getLogger(__name__)

# Staleness threshold for Framework 8 data (minutes).  If F8 reports
# data_age_minutes above this value the f8_stale flag is set in the response.
_F8_STALE_THRESHOLD_MINUTES: Final[int] = 30

# ---------------------------------------------------------------------------
# Framework-level weights (Factor_Mapping_Guide §Final Score)
# ---------------------------------------------------------------------------

# Each factor is scored 0-100; multiplied by its weight to contribute to the
# raw total.  Weights sum to 1.00 (maximum raw total = 100).
_W_F1: Final[float] = 0.15  # Momentum
_W_F2: Final[float] = 0.25  # Earnings Quality
_W_F3: Final[float] = 0.15  # Analyst Sentiment
_W_F4: Final[float] = 0.15  # Options Flow
_W_F5: Final[float] = 0.30  # Fundamental Quality

# Neutral fallback score when a factor service is unavailable.
_NEUTRAL_SCORE: Final[int] = 50


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no side effects
# ---------------------------------------------------------------------------


def _map_action(final_score: int) -> tuple[str, str]:
    """Map a final conviction score to (action_string, tone_class).

    Delegates to ``atlas.core.scoring.classify_tier`` — the single source
    of truth for v7.3.3 tier boundaries.

    Pure function — no I/O.
    """
    result = classify_tier(final_score)
    return result["action"], result["action_tone"]


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

        INCOME_STATEMENT and OVERVIEW are each used by two factor services
        (F2+F5 and F3+F5 respectively).  We create shared asyncio Tasks for
        them before the gather so both tasks start immediately; F2, F3, and F5
        await the same Task objects instead of making duplicate HTTP calls.
        Each Task executes the fetch exactly once regardless of how many
        services await it.
        """
        async with httpx.AsyncClient() as client:
            # Shared AV pre-fetches — started before the gather so they are
            # already in-flight when F2 / F3 / F5 coroutines begin.
            income_task: asyncio.Task[dict[str, Any]] = asyncio.create_task(
                self._fetch_av_raw(client, ticker, "INCOME_STATEMENT")
            )
            overview_task: asyncio.Task[dict[str, Any]] = asyncio.create_task(
                self._fetch_av_raw(client, ticker, "OVERVIEW")
            )

            f1_result, f2_result, f3_result, f4_result, f5_result, f8_data = await asyncio.gather(
                self._fetch_f1(ticker, client),
                self._fetch_f2(ticker, client, income_task),
                self._fetch_f3(ticker, overview_task),
                self._fetch_f4(ticker),
                self._fetch_f5(ticker, income_task, overview_task),
                self._fetch_f8(ticker),
                return_exceptions=True,
            )

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
        f5_raw_score = f5_score  # preserve pre-cap value for response metadata

        # --- Framework 8 insider cap (Rule 1-10 per Data Sync Rules) ---
        # F8 is fetched fresh in parallel above — never cached here.
        if isinstance(f8_data, Exception):
            f8_data = {
                "available": False,
                "flag_active": None,
                "f5_cap": None,
                "reason": repr(f8_data),
                "data_age_minutes": 0,
            }

        f8_available: bool = bool(f8_data.get("available", False))
        f8_flag_active: bool | None = f8_data.get("flag_active")
        f8_cap: int | None = f8_data.get("f5_cap")
        f8_data_age: int = int(f8_data.get("data_age_minutes", 0))
        f8_stale: bool = f8_available and f8_data_age > _F8_STALE_THRESHOLD_MINUTES
        f5_capped = False
        f5_cap_applied: int | None = None
        f5_cap_source: str | None = None

        if not f8_available:
            flags.append(
                f"Framework 8 unavailable — {f8_data.get('reason', 'unknown error')}. "
                "F5 cap could not be verified. Using raw F5 score. "
                "Verify insider flag manually before acting."
            )
        elif f8_stale:
            flags.append(
                f"Framework 8 data is {f8_data_age} minutes old. "
                "F5 cap value may be stale. Refresh recommended."
            )

        if f8_available and f8_flag_active is True and f8_cap is not None and f5_score > f8_cap:
            f5_capped = True
            f5_score = f8_cap
            f5_cap_applied = f8_cap
            f5_cap_source = f8_data.get("cap_reason", "Framework 8 insider flag active")
            flags.append(
                f"F5 capped at {f8_cap} by Framework 8 insider flag. Raw F5 was {f5_raw_score}."
            )

        # --- F5 block detection ---
        f5_blocked = False
        if isinstance(f5_result, FundamentalResponse) and getattr(f5_result, "f5_blocked", False):
            f5_blocked = True
            flags.append("F5 HARD BLOCK: Altman Z-Score below 1.8 — no new capital.")

        # --- Assemble factor breakdowns ---
        # available=False when either score extraction failed OR the underlying
        # data source reported data_available=False (the latter drives degraded=True).
        f2_data_ok = not (isinstance(f2_result, EarningsResponse) and not f2_result.data_available)
        f5_data_ok = not (
            isinstance(f5_result, FundamentalResponse) and not f5_result.data_available
        )

        factor_meta: list[tuple[str, str, int, float, str, bool]] = [
            ("f1", "Momentum", f1_score, _W_F1, f1_grade, f1_ok),
            ("f2", "Earnings Quality", f2_score, _W_F2, f2_grade, f2_ok and f2_data_ok),
            ("f3", "Analyst Sentiment", f3_score, _W_F3, f3_grade, f3_ok),
            ("f4", "Options Flow", f4_score, _W_F4, f4_grade, f4_ok),
            ("f5", "Fundamental Quality", f5_score, _W_F5, f5_grade, f5_ok and f5_data_ok),
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
            degraded=(
                (isinstance(f2_result, EarningsResponse) and not f2_result.data_available)
                or (isinstance(f5_result, FundamentalResponse) and not f5_result.data_available)
            ),
            f4_data_gap_badge=(
                f4_result.f1_propagation_badge
                if hasattr(f4_result, "f1_propagation_badge")
                else None
            ),
            f4_data_gap_message=(
                f4_result.f1_propagation_message
                if hasattr(f4_result, "f1_propagation_message")
                else None
            ),
            f4_data_gap_tooltip=(
                f4_result.f1_propagation_tooltip
                if hasattr(f4_result, "f1_propagation_tooltip")
                else None
            ),
            f5_raw_score=f5_raw_score,
            f5_capped=f5_capped,
            f5_cap_applied=f5_cap_applied,
            f5_cap_source=f5_cap_source,
            f8_available=f8_available,
            f8_flag_active=f8_flag_active,
            f8_stale=f8_stale,
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

    async def _fetch_av_raw(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        function: str,
    ) -> dict[str, Any]:
        """Fetch one Alpha Vantage endpoint; returns {} on rate-limit or error.

        Used to create shared Tasks so the same endpoint is never fetched more
        than once per framework-score request regardless of how many factor
        services need it.
        """
        try:
            resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": function,
                    "symbol": ticker.upper(),
                    "apikey": self._alphavantage_key,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            if "Note" in data or "Information" in data:
                logger.debug("AV %s rate-limited for %s (shared prefetch)", function, ticker)
                return {}
            return data
        except (httpx.HTTPStatusError, httpx.RequestError):
            return {}

    async def _fetch_f2(
        self,
        ticker: str,
        client: httpx.AsyncClient,
        income_task: asyncio.Task[dict[str, Any]],
    ) -> EarningsResponse:
        """Fetch F2 Earnings Quality score (shares pre-fetched INCOME_STATEMENT)."""
        service = EarningsService(
            api_key=self._alphavantage_key,
            transcript_api_key=self._transcript_key,
            polygon_api_key=self._polygon_key,
            client=client,
        )
        return await service.compute_earnings(ticker, income_task=income_task)

    async def _fetch_f3(
        self,
        ticker: str,
        overview_task: asyncio.Task[dict[str, Any]],
    ) -> AnalystResponse:
        """Fetch F3 Analyst Sentiment score (shares pre-fetched OVERVIEW)."""
        service = AnalystService(
            benzinga_api_key=self._benzinga_key,
            polygon_api_key=self._polygon_key,
            alphavantage_api_key=self._alphavantage_key,
            fmp_api_key=self._transcript_key,
        )
        return await service.compute_analyst(ticker, overview_task=overview_task)

    async def _fetch_f4(self, ticker: str) -> Framework9Result:
        """Fetch F4 Options Flow score via Framework 9.

        Framework 9 wraps OptionsFlowService and applies pre-earnings timing
        modifiers (-25% reduction or +10% Exceptional Conviction premium).
        Framework 1 must consume the *adjusted* score so timing risk is
        reflected in the final conviction score.
        """
        return await evaluate_framework9(
            ticker,
            uw_api_key=self._unusual_whales_key,
            polygon_api_key=self._polygon_key,
            av_api_key=self._alphavantage_key,
        )

    async def _fetch_f5(
        self,
        ticker: str,
        income_task: asyncio.Task[dict[str, Any]],
        overview_task: asyncio.Task[dict[str, Any]],
    ) -> FundamentalResponse:
        """Fetch F5 Fundamental Quality score (shares pre-fetched INCOME_STATEMENT + OVERVIEW)."""
        service = FundamentalService(
            sec_api_key=self._sec_key,
            alphavantage_key=self._alphavantage_key,
        )
        return await service.compute_fundamental(
            ticker, income_task=income_task, overview_task=overview_task
        )

    async def _fetch_f8(self, ticker: str) -> dict[str, Any]:
        """Fetch Framework 8 insider flag status for *ticker*.

        Called fresh on every evaluation — no caching of the cap value.
        On any failure returns a safe dict with available=False so the caller
        can surface a warning without blocking Framework 1 scoring.
        """
        try:
            service = Framework8Service(sec_api_key=self._sec_key)
            result = await service.compute(ticker)
            return {
                "available": True,
                "flag_active": result.flag_active,
                "f5_cap": result.f5_cap,
                "cap_reason": (
                    f"Framework 8 insider flag — "
                    f"largest sale ${(result.largest_sale_usd or 0) / 1_000_000:.1f}M "
                    f"(filer tier: {result.filer_tier})"
                ),
                "data_age_minutes": 0,
            }
        except Exception as exc:
            logger.warning(
                "Framework 8 fetch failed — F5 cap cannot be verified",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return {
                "available": False,
                "flag_active": None,
                "f5_cap": None,
                "reason": repr(exc),
                "data_age_minutes": 0,
            }

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
