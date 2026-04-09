"""F4 Options Flow service.

Data source: Unusual Whales API (https://api.unusualwhales.com)
Authentication: Bearer token in Authorization header.

Three API calls per ticker:
  1. GET /api/stock/{ticker}/options-volume         → call/put premiums, volumes, OI
  2. GET /api/option-trades/flow-alerts             → whale blocks, sweeps, collar detection
  3. GET /api/darkpool/{ticker}                     → dark pool prints

F4 sub-indicators and weights (Factor_Mapping_Guide Table 10):
  1. Whale Block Size      (35%) — largest single-print premium
  2. Call/Put Ratio        (20%) — call_premium / put_premium
  3. Volume vs OI          (20%) — call_volume / call_open_interest
  4. Dark Pool Print       (15%) — total dark pool premium today
  5. Sweep Type            (10%) — golden sweep / single sweep / block / normal

Collar flag: capped at 68 if multi-leg put+call structure detected.

Signal Hierarchy (Factor_Mapping_Guide Table 11):
  GOLD   — Golden Sweep >$5M multi-exchange
  BLUE   — Whale Block  >$1M
  GREEN  — Repeated Hits >$500K same strike
  YELLOW — Unusual Volume >3× OI
  GREY   — Dark Pool >$100K
  WHITE  — Normal elevated call activity

LITE worked example (F4 = 82):
  Whale Block: 85 (1-5M block) × 0.35 = 29.75
  Call/Put:   100 (>3:1 call)  × 0.20 = 20.00
  Vol/OI:      85 (3-5×)       × 0.20 = 17.00
  Dark Pool:   50 (normal)     × 0.15 =  7.50
  Sweep:       80 (single)     × 0.10 =  8.00
  F4 = 82.25 → 82
"""

from __future__ import annotations

import os
from typing import Any, Final

import httpx

from atlas.schemas.options_flow import (
    CallPutRatioIndicator,
    DarkPoolIndicator,
    OptionsFlowResponse,
    SignalTier,
    SweepTypeIndicator,
    VolumeOiIndicator,
    WhaleBlockIndicator,
)

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

_W_WHALE: Final[float] = 0.35
_W_CP_RATIO: Final[float] = 0.20
_W_VOL_OI: Final[float] = 0.20
_W_DARK_POOL: Final[float] = 0.15
_W_SWEEP: Final[float] = 0.10

# ---------------------------------------------------------------------------
# Score thresholds
# ---------------------------------------------------------------------------

_COLLAR_CAP: Final[int] = 68
_GRADE_STRONG_BUY: Final[int] = 80
_GRADE_BUY: Final[int] = 60
_GRADE_NEUTRAL: Final[int] = 40
_GRADE_WEAK: Final[int] = 20

# Whale / golden sweep premium thresholds (USD)
_GOLDEN_SWEEP_THRESHOLD: Final[float] = 5_000_000
_WHALE_BLUE_THRESHOLD: Final[float] = 1_000_000
_WHALE_GREEN_THRESHOLD: Final[float] = 500_000
_WHALE_GREY_THRESHOLD: Final[float] = 100_000

_TIMEOUT: Final[float] = 10.0
_BASE_URL: Final[str] = "https://api.unusualwhales.com"

# ---------------------------------------------------------------------------
# Scoring functions (each returns 0-100)
# ---------------------------------------------------------------------------


def _score_whale_block(largest_premium: float | None) -> int:
    """Whale Block Size score (0-100).

    Guide: >$5M → 100 | $1-5M → 85 | $500K-1M → 70 | $100K-500K → 50 | <$100K → 30
    """
    if largest_premium is None:
        return 30
    if largest_premium > _GOLDEN_SWEEP_THRESHOLD:
        return 100
    if largest_premium >= _WHALE_BLUE_THRESHOLD:
        return 85
    if largest_premium >= _WHALE_GREEN_THRESHOLD:
        return 70
    if largest_premium >= _WHALE_GREY_THRESHOLD:
        return 50
    return 30


def _score_cp_ratio(ratio: float | None) -> int:
    """Call/Put Ratio score (0-100).

    Guide: >3:1 → 100 | 2-3:1 → 85 | 1.5-2:1 → 70 | ~1:1 → 50 | Put heavy (<1) → 20
    """
    if ratio is None:
        return 50  # neutral
    if ratio > 3.0:
        return 100
    if ratio >= 2.0:
        return 85
    if ratio >= 1.5:
        return 70
    if ratio >= 0.8:
        return 50
    return 20


