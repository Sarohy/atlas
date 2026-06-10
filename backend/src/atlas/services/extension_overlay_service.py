"""ATLAS Overbought / Extension Overlay service.

Fetches a single ticker's daily bars from Polygon (plus IV rank from Unusual
Whales when a key is configured) and runs the pure extension engine
(atlas.core.extension) to produce the Extension Risk Score, flag, and action
recommendation.  All scoring logic lives in the pure core; this service only
owns the I/O and response assembly.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Final

import httpx

from atlas.core import extension as ext
from atlas.schemas.extension_overlay import ExtensionOverlayResponse

# 380 calendar days ≈ 265 trading sessions — enough for the 200-day MA plus the
# trailing windows even accounting for holidays.
_LOOKBACK_DAYS: Final[int] = 380
_POLYGON_AGGS_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
)
# Unusual Whales IV-rank endpoint. Returns {"data": [{"date", "iv_rank_1y", ...}]}
# — a list of daily records; the latest record's ``iv_rank_1y`` is the 1-year IV
# rank already expressed on a 0-100 scale.
_UW_IV_RANK_URL: Final[str] = "https://api.unusualwhales.com/api/stock/{ticker}/iv-rank"
_TIMEOUT: Final[float] = 15.0


class ExtensionOverlayService:
    """Computes the Extension Overlay for a single ticker from Polygon bars."""

    def __init__(
        self,
        api_key: str,
        uw_api_key: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._uw_api_key = uw_api_key
        self._client = client

    async def compute_overlay(
        self, ticker: str, atlas_score: int | None = None
    ) -> ExtensionOverlayResponse:
        """Fetch bars + IV rank and assemble the Extension Overlay response."""
        if self._client is not None:
            bars, iv_rank = await self._fetch_inputs(self._client, ticker)
        else:
            async with httpx.AsyncClient() as client:
                bars, iv_rank = await self._fetch_inputs(client, ticker)

        return self._build_response(ticker, bars, atlas_score, iv_rank)

    async def _fetch_inputs(
        self, client: httpx.AsyncClient, ticker: str
    ) -> tuple[list[dict[str, Any]], float | None]:
        """Fetch Polygon bars and (when a UW key is set) IV rank concurrently.

        IV rank comes from Unusual Whales as a 0-1 fraction (shared with the
        LEAPS module); it is rescaled to the 0-100 convention the extension
        engine expects.  Returns ``(bars, iv_rank_0_100_or_None)``.
        """
        if not self._uw_api_key:
            return await self._fetch_bars(client, ticker), None

        bars, iv_rank = await asyncio.gather(
            self._fetch_bars(client, ticker),
            self._fetch_iv_rank(client, ticker),
        )
        return bars, iv_rank

    async def _fetch_iv_rank(
        self, client: httpx.AsyncClient, ticker: str
    ) -> float | None:
        """Return the latest 1-year IV rank (0-100) from Unusual Whales, or None.

        UW returns ``{"data": [{"date", "iv_rank_1y", ...}, ...]}`` ascending by
        date; the last record holds the most recent ``iv_rank_1y`` (already on a
        0-100 scale).  Any error or unexpected shape degrades to None.
        """
        try:
            resp = await client.get(
                _UW_IV_RANK_URL.format(ticker=ticker.upper()),
                headers={
                    "Authorization": f"Bearer {self._uw_api_key}",
                    "Accept": "application/json",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None

        payload = resp.json()
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            return None
        latest = rows[-1]
        raw = latest.get("iv_rank_1y") if isinstance(latest, dict) else None
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    async def _fetch_bars(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[dict[str, Any]]:
        """Return ascending daily OHLCV bars from Polygon; [] on any error."""
        to_date = date.today()
        from_date = to_date - timedelta(days=_LOOKBACK_DAYS)
        url = _POLYGON_AGGS_URL.format(
            ticker=ticker,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
        )
        try:
            resp = await client.get(
                url,
                params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": "500",
                    "apiKey": self._api_key,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return []
        payload: dict[str, Any] = resp.json()
        return payload.get("results", []) or []

    @staticmethod
    def _build_response(
        ticker: str,
        bars: list[dict[str, Any]],
        atlas_score: int | None,
        iv_rank: float | None = None,
    ) -> ExtensionOverlayResponse:
        symbol = ticker.upper()
        data_gaps: list[str] = []
        if iv_rank is None:
            data_gaps.append("IV_RANK")

        # All metrics default to None and are filled in when enough bars exist.
        rsi14 = rsi7 = move14 = move21 = None
        above20 = above50 = above200 = gap = week52 = None
        vwap = vs_vwap = None

        closes = [float(b["c"]) for b in bars if b.get("c") is not None]
        if not closes:
            data_gaps.append("PRICE_BARS")
        else:
            price = closes[-1]
            rsi14 = ext.compute_rsi(closes, 14)
            rsi7 = ext.compute_rsi(closes, 7)
            move14 = ext.pct_move(closes, 14)
            move21 = ext.pct_move(closes, 21)
            above20 = ext.pct_above_ma(price, ext.simple_ma(closes, 20))
            above50 = ext.pct_above_ma(price, ext.simple_ma(closes, 50))
            ma200 = ext.simple_ma(closes, 200)
            above200 = ext.pct_above_ma(price, ma200)

            # Today's gap = latest bar open vs prior bar close.
            if len(bars) >= 2:
                today_open = bars[-1].get("o")
                prev_close = bars[-2].get("c")
                gap = ext.gap_pct(
                    float(today_open) if today_open is not None else None,
                    float(prev_close) if prev_close is not None else None,
                )

            # Daily VWAP — Polygon supplies `vw` on every aggregate bar. This is
            # the session VWAP, not the intraday running VWAP.
            latest_vw = bars[-1].get("vw")
            if latest_vw is not None:
                vwap = float(latest_vw)
                vs_vwap = ext.pct_above_ma(price, vwap)
            else:
                data_gaps.append("VWAP")

            if len(closes) >= 252:
                window = closes[-252:]
                hi, lo = max(window), min(window)
                week52 = 50.0 if hi == lo else (price - lo) / (hi - lo) * 100.0

            if ma200 is None:
                data_gaps.append("MA_200")

        risk = ext.extension_risk_score(
            rsi14=rsi14,
            rsi7=rsi7,
            move14_pct=move14,
            move21_pct=move21,
            pct_above_20dma=above20,
            pct_above_50dma=above50,
            pct_above_200dma=above200,
            gap_today_pct=gap,
            iv_rank=iv_rank,
        )
        flag = ext.classify_extension_flag(risk)
        action, detail = ext.recommend_action(atlas_score, flag)

        def _round(value: float | None) -> float | None:
            return round(value, 2) if value is not None else None

        return ExtensionOverlayResponse(
            ticker=symbol,
            rsi_14=_round(rsi14),
            rsi_7=_round(rsi7),
            move_14d_pct=_round(move14),
            move_21d_pct=_round(move21),
            pct_above_20dma=_round(above20),
            pct_above_50dma=_round(above50),
            pct_above_200dma=_round(above200),
            week_52_position_pct=_round(week52),
            gap_today_pct=_round(gap),
            vwap=_round(vwap),
            pct_vs_vwap=_round(vs_vwap),
            iv_rank=_round(iv_rank),
            extension_risk_score=risk,
            extension_flag=flag,
            atlas_score=atlas_score,
            action=action,
            action_detail=detail,
            data_gaps=data_gaps,
        )
