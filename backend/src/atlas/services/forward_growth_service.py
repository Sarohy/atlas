"""Forward Growth Score (FGS) service — Phase 1 + transcript signals.

Computes the data-grounded FGS sub-factors:
  * G1 revenue acceleration — Alpha Vantage quarterly revenue,
  * G5 TAM/bottleneck       — curated wave lookup,
  * G2 backlog, G3 customer quality, G4 product ramp — heuristic keyword/regex
    extraction over the FMP earnings-call transcript we already fetch.

Precedence per sub-factor: operator override > transcript signal > DATA_GAP.
When the caller supplies the live F5 (and ideally F4) scores, the F5 x FGS x F4
action matrix is evaluated to produce a bucket + plain-English action.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Final

import httpx

from atlas.core import forward_growth as fg
from atlas.schemas.forward_growth import (
    FgsSubFactor,
    ForwardGrowthResponse,
    RevenueAccelerationSubFactor,
    TamBottleneckSubFactor,
)
from atlas.services import edgar_fundamentals as edgar
from atlas.services.edgar_fundamentals import CustomerConcentration
from atlas.services.provider_response_cache import fetch_alpha_vantage_cached

_TIMEOUT: Final[float] = 15.0
_FMP_TRANSCRIPT_URL: Final[str] = (
    "https://financialmodelingprep.com/stable/earning-call-transcript"
)
# How many quarter slots to probe back from "now" looking for a transcript.
_TRANSCRIPT_PROBE_SLOTS: Final[int] = 5


class ForwardGrowthService:
    """Computes the Forward Growth Score for a single ticker."""

    def __init__(
        self,
        alphavantage_key: str,
        transcript_api_key: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._av_key = alphavantage_key
        self._transcript_api_key = transcript_api_key
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
        """Fetch revenue + transcript + EDGAR and assemble the FGS response."""
        if self._client is not None:
            income, transcript, backlog_usd, concentration = await self._fetch_inputs(
                self._client, ticker
            )
        else:
            async with httpx.AsyncClient() as client:
                income, transcript, backlog_usd, concentration = await self._fetch_inputs(
                    client, ticker
                )

        return self._build_response(
            ticker,
            income,
            transcript,
            f5_score=f5_score,
            f4_score=f4_score,
            atlas_score=atlas_score,
            backlog_override=backlog_override,
            customer_quality_override=customer_quality_override,
            product_ramp_override=product_ramp_override,
            backlog_usd=backlog_usd,
            concentration=concentration,
        )

    async def _fetch_inputs(
        self, client: httpx.AsyncClient, ticker: str
    ) -> tuple[dict[str, Any], str, float | None, CustomerConcentration | None]:
        """Fetch income, transcript, and EDGAR (backlog + concentration) concurrently."""
        income, transcript, edgar_data = await asyncio.gather(
            self._fetch_income(client, ticker),
            self._fetch_transcript(client, ticker),
            self._fetch_edgar(client, ticker),
        )
        backlog_usd, concentration = edgar_data
        return income, transcript, backlog_usd, concentration

    @staticmethod
    async def _fetch_edgar(
        client: httpx.AsyncClient, ticker: str
    ) -> tuple[float | None, CustomerConcentration | None]:
        """Resolve CIK, then fetch backlog (RPO) + customer concentration from EDGAR."""
        cik = await edgar.resolve_cik(client, ticker)
        if cik is None:
            return None, None
        backlog_usd, concentration = await asyncio.gather(
            edgar.fetch_backlog_usd(client, cik),
            edgar.fetch_customer_concentration(client, cik),
        )
        return backlog_usd, concentration

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

    async def _fetch_transcript(self, client: httpx.AsyncClient, ticker: str) -> str:
        """Return the most recent FMP earnings-call transcript text, or "".

        FMP indexes transcripts by calendar year/quarter; we probe back a few
        quarter slots from "now" and return the first non-empty content.
        """
        if not self._transcript_api_key:
            return ""

        today = date.today()
        year, quarter = today.year, (today.month - 1) // 3 + 1
        slots: list[tuple[int, int]] = []
        for _ in range(_TRANSCRIPT_PROBE_SLOTS):
            slots.append((year, quarter))
            year, quarter = (year - 1, 4) if quarter == 1 else (year, quarter - 1)

        for slot_year, slot_quarter in slots:
            try:
                resp = await client.get(
                    _FMP_TRANSCRIPT_URL,
                    params={
                        "symbol": ticker,
                        "year": slot_year,
                        "quarter": slot_quarter,
                        "apikey": self._transcript_api_key,
                    },
                    timeout=20.0,
                )
                resp.raise_for_status()
                raw = resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
                continue
            if isinstance(raw, list) and raw and isinstance(raw[0], dict):
                content = raw[0].get("content")
                if content:
                    return str(content)
        return ""

    @staticmethod
    def _build_response(
        ticker: str,
        income: dict[str, Any],
        transcript: str,
        *,
        f5_score: int | None,
        f4_score: int | None,
        atlas_score: int | None,
        backlog_override: int | None,
        customer_quality_override: int | None,
        product_ramp_override: int | None,
        backlog_usd: float | None = None,
        concentration: CustomerConcentration | None = None,
    ) -> ForwardGrowthResponse:
        symbol = ticker.upper()
        data_gaps: list[str] = []

        # --- G1 revenue acceleration (Alpha Vantage) ---
        revenues = _quarterly_revenues(income)
        ttm_revenue = sum(revenues[:4]) if len(revenues) >= 4 else None
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

        # --- G2 backlog: override > EDGAR RPO ($ coverage) > transcript > DATA_GAP ---
        g2 = _resolve_subfactor(
            backlog_override,
            [
                (fg.score_backlog_from_rpo(backlog_usd, ttm_revenue), "edgar"),
                (fg.score_backlog_signal(transcript), "transcript"),
            ],
            "BACKLOG_BOOKINGS",
            data_gaps,
        )

        # --- G3 customer quality: override > transcript; capped by concentration ---
        largest_pct = concentration.largest_customer_pct if concentration else None
        g3 = _resolve_subfactor(
            customer_quality_override,
            [(fg.score_customer_quality_signal(transcript), "transcript")],
            "CUSTOMER_QUALITY",
            data_gaps,
        )
        cap = fg.concentration_quality_cap(largest_pct)
        if cap is not None and g3.source not in ("DATA_GAP", "override"):
            g3 = g3.model_copy(update={"score": min(g3.score, cap)})

        # --- G4 product ramp: override > transcript > DATA_GAP ---
        g4 = _resolve_subfactor(
            product_ramp_override,
            [(fg.score_product_ramp_signal(transcript), "transcript")],
            "PRODUCT_RAMP",
            data_gaps,
        )

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
            backlog_usd=round(backlog_usd, 2) if backlog_usd is not None else None,
            customer_concentration_pct=largest_pct,
            customers_over_10pct=(concentration.customers_over_10pct if concentration else None),
            customer_concentration_summary=(concentration.summary if concentration else None),
            f5_score=f5_score,
            f4_score=f4_score,
            atlas_score=atlas_score,
            bucket=bucket,
            action=action,
            data_gaps=data_gaps,
        )


def _resolve_subfactor(
    override: int | None,
    candidates: list[tuple[int | None, str]],
    gap_key: str,
    data_gaps: list[str],
) -> FgsSubFactor:
    """Resolve a sub-factor by precedence: override > ordered candidates > DATA_GAP.

    ``candidates`` is an ordered list of ``(score_or_None, source)`` — the first
    with a non-None score wins (e.g. EDGAR before transcript). When nothing is
    available it falls back to a neutral 50 (DATA_GAP), excluded from the
    composite.
    """
    if override is not None:
        return FgsSubFactor(score=max(0, min(100, override)), source="override")
    for score, source in candidates:
        if score is not None:
            return FgsSubFactor(score=score, source=source)
    data_gaps.append(gap_key)
    return FgsSubFactor(score=fg.NEUTRAL_SCORE, source="DATA_GAP")


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