def _score_vol_oi(vol_oi_ratio: float | None) -> int:
    """Volume vs OI score (0-100).

    Guide: >5× → 100 | 3-5× → 85 | 2-3× → 70 | 1-2× → 55 | <1× → 30
    """
    if vol_oi_ratio is None:
        return 30
    if vol_oi_ratio > 5.0:
        return 100
    if vol_oi_ratio >= 3.0:
        return 85
    if vol_oi_ratio >= 2.0:
        return 70
    if vol_oi_ratio >= 1.0:
        return 55
    return 30


def _score_dark_pool(largest_print: float | None) -> int:
    """Dark Pool Print score (0-100).

    Guide: Print at key support level → 100 | Large block off-exchange → 80
           Normal DP activity → 50 | None → 30
    Thresholds: >$5M → 100 | $1-5M → 80 | $100K-1M → 50 | <$100K or none → 30
    """
    if largest_print is None or largest_print == 0:
        return 30
    if largest_print > _GOLDEN_SWEEP_THRESHOLD:
        return 100
    if largest_print >= _WHALE_BLUE_THRESHOLD:
        return 80
    if largest_print >= _WHALE_GREY_THRESHOLD:
        return 50
    return 30


def _score_sweep(
    has_golden_sweep: bool,
    has_single_sweep: bool,
    has_repeated_hits: bool,
) -> int:
    """Sweep Type score (0-100).

    Guide: Golden Sweep (multi-exchange) → 100 | Single sweep → 80
           Repeated hits → 75 | Block → 65 | Normal → 40
    """
    if has_golden_sweep:
        return 100
    if has_single_sweep:
        return 80
    if has_repeated_hits:
        return 75
    return 40


def _derive_signal_tier(
    largest_premium: float | None,
    vol_oi_ratio: float | None,
    largest_dark_pool: float | None,
    has_golden_sweep: bool,
    has_repeated_hits: bool,
) -> str:
    """Return the highest applicable signal tier per the F4 signal hierarchy."""
    if has_golden_sweep and (largest_premium or 0) > _GOLDEN_SWEEP_THRESHOLD:
        return SignalTier.GOLD
    if (largest_premium or 0) >= _WHALE_BLUE_THRESHOLD:
        return SignalTier.BLUE
    if has_repeated_hits and (largest_premium or 0) >= _WHALE_GREEN_THRESHOLD:
        return SignalTier.GREEN
    if (vol_oi_ratio or 0) > 3.0:
        return SignalTier.YELLOW
    if (largest_dark_pool or 0) >= _WHALE_GREY_THRESHOLD:
        return SignalTier.GREY
    return SignalTier.WHITE


