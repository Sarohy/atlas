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

from atlas.core import elliott as ell
from atlas.core import extension as ext
from atlas.core import gann
from atlas.schemas.extension_overlay import ExtensionOverlayResponse

# 380 calendar days ≈ 265 trading sessions — enough for the 200-day MA plus the
# trailing windows even accounting for holidays.
_LOOKBACK_DAYS: Final[int] = 380
# Long window for the all-time-high lookup — ~25 years, capped by whatever history
# the Polygon plan returns. The ATH is the max split-adjusted high over that range.
_ATH_LOOKBACK_DAYS: Final[int] = 9200
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
        """Fetch bars + IV rank + ATH and assemble the Extension Overlay response."""
        if self._client is not None:
            bars, iv_rank, ath, ath_date = await self._fetch_inputs(self._client, ticker)
        else:
            async with httpx.AsyncClient() as client:
                bars, iv_rank, ath, ath_date = await self._fetch_inputs(client, ticker)

        return self._build_response(ticker, bars, atlas_score, iv_rank, ath, ath_date)

    async def _fetch_inputs(
        self, client: httpx.AsyncClient, ticker: str
    ) -> tuple[list[dict[str, Any]], float | None, float | None, str | None]:
        """Fetch Polygon bars, the all-time high, and (with a UW key) IV rank.

        All fetches run concurrently. IV rank comes from Unusual Whales already
        on a 0-100 scale. Returns ``(bars, iv_rank, ath_high, ath_date)``.
        """
        bars_task = self._fetch_bars(client, ticker)
        ath_task = self._fetch_ath(client, ticker)
        if self._uw_api_key:
            bars, iv_rank, (ath, ath_date) = await asyncio.gather(
                bars_task, self._fetch_iv_rank(client, ticker), ath_task
            )
            return bars, iv_rank, ath, ath_date
        bars, (ath, ath_date) = await asyncio.gather(bars_task, ath_task)
        return bars, None, ath, ath_date

    async def _fetch_ath(
        self, client: httpx.AsyncClient, ticker: str
    ) -> tuple[float | None, str | None]:
        """Return ``(all_time_high, ath_date)`` from the max split-adjusted daily
        high over the long window (best-effort, capped by available history)."""
        to_date = date.today()
        from_date = to_date - timedelta(days=_ATH_LOOKBACK_DAYS)
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
                    "limit": "50000",
                    "apiKey": self._api_key,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return None, None

        payload: dict[str, Any] = resp.json()
        results = payload.get("results", []) or []
        best_high: float | None = None
        best_ts: int | None = None
        for bar in results:
            high = bar.get("h")
            if high is None:
                continue
            high = float(high)
            if best_high is None or high > best_high:
                best_high, best_ts = high, bar.get("t")
        if best_high is None:
            return None, None
        ath_date = date.fromtimestamp(best_ts / 1000).isoformat() if best_ts else None
        return best_high, ath_date

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
        ath: float | None = None,
        ath_date: str | None = None,
    ) -> ExtensionOverlayResponse:
        symbol = ticker.upper()
        data_gaps: list[str] = []
        if iv_rank is None:
            data_gaps.append("IV_RANK")
        if ath is None:
            data_gaps.append("ATH")

        # All metrics default to None and are filled in when enough bars exist.
        rsi14 = rsi7 = move14 = move21 = None
        above20 = above50 = above200 = gap = week52 = None
        vwap = vs_vwap = pct_from_ath = None
        td = ext.TdSequential(0, None, 0, None)
        rsi_divergence = macd_cross = False
        elliott = ell.ElliottResult(None, None, False, False, None, 0, 0)
        gann_res = gann.GannResult(None, None, False, False, None, None, None)

        ohlc = [
            b
            for b in bars
            if b.get("c") is not None and b.get("h") is not None and b.get("l") is not None
        ]
        closes = [float(b["c"]) for b in ohlc]
        highs = [float(b["h"]) for b in ohlc]
        lows = [float(b["l"]) for b in ohlc]
        if not closes:
            data_gaps.append("PRICE_BARS")
        else:
            price = closes[-1]

            # Deterministic technical sell/exhaustion signals.
            td = ext.td_sequential(highs, closes)
            rsi_divergence = ext.detect_rsi_bearish_divergence(closes, ext.rsi_series(closes, 14))
            macd_cross = ext.macd_bearish_cross(closes)
            # Rule-based Elliott Wave + Gann (informational/contextual — these do
            # NOT feed the calibrated extension risk score).
            elliott = ell.label_impulse(highs, lows)
            gann_res = gann.analyze_gann(highs, lows, closes)

            # Distance from the all-time high (negative = below ATH = dipped).
            if ath is not None and ath > 0:
                pct_from_ath = (price - ath) / ath * 100.0
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
            td_sell_signal=td.signal,
            rsi_bearish_divergence=rsi_divergence,
            macd_bearish_cross=macd_cross,
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
            ath=_round(ath),
            ath_date=ath_date,
            pct_from_ath=_round(pct_from_ath),
            iv_rank=_round(iv_rank),
            td_setup=td.setup_count or None,
            td_setup_direction=td.setup_direction,
            td_countdown=td.sell_countdown or None,
            td_signal=td.signal,
            rsi_bearish_divergence=rsi_divergence,
            macd_bearish_cross=macd_cross,
            elliott_wave=elliott.current_wave,
            elliott_direction=elliott.direction,
            elliott_signal=elliott.signal,
            elliott_confidence=elliott.confidence or None,
            gann_signal=gann_res.signal,
            gann_below_1x1=gann_res.below_1x1,
            gann_time_cycle_due=gann_res.time_cycle_due,
            gann_nearest_support=gann_res.nearest_support,
            gann_nearest_resistance=gann_res.nearest_resistance,
            extension_risk_score=risk,
            extension_flag=flag,
            atlas_score=atlas_score,
            action=action,
            action_detail=detail,
            data_gaps=data_gaps,
        )
