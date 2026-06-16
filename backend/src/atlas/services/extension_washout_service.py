"""Extension & Washout Overlay service (Spec v2).

Assembles the measured inputs for the pure ``atlas.core.extension_washout``
engine and returns the nine-state posture. Reads price/flow only; writes nothing
into the F1-F5 score path (hard separation, Edit 1).

Data:
  * Polygon daily bars        — 50d distance, RSI/moves, MA20/50, daily VWAP.
  * Unusual Whales dark pool   — latest-session sell% / net (reactive confirm §6,
    absorption §4).
  * Polygon grouped-daily      — book-level breadth scan over the 32-name complex
    (§5), cached book-wide.
"""

from __future__ import annotations

import asyncio
from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final

import httpx

from atlas.core import extension as ext
from atlas.core import extension_washout as ew
from atlas.core import overshoot_elasticity as oe
from atlas.schemas.extension_washout import (
    ExtensionWashoutResponse,
    MetricLegsOut,
    RiskExceptionRow,
    ThresholdRow,
    WashoutReferenceResponse,
)
from atlas.services.options_flow_service import (
    _classify_dark_pool_print,
    _fetch_dark_pool_prints,
    _group_by_session,
    _print_premium_usd,
    _safe_float,
)

_TIMEOUT: Final[float] = 15.0
_LOOKBACK_DAYS: Final[int] = 380
_POLYGON_AGGS_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
)
_POLYGON_GROUPED_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date}"
)

# Default 32-name complex for the breadth monitor (§5). Editable.
_BREADTH_UNIVERSE: Final[tuple[str, ...]] = (
    "MU", "MRVL", "BE", "CLS", "NBIS", "CRWV", "AVGO", "CRDO",
    "SNDK", "LITE", "AAOI", "COHR", "ARM", "MXL", "ONTO", "TSEM",
    "AMD", "VICR", "NVDA", "TSM", "CIEN", "FN", "VRT", "AEHR",
    "UCTT", "TTMI", "ICHR", "GEV", "CEG", "ANET", "SMCI", "ALAB",
)

# Position-size gate defaults (§3.1) — % NAV. Target = §13/§15 soft cap.
_TARGET_PCT: Final[float] = 8.0
_STARTER_PCT: Final[float] = 2.0

# Elasticity-enhancement sources not yet wired into the elasticity score —
# surfaced as DATA_GAP for transparency (SPEC v2.1 amendment requirement).
_ELASTICITY_DATA_GAPS: Final[tuple[str, ...]] = (
    "SHORT_INTEREST", "FLOAT", "OPTIONS", "DP", "F4", "FLOW_MONITOR",
)

# Book-level breadth cache (shared across single-name requests). 5-min TTL.
_BREADTH_TTL: Final[timedelta] = timedelta(minutes=5)
_breadth_cache: dict[str, tuple[datetime, tuple[int, int, int]]] = {}


