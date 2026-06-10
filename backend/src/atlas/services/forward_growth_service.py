"""Forward Growth Score (FGS) service — Phase 1.

Computes the two data-grounded FGS sub-factors (G1 revenue acceleration from
Alpha Vantage quarterly revenue, G5 TAM/bottleneck from the curated wave lookup)
and leaves G2 (backlog), G3 (customer quality) and G4 (product ramp) as optional
operator overrides defaulting to a neutral 50 (DATA_GAP).

When the caller supplies the live F5 (and ideally F4) scores, the F5 x FGS x F4
action matrix is evaluated to produce a bucket + plain-English action.
"""

from __future__ import annotations

from typing import Any, Final

import httpx

from atlas.core import forward_growth as fg
from atlas.schemas.forward_growth import (
    FgsSubFactor,
    ForwardGrowthResponse,
    RevenueAccelerationSubFactor,
    TamBottleneckSubFactor,
)
from atlas.services.provider_response_cache import fetch_alpha_vantage_cached

_TIMEOUT: Final[float] = 15.0


class ForwardGrowthService:
    """Computes the Forward Growth Score for a single ticker."""

    def __init__(self, alphavantage_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._av_key = alphavantage_key
        self._client = client

    async def compute_forward_growth(
        self,
        ticker: str,
        *,
        f5_score: int | None = None,
        f4_score: int | None = None,
        atlas_score: int | None = None,
        backlog_override: int | None = None,
        customer_quality_override: int | None = None,
        product_ramp_override: int | None = None,
    ) -> ForwardGrowthResponse:
        """Fetch revenue + assemble the FGS response (and action matrix)."""
        if self._client is not None:
            income = await self._fetch_income(self._client, ticker)
        else:
            async with httpx.AsyncClient() as client:
                income = await self._fetch_income(client, ticker)

        return self._build_response(
            ticker,
            income,
            f5_score=f5_score,
            f4_score=f4_score,
            atlas_score=atlas_score,
            backlog_override=backlog_override,
            customer_quality_override=customer_quality_override,
            product_ramp_override=product_ramp_override,
        )

    async def _fetch_income(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        """Fetch Alpha Vantage INCOME_STATEMENT (cached); {} on error/rate-limit."""
        if not self._av_key:
            return {}
        return await fetch_alpha_vantage_cached(
            client,
            api_key=self._av_key,
            function="INCOME_STATEMENT",
            symbol=ticker,
            timeout=_TIMEOUT,
        )

    @staticmethod
    def _build_response(
        ticker: str,
        income: dict[str, Any],
        *,
        f5_score: int | None,
        f4_score: int | None,
        atlas_score: int | None,
        backlog_override: int | None,
        customer_quality_override: int | None,
        product_ramp_override: int | None,
    ) -> ForwardGrowthResponse:
        symbol = ticker.upper()
        data_gaps: list[str] = []

        # --- G1 revenue acceleration (Alpha Vantage) ---
        revenues = _quarterly_revenues(income)
        g1_score, yoy_pct, accelerating = fg.score_revenue_acceleration(revenues)
        if g1_score is None:
            g1 = RevenueAccelerationSubFactor(
                score=fg.NEUTRAL_SCORE, source="DATA_GAP", yoy_pct=None, accelerating=None
            )
            data_gaps.append("REVENUE_ACCELERATION")
        else:
            g1 = RevenueAccelerationSubFactor(
                score=g1_score, source="alpha_vantage", yoy_pct=yoy_pct, accelerating=accelerating
            )

        # --- G2/G3/G4 optional operator overrides (default neutral / DATA_GAP) ---
        g2 = _override_subfactor(backlog_override, "BACKLOG_BOOKINGS", data_gaps)
        g3 = _override_subfactor(customer_quality_override, "CUSTOMER_QUALITY", data_gaps)
        g4 = _override_subfactor(product_ramp_override, "PRODUCT_RAMP", data_gaps)

        # --- G5 TAM / bottleneck (curated) ---
        g5_score, wave, status = fg.lookup_tam_bottleneck(symbol)
        if wave == "UNCLASSIFIED":
            data_gaps.append("TAM_BOTTLENECK")
        g5 = TamBottleneckSubFactor(
            score=g5_score,
            source="curated" if wave != "UNCLASSIFIED" else "DATA_GAP",
            wave=wave,
            status=status,
        )

        # Composite over instrumented sub-factors only (DATA_GAP excluded).
        subfactors = (g1, g2, g3, g4, g5)
        instrumented = [sf.score for sf in subfactors if sf.source != "DATA_GAP"]
        fgs = fg.compute_fgs(instrumented)
        grade = fg.fgs_grade(fgs)
        bucket, action = fg.classify_bucket(f5_score, fgs, f4_score)

        return ForwardGrowthResponse(
            ticker=symbol,
            fgs_score=fgs,
            fgs_grade=grade,
            confidence_pct=fg.confidence_pct(len(instrumented)),
            revenue_acceleration=g1,
            backlog_bookings=g2,
            customer_quality=g3,
            product_ramp=g4,
            tam_bottleneck=g5,
            f5_score=f5_score,
            f4_score=f4_score,
            atlas_score=atlas_score,
            bucket=bucket,
            action=action,
            data_gaps=data_gaps,
        )


def _override_subfactor(
    override: int | None, gap_key: str, data_gaps: list[str]
) -> FgsSubFactor:
    """Operator-override sub-factor; neutral 50 + DATA_GAP when not supplied."""
    if override is None:
        data_gaps.append(gap_key)
        return FgsSubFactor(score=fg.NEUTRAL_SCORE, source="DATA_GAP")
    return FgsSubFactor(score=max(0, min(100, override)), source="override")


def _quarterly_revenues(income: dict[str, Any]) -> list[float]:
    """Extract the quarterly totalRevenue series (newest first) from AV income data."""
    reports = income.get("quarterlyReports", []) if isinstance(income, dict) else []
    revenues: list[float] = []
    for rec in reports:
        raw = rec.get("totalRevenue") if isinstance(rec, dict) else None
        if raw is None or str(raw).strip().lower() in ("none", "", "-"):
            break  # series must be contiguous for YoY alignment
        try:
            revenues.append(float(raw))
        except (TypeError, ValueError):
            break
    return revenues