def _grade_from_score(score: int) -> str:
    if score >= _GRADE_STRONG_BUY:
        return "STRONG BUY"
    if score >= _GRADE_BUY:
        return "BUY"
    if score >= _GRADE_NEUTRAL:
        return "NEUTRAL"
    if score >= _GRADE_WEAK:
        return "WEAK"
    return "AVOID"


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _build_response(
    ticker: str,
    largest_premium: float | None,
    call_premium: float | None,
    put_premium: float | None,
    call_volume: float | None,
    call_oi: float | None,
    largest_dark_pool: float | None,
    total_dark_pool: float | None,
    dark_pool_count: int,
    has_golden_sweep: bool,
    has_single_sweep: bool,
    has_repeated_hits: bool,
    sweep_premium: float | None,
    collar_flag: bool,
) -> OptionsFlowResponse:
    # Call/put ratio
    ratio: float | None = None
    if call_premium and put_premium and put_premium > 0:
        ratio = call_premium / put_premium

    # Vol/OI ratio
    vol_oi_ratio: float | None = None
    if call_volume is not None and call_oi and call_oi > 0:
        vol_oi_ratio = call_volume / call_oi

    # Individual scores
    whale_score = _score_whale_block(largest_premium)
    cp_score = _score_cp_ratio(ratio)
    vol_oi_score = _score_vol_oi(vol_oi_ratio)
    dp_score = _score_dark_pool(largest_dark_pool)
    sweep_score = _score_sweep(has_golden_sweep, has_single_sweep, has_repeated_hits)

    # Weighted F4
    f4_raw = (
        whale_score * _W_WHALE
        + cp_score * _W_CP_RATIO
        + vol_oi_score * _W_VOL_OI
        + dp_score * _W_DARK_POOL
        + sweep_score * _W_SWEEP
    )
    f4_score = round(f4_raw)

    # Collar cap
    if collar_flag:
        f4_score = min(f4_score, _COLLAR_CAP)

    signal_tier = _derive_signal_tier(
        largest_premium, vol_oi_ratio, largest_dark_pool, has_golden_sweep, has_repeated_hits
    )

    return OptionsFlowResponse(
        ticker=ticker.upper(),
        whale_block=WhaleBlockIndicator(
            largest_premium=largest_premium,
            score=whale_score,
            weight=_W_WHALE,
        ),
        call_put_ratio=CallPutRatioIndicator(
            call_premium=call_premium,
            put_premium=put_premium,
            ratio=ratio,
            score=cp_score,
            weight=_W_CP_RATIO,
        ),
        volume_oi=VolumeOiIndicator(
            call_volume=call_volume,
            call_open_interest=call_oi,
            vol_oi_ratio=vol_oi_ratio,
            score=vol_oi_score,
            weight=_W_VOL_OI,
        ),
        dark_pool=DarkPoolIndicator(
            total_dark_pool_premium=total_dark_pool,
            largest_print=largest_dark_pool,
            print_count=dark_pool_count,
            score=dp_score,
            weight=_W_DARK_POOL,
        ),
        sweep_type=SweepTypeIndicator(
            has_golden_sweep=has_golden_sweep,
            has_single_sweep=has_single_sweep,
            has_repeated_hits=has_repeated_hits,
            sweep_premium=sweep_premium,
            score=sweep_score,
            weight=_W_SWEEP,
        ),
        signal_tier=signal_tier,
        collar_flag=collar_flag,
        f4_score=f4_score,
        f4_grade=_grade_from_score(f4_score),
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class OptionsFlowService:
    """Fetches F4 data from Unusual Whales API and computes the F4 score."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    @classmethod
    def from_env(cls) -> OptionsFlowService:
        return cls(api_key=os.environ.get("UNUSUAL_WHALES_API_KEY", ""))

    async def compute_options_flow(self, ticker: str) -> OptionsFlowResponse:
        """Fetch data from Unusual Whales and return an OptionsFlowResponse."""
        ticker = ticker.upper()
        async with httpx.AsyncClient(
            base_url=_BASE_URL,
            headers=self._headers,
            timeout=_TIMEOUT,
        ) as client:
            vol_data = await self._fetch_options_volume(client, ticker)
            flow_data = await self._fetch_flow_alerts(client, ticker)
            dp_data = await self._fetch_dark_pool(client, ticker)

        return _build_response(
            ticker=ticker,
            largest_premium=flow_data.get("largest_premium"),
            call_premium=vol_data.get("call_premium"),
            put_premium=vol_data.get("put_premium"),
            call_volume=vol_data.get("call_volume"),
            call_oi=vol_data.get("call_open_interest"),
            largest_dark_pool=dp_data.get("largest_print"),
            total_dark_pool=dp_data.get("total_premium"),
            dark_pool_count=dp_data.get("count", 0),
            has_golden_sweep=flow_data.get("has_golden_sweep", False),
            has_single_sweep=flow_data.get("has_single_sweep", False),
            has_repeated_hits=flow_data.get("has_repeated_hits", False),
            sweep_premium=flow_data.get("sweep_premium"),
            collar_flag=flow_data.get("collar_flag", False),
        )

    # ------------------------------------------------------------------
    # Unusual Whales — options volume summary
    # ------------------------------------------------------------------

    async def _fetch_options_volume(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        """Fetch today's call/put premiums, volumes, and OI.

        Endpoint: GET /api/stock/{ticker}/options-volume?limit=1
        Returns most recent trading day's aggregate data.
        """
        try:
            resp = await client.get(
                f"/api/stock/{ticker}/options-volume",
                params={"limit": 1},
            )
            resp.raise_for_status()
            payload: Any = resp.json()

            # Response is a list; take the first (most recent) record
            records: list[Any] = payload if isinstance(payload, list) else payload.get("data", [])
            if not records:
                return {}

            rec: dict[str, Any] = records[0] if isinstance(records[0], dict) else {}

            def _float(key: str) -> float | None:
                v = rec.get(key)
                try:
                    return float(v) if v is not None else None
                except (TypeError, ValueError):
                    return None

            return {
                "call_premium": _float("call_premium"),
                "put_premium": _float("put_premium"),
                "call_volume": _float("call_volume"),
                "put_volume": _float("put_volume"),
                "call_open_interest": _float("call_open_interest"),
                "put_open_interest": _float("put_open_interest"),
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Unusual Whales — flow alerts (whale blocks + sweeps + collar)
    # ------------------------------------------------------------------

    async def _fetch_flow_alerts(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        """Detect whale blocks, sweeps, repeated hits, and collar structures.

        Endpoint: GET /api/option-trades/flow-alerts
        Params: ticker_symbol, min_premium=100000, limit=200
        """
        try:
            resp = await client.get(
                "/api/option-trades/flow-alerts",
                params={
                    "ticker_symbol": ticker,
                    "min_premium": 100_000,
                    "limit": 200,
                },
            )
            resp.raise_for_status()
            payload: Any = resp.json()
            alerts: list[Any] = (
                payload if isinstance(payload, list)
                else payload.get("data", payload.get("alerts", []))
            )

            largest_premium: float = 0.0
            sweep_premium: float | None = None
            has_golden_sweep = False
            has_single_sweep = False
            has_repeated_hits = False
            large_call_premium: float = 0.0
            large_put_premium: float = 0.0

            for alert in alerts:
                if not isinstance(alert, dict):
                    continue

                raw_prem = alert.get("total_premium") or alert.get("premium") or 0
                try:
                    prem = float(raw_prem)
                except (TypeError, ValueError):
                    prem = 0.0

                contract_type: str = (
                    alert.get("type") or alert.get("option_type") or ""
                ).lower()

                # Track largest print
                if prem > largest_premium:
                    largest_premium = prem

                # Sweep detection
                is_sweep = bool(alert.get("has_sweep") or alert.get("is_sweep"))
                is_multileg = bool(alert.get("has_multileg") or alert.get("is_multi_leg"))
                alert_rule: str = (alert.get("alert_rule") or "").lower()

                if is_sweep and prem > _GOLDEN_SWEEP_THRESHOLD:
                    has_golden_sweep = True
                    sweep_premium = prem
                elif is_sweep:
                    has_single_sweep = True
                    if sweep_premium is None or prem > (sweep_premium or 0):
                        sweep_premium = prem

                if "repeatedhits" in alert_rule or "repeated" in alert_rule:
                    has_repeated_hits = True

                # Collar detection: large multi-leg with both calls and puts
                if is_multileg:
                    if contract_type == "call":
                        large_call_premium += prem
                    elif contract_type == "put":
                        large_put_premium += prem

            # Collar flag: multi-leg with significant both-sided premium
            collar_flag = (
                large_call_premium > _WHALE_GREY_THRESHOLD
                and large_put_premium > _WHALE_GREY_THRESHOLD
                and abs(large_call_premium - large_put_premium)
                < max(large_call_premium, large_put_premium) * 0.5
            )

            return {
                "largest_premium": largest_premium if largest_premium > 0 else None,
                "has_golden_sweep": has_golden_sweep,
                "has_single_sweep": has_single_sweep,
                "has_repeated_hits": has_repeated_hits,
                "sweep_premium": sweep_premium,
                "collar_flag": collar_flag,
            }
        except Exception:
            return {
                "has_golden_sweep": False,
                "has_single_sweep": False,
                "has_repeated_hits": False,
                "collar_flag": False,
            }

    # ------------------------------------------------------------------
    # Unusual Whales — dark pool prints
    # ------------------------------------------------------------------

    async def _fetch_dark_pool(
        self, client: httpx.AsyncClient, ticker: str
    ) -> dict[str, Any]:
        """Fetch today's dark pool / off-exchange print activity.

        Endpoint: GET /api/darkpool/{ticker}
        """
        try:
            resp = await client.get(
                f"/api/darkpool/{ticker}",
                params={"limit": 500},
            )
            resp.raise_for_status()
            payload: Any = resp.json()
            prints: list[Any] = (
                payload if isinstance(payload, list)
                else payload.get("data", payload.get("darkpool", []))
            )

            total_premium: float = 0.0
            largest_print: float = 0.0
            count = 0

            for print_rec in prints:
                if not isinstance(print_rec, dict):
                    continue
                if print_rec.get("canceled"):
                    continue

                raw_prem = print_rec.get("premium") or print_rec.get("size", 0)
                try:
                    prem = float(raw_prem)
                except (TypeError, ValueError):
                    prem = 0.0

                # If only size (shares) is returned, estimate premium = size × price
                if prem < 1000 and print_rec.get("price"):
                    try:
                        prem = prem * float(print_rec["price"])
                    except (TypeError, ValueError):
                        pass

                total_premium += prem
                count += 1
                if prem > largest_print:
                    largest_print = prem

            return {
                "total_premium": total_premium if total_premium > 0 else None,
                "largest_print": largest_print if largest_print > 0 else None,
                "count": count,
            }
        except Exception:
            return {"count": 0}