class ExtensionWashoutService:
    """Computes the Extension & Washout Overlay posture for a single ticker."""

    def __init__(
        self,
        api_key: str,
        uw_api_key: str = "",
        client: httpx.AsyncClient | None = None,
        cfg: ew.WashoutConfig = ew.DEFAULT_CONFIG,
    ) -> None:
        self._api_key = api_key
        self._uw_api_key = uw_api_key
        self._client = client
        self._cfg = cfg

    async def compute(
        self,
        ticker: str,
        *,
        position_weight_pct: float | None = None,
        negative_catalyst: bool = False,
        beta: float | None = None,
    ) -> ExtensionWashoutResponse:
        if self._client is not None:
            return await self._compute(
                self._client, ticker, position_weight_pct, negative_catalyst, beta
            )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            return await self._compute(
                client, ticker, position_weight_pct, negative_catalyst, beta
            )

    async def _compute(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        position_weight_pct: float | None,
        negative_catalyst: bool,
        beta: float | None,
    ) -> ExtensionWashoutResponse:
        bars, dp_prints, breadth_counts = await asyncio.gather(
            self._fetch_bars(client, ticker),
            self._fetch_dark_pool(client, ticker),
            self._breadth_counts(client),
        )
        return self._build(
            ticker=ticker,
            bars=bars,
            dp_prints=dp_prints,
            breadth_counts=breadth_counts,
            position_weight_pct=position_weight_pct,
            negative_catalyst=negative_catalyst,
            beta=beta,
        )

    # ------------------------------------------------------------------
    # Network I/O
    # ------------------------------------------------------------------

    async def _fetch_bars(self, client: httpx.AsyncClient, ticker: str) -> list[dict[str, Any]]:
        to_date = date.today()
        from_date = to_date - timedelta(days=_LOOKBACK_DAYS)
        url = _POLYGON_AGGS_URL.format(
            ticker=ticker, from_date=from_date.isoformat(), to_date=to_date.isoformat()
        )
        try:
            resp = await client.get(
                url,
                params={"adjusted": "true", "sort": "asc", "limit": "500", "apiKey": self._api_key},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return []
        payload: dict[str, Any] = resp.json()
        return payload.get("results", []) or []

    async def _fetch_dark_pool(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[dict[str, Any]] | None:
        if not self._uw_api_key:
            return None
        headers = {"Authorization": f"Bearer {self._uw_api_key}", "Accept": "application/json"}
        return await _fetch_dark_pool_prints(client, ticker, headers)

    async def _breadth_counts(self, client: httpx.AsyncClient) -> tuple[int, int, int]:
        """Return (watch_count, hedge_count, universe_size) for the complex (§5).

        Cached book-wide (5 min) since breadth is a single book-level signal.
        """
        cached = _breadth_cache.get("BREADTH")
        if cached is not None and datetime.now(UTC) - cached[0] < _BREADTH_TTL:
            return cached[1]

        closes_by_day = await self._fetch_grouped_closes(client, days=3)
        counts = _compute_breadth(closes_by_day, _BREADTH_UNIVERSE, self._cfg)
        _breadth_cache["BREADTH"] = (datetime.now(UTC), counts)
        return counts

    async def _fetch_grouped_closes(
        self, client: httpx.AsyncClient, *, days: int
    ) -> list[dict[str, float]]:
        """Fetch the most recent ``days`` trading sessions of grouped daily closes.

        Returns a list (newest first) of {ticker: close} maps. Walks back over
        calendar days, skipping non-trading days (empty responses).
        """
        out: list[dict[str, float]] = []
        probe = date.today()
        for _ in range(days + 6):  # allow for weekends/holidays
            if len(out) >= days:
                break
            url = _POLYGON_GROUPED_URL.format(date=probe.isoformat())
            try:
                resp = await client.get(
                    url, params={"adjusted": "true", "apiKey": self._api_key}, timeout=_TIMEOUT
                )
                resp.raise_for_status()
                results = resp.json().get("results", []) or []
            except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
                results = []
            if results:
                out.append(
                    {
                        str(r["T"]): float(r["c"])
                        for r in results
                        if r.get("T") and r.get("c") is not None
                    }
                )
            probe -= timedelta(days=1)
        return out

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------

    def _build(
        self,
        *,
        ticker: str,
        bars: list[dict[str, Any]],
        dp_prints: list[dict[str, Any]] | None,
        breadth_counts: tuple[int, int, int],
        position_weight_pct: float | None,
        negative_catalyst: bool,
        beta: float | None = None,
    ) -> ExtensionWashoutResponse:
        cfg = self._cfg
        symbol = ticker.upper()
        data_gaps: list[str] = []

        closes = [float(b["c"]) for b in bars if b.get("c") is not None]
        dist_50d = rsi14 = move21 = move14 = move20 = None
        rv20 = rv60 = None
        vwap_lost = hard_override = False
        if not closes:
            data_gaps.append("PRICE_BARS")
        else:
            price = closes[-1]
            ma50 = ext.simple_ma(closes, 50)
            ma20 = ext.simple_ma(closes, 20)
            dist_50d = ext.pct_above_ma(price, ma50)
            rsi14 = ext.compute_rsi(closes, 14)
            move21 = ext.pct_move(closes, 21)
            move14 = ext.pct_move(closes, 14)
            move20 = ext.pct_move(closes, 20)
            rv20 = _realized_vol(closes, 20)
            rv60 = _realized_vol(closes, 60)
            # VWAP loss only counts as a confirmation leg when the name is
            # actually extended (>= Stop-Add line). A close below VWAP on an
            # ordinary red day is not a washout-trim signal on a non-extended
            # name — this prevents the 2-of-N gate from over-firing.
            vw = bars[-1].get("vw")
            if vw is not None and dist_50d is not None and dist_50d >= cfg.stop_add_50d:
                vwap_lost = price < float(vw)
            # Hard override (§7): confirmed close BACK below 20d/50d — a reversal,
            # not a routine pullback. The 20d break only counts when the name is
            # (or was just) extended (>= Stop-Add); a close back below the 50d is
            # always a structural break. Prevents firing on every name below its
            # 20d MA.
            ext_now = dist_50d is not None and dist_50d >= cfg.stop_add_50d
            broke_20d = ma20 is not None and price < ma20 and ext_now
            broke_50d = ma50 is not None and price < ma50
            hard_override = broke_20d or broke_50d

        # Dark-pool: latest-session sell% + net (reactive confirm §6, absorption §4).
        dp_sell_pct, dp_net = _latest_session_dp_stats(dp_prints)
        if dp_prints is None:
            data_gaps.append("DARK_POOL")

        down_day = len(closes) >= 2 and closes[-1] < closes[-2]
        flow_distribution = (
            dp_sell_pct is not None and dp_sell_pct >= cfg.reactive_dp_sell_pct and down_day
        )

        legs = ew.metric_legs(
            rsi14=rsi14, move21=move21, move14=move14, move20=move20, dist_50d=dist_50d, cfg=cfg
        )
        # Absorption (§4): extreme extension + aggressive DP buying + no follow-through.
        absorption = (
            bool(legs.extreme)
            and dp_net is not None
            and dp_net > 0
            and down_day
        )

        watch_count, hedge_count, universe_size = breadth_counts
        breadth = ew.breadth_level(
            count_down_watch=watch_count, count_down_hedge=hedge_count, cfg=cfg
        )
        group_rolling = breadth is not None

        # Position size gate (§3.1).
        below_target: bool | None = None
        at_or_above_target = False
        if position_weight_pct is not None:
            below_target = position_weight_pct < _TARGET_PCT
            at_or_above_target = position_weight_pct >= _TARGET_PCT

        confirmation = ew.ConfirmationLegs(
            flow_distribution=flow_distribution,
            vwap_lost=vwap_lost,
            group_rolling=group_rolling,
            absorption=absorption,
        )

        # --- Overshoot Elasticity (SPEC v2.1) — tunes ladder spacing only ---
        meta = ew.name_meta(symbol)
        elasticity = oe.compute_elasticity(
            symbol,
            oe.ElasticityInputs(rv20=rv20, rv60=rv60, beta=beta, mom21=move21),
            peak_50d=meta.peak_50d,
            event_count=meta.washout_count,
            extra_data_gaps=list(_ELASTICITY_DATA_GAPS),
        )
        # Elasticity ONLY adjusts trim-rung spacing (the arm/active/forced lines).
        # Track, the 9-state precedence, and the §3.1 size gate are untouched.
        arm, active, forced = elasticity.ladder
        adj_cfg = replace(
            cfg,
            arm_protection_50d=arm,
            active_protection_50d=active,
            forced_derisk_50d=forced,
        )

        inp = ew.WashoutInputs(
            ticker=symbol,
            dist_50d=dist_50d,
            rsi14=rsi14,
            move21=move21,
            move14=move14,
            move20=move20,
            below_target=below_target,
            at_or_above_target=at_or_above_target,
            confirmation=confirmation,
            negative_catalyst=negative_catalyst,
            hard_override=hard_override,
            absorption=absorption,
            breadth=breadth,
            data_ok=bool(closes),
        )
        result = ew.resolve_overlay(inp, adj_cfg)

        def _round(v: float | None) -> float | None:
            return round(v, 2) if v is not None else None

        return ExtensionWashoutResponse(
            ticker=symbol,
            state=result.state,
            reason=result.reason,
            rung=result.rung,
            track=result.track,
            overshoot=result.overshoot,
            low_confidence=result.low_confidence,
            trim_authorized=result.trim_authorized,
            size_relabeled=result.size_relabeled,
            confirmation_count=result.confirmation_count,
            confirmation_present=result.confirmation_present,
            flow_distribution=flow_distribution,
            vwap_lost=vwap_lost,
            group_rolling=group_rolling,
            absorption=absorption,
            hard_override=hard_override,
            negative_catalyst=negative_catalyst,
            dist_50d=_round(dist_50d),
            rsi_14=_round(rsi14),
            move_21d_pct=_round(move21),
            move_14d_pct=_round(move14),
            move_20d_pct=_round(move20),
            dark_pool_sell_pct=_round(dp_sell_pct),
            metric_legs=MetricLegsOut(moderate=result.metric_legs.moderate,
                                      extreme=result.metric_legs.extreme),
            position_weight_pct=position_weight_pct,
            target_pct=_TARGET_PCT,
            below_target=below_target,
            breadth=breadth,
            breadth_watch_count=watch_count,
            breadth_hedge_count=hedge_count,
            breadth_universe_size=universe_size,
            # --- Overshoot Elasticity (SPEC v2.1) ---
            elasticity_tier=elasticity.tier,
            elasticity_score=elasticity.score,
            elasticity_confidence=elasticity.confidence,
            elasticity_event_count=elasticity.event_count,
            plus40_state=elasticity.plus40_state,
            plus40_behavior=elasticity.plus40_label,
            elasticity_ladder=list(elasticity.ladder),
            sizing_guidance=elasticity.sizing_guidance,
            elasticity_provisional=elasticity.provisional,
            elasticity_watch_promote=elasticity.watch_promote,
            elasticity_excluded_from_recalibration=elasticity.exclude_recalibration,
            elasticity_hard_override=elasticity.hard_override,
            rv20=_round(rv20),
            rv60=_round(rv60),
            beta=_round(beta),
            elasticity_data_gaps=elasticity.data_gaps,
            data_gaps=data_gaps,
        )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _washout_threshold_group(name: str) -> str:
    if name.startswith("breadth"):
        return "Breadth (§5)"
    if name.startswith(("mod_", "ext_", "reactive", "sell_")):
        return "Confirmation (§7/§10)"
    return "Ladder (§3)"


def build_reference() -> WashoutReferenceResponse:
    """Settings thresholds (§10) + Risk exception rows (per-name overrides).

    Read-only reference for the Settings + Risk views. All values are the editable
    config defaults; per the spec they are provisional / quarterly-recompute.
    """
    thresholds: list[ThresholdRow] = []
    for f in fields(ew.DEFAULT_CONFIG):
        thresholds.append(
            ThresholdRow(
                key=f.name,
                value=str(getattr(ew.DEFAULT_CONFIG, f.name)),
                group=_washout_threshold_group(f.name),
            )
        )
    for f in fields(oe.DEFAULT_ELASTICITY_CONFIG):
        group = "Elasticity ladder" if f.name.startswith("ladder_") else "Elasticity score"
        thresholds.append(
            ThresholdRow(
                key=f.name, value=str(getattr(oe.DEFAULT_ELASTICITY_CONFIG, f.name)), group=group
            )
        )

    exceptions: list[RiskExceptionRow] = []
    for sym in sorted(oe.all_overrides()):
        meta = ew.name_meta(sym)
        ov = oe.name_elasticity(sym)
        tier = oe.compute_elasticity(sym, oe.ElasticityInputs(), peak_50d=meta.peak_50d).tier
        flags: list[str] = []
        if ov:
            if ov.hard_override:
                flags.append("hard-override")
            if ov.provisional:
                flags.append("provisional")
            if ov.watch_promote:
                flags.append("watch-promote")
            if ov.exclude_recalibration:
                flags.append("excl-recalibration")
        if meta.low_confidence:
            flags.append("low-confidence")
        exceptions.append(
            RiskExceptionRow(
                ticker=sym,
                track=meta.track,
                overshoot=meta.overshoot,
                elasticity_tier=tier,
                flags=flags,
                note=ov.note if ov else "",
            )
        )
    return WashoutReferenceResponse(thresholds=thresholds, exceptions=exceptions)


def _realized_vol(closes: list[float], window: int) -> float | None:
    """Annualized realized volatility (%) over the last ``window`` daily returns."""
    if len(closes) < window + 1:
        return None
    rets = [
        closes[i] / closes[i - 1] - 1.0
        for i in range(len(closes) - window, len(closes))
        if closes[i - 1] > 0
    ]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return float((var**0.5) * (252**0.5) * 100.0)


def _latest_session_dp_stats(
    prints: list[dict[str, Any]] | None,
) -> tuple[float | None, float | None]:
    """Return (sell_pct, net_flow_usd) for the most recent dark-pool session."""
    if not prints:
        return None, None
    sessions = _group_by_session(prints, "executed_at")
    if not sessions:
        return None, None
    latest = sessions[0]
    buy_usd = 0.0
    sell_usd = 0.0
    for rec in latest:
        price = _safe_float(rec.get("price"))
        if price is None:
            continue
        bid = _safe_float(rec.get("nbbo_bid"))
        ask = _safe_float(rec.get("nbbo_ask"))
        codes_raw = rec.get("sale_cond_codes") or ()
        codes = tuple(c for c in codes_raw if isinstance(c, str)) if isinstance(
            codes_raw, (list, tuple)
        ) else ()
        cls = _classify_dark_pool_print(price, bid, ask, codes)
        if cls == "SETTLEMENT":
            continue
        prem = _print_premium_usd(rec)
        if prem <= 0:
            continue
        if cls == "BUY":
            buy_usd += prem
        else:
            sell_usd += prem
    total = buy_usd + sell_usd
    if total <= 0:
        return None, None
    return (sell_usd / total) * 100.0, buy_usd - sell_usd


def _compute_breadth(
    closes_by_day: list[dict[str, float]],
    universe: tuple[str, ...],
    cfg: ew.WashoutConfig,
) -> tuple[int, int, int]:
    """Count universe names down >= watch/hedge thresholds over 1-2 sessions (§5).

    ``closes_by_day`` is newest-first. Uses the more negative of the 1- and
    2-session returns per name. Returns (watch_count, hedge_count, universe_size).
    """
    if len(closes_by_day) < 2:
        return 0, 0, len(universe)
    today = closes_by_day[0]
    prev1 = closes_by_day[1]
    prev2 = closes_by_day[2] if len(closes_by_day) >= 3 else None

    watch = 0
    hedge = 0
    for sym in universe:
        c0 = today.get(sym)
        if c0 is None:
            continue
        rets: list[float] = []
        if prev1.get(sym):
            rets.append((c0 - prev1[sym]) / prev1[sym] * 100.0)
        if prev2 and prev2.get(sym):
            rets.append((c0 - prev2[sym]) / prev2[sym] * 100.0)
        if not rets:
            continue
        worst = min(rets)
        if worst <= -cfg.breadth_watch_down_pct:
            watch += 1
        if worst <= -cfg.breadth_hedge_down_pct:
            hedge += 1
    return watch, hedge, len(universe)
