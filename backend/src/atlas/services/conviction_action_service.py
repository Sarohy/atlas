"""Framework 6 — Conviction Action service (v7.3.5 New Tier Structure).

Derives the investor conviction tier and position-size guidance from the
regime-adjusted Framework Score (Framework 1 score, modified by Framework 2).

Tier assignment (evaluated against the adjusted score):
  score >= 85  -> T1_ELITE : 5-10% NAV  -- LEAPS eligible
  80-84        -> T1       : 2-4% NAV   -- Core position
  70-79        -> T2       : 0.5-1.5%   -- GTC adds permitted
  50-69        -> T3       : 0-0.5%     -- Small speculative position
  below 50    → BELOW_GATE : 0%        — No capital; exit rules active

Exit rule: two consecutive Friday closes below 50 → exit_triggered = True.
  Framework 16 owns exit execution; Framework 6 only sets the flag.

Exit cycle counts: stored in in-memory dict (swap for Redis in prod).

Pure helpers (no I/O, fully unit-testable without mocks):
  assign_tier, get_tier_details, _compute_size_status, _compute_adds_permitted,
  _score_band, update_exit_cycle, get_exit_cycle_count, reset_exit_cycle.
"""

from __future__ import annotations

import logging
from typing import Final, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.core.scoring import TIER_3_MIN as _SCORE_TIER3_MIN
from atlas.core.scoring import classify_tier
from atlas.schemas.conviction_action import (
    ConsensusStatus,
    ConsensusUpdateRequest,
    ConvictionActionResponse,
    ExitCycleResponse,
    PositionSizeStatus,
    Tier,
)
# ConsensusStatus and ConsensusUpdateRequest retained for backward compatibility
from atlas.schemas.regime_modifier import RegimeModifierResponse
from atlas.services.framework13_service import is_beta_capped
from atlas.services.framework14_service import (
    TICKER_CLUSTER_MAP,
    evaluate_cluster,
    evaluate_concentration,
    get_cluster_weight,
    get_position_weight_and_nav,
)
from atlas.services.regime_modifier_service import RegimeModifierService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score thresholds — the only constant needed locally; all band boundaries
# live in atlas.core.scoring.classify_tier (single source of truth).
# ---------------------------------------------------------------------------

# Threshold below which exit cycle increments (== Tier 3 lower bound = 55)
_SCORE_EXIT_THRESHOLD: Final[int] = _SCORE_TIER3_MIN

# Number of consecutive below-threshold closes before exit is triggered
_EXIT_CYCLE_TRIGGER: Final[int] = 2


class _TierDetails(TypedDict):
    label: str
    size_min: float
    size_max: float
    action: str
    leaps: bool
    consensus: bool
    color: str


# In-memory stores -- swap for Redis with TTL in production
# ---------------------------------------------------------------------------

# Key: ticker (upper-case) → ConsensusStatus
_consensus_store: dict[str, ConsensusStatus] = {}

# Key: ticker (upper-case) → consecutive below-55 Friday close count
_exit_cycle_store: dict[str, int] = {}

# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no side effects
# ---------------------------------------------------------------------------


def assign_tier(final_score: float) -> Tier:
    """Map a regime-adjusted score to a conviction tier.

    Delegates to ``atlas.core.scoring.classify_tier`` — the single source of
    truth for v7.3.3 tier boundaries.

    Pure function — no I/O, fully unit-testable.
    """
    return Tier(classify_tier(final_score)["tier"])


def get_tier_details(tier: Tier) -> _TierDetails:
    """Return size range, label, action text and flags for a tier.

    Pure function -- no I/O.
    """
    details: dict[Tier, _TierDetails] = {
        Tier.T1_ELITE: {
            "label": "T1 ELITE",
            "size_min": 0.05,
            "size_max": 0.10,
            "action": "Hold full — add on dips. LEAPS eligible",
            "leaps": True,
            "consensus": False,
            "color": "#39d353",
        },
        Tier.T1: {
            "label": "T1",
            "size_min": 0.02,
            "size_max": 0.04,
            "action": "Core position — GTC adds permitted",
            "leaps": False,
            "consensus": False,
            "color": "#26c6a2",
        },
        Tier.T2: {
            "label": "T2",
            "size_min": 0.005,
            "size_max": 0.015,
            "action": "Small satellites only",
            "leaps": False,
            "consensus": False,
            "color": "#58a6ff",
        },
        Tier.T3: {
            "label": "T3",
            "size_min": 0.0,
            "size_max": 0.005,
            "action": "Small speculative position only",
            "leaps": False,
            "consensus": False,
            "color": "#f0a500",
        },
        Tier.BELOW_GATE: {
            "label": "BELOW GATE",
            "size_min": 0.0,
            "size_max": 0.0,
            "action": "No capital — monitor only",
            "leaps": False,
            "consensus": False,
            "color": "#f85149",
        },
    }
    return details[tier]


def _compute_size_status(
    tier: Tier,
    position_weight: float,
    size_min: float,
    size_max: float,
) -> tuple[PositionSizeStatus, float, bool]:
    """Return (position_size_status, room_to_add, trim_suggested).

    room_to_add and position_weight are expressed as fractions of NAV.

    Pure function — no I/O.
    """
    if tier == Tier.BELOW_GATE:
        trim_suggested = position_weight > 0.0
        return (PositionSizeStatus.NO_POSITION, 0.0, trim_suggested)
    if position_weight < size_min:
        return (PositionSizeStatus.UNDERWEIGHT, size_max - position_weight, False)
    if position_weight <= size_max:
        return (PositionSizeStatus.IN_RANGE, size_max - position_weight, False)
    return (PositionSizeStatus.OVERWEIGHT, 0.0, True)


def _compute_adds_permitted(
    tier: Tier,
    beta_cap_active: bool,
    concentration_cap: bool,
    consensus_status: ConsensusStatus,
    f15_blocks: bool | None = False,
    f18_speculative_blocked: bool = False,
    f18_tier3_blocked: bool = False,
    f18_unknown_blocks: bool = False,
) -> tuple[bool, str | None]:
    """Return (adds_permitted, blocking_reason).

    Priority order (spec §7 step 7):
      1. BELOW_GATE → blocked
      2. Beta cap active → blocked
      3. Concentration cap active → blocked
      4. F15 VIX session halt → blocked
      5. F18 speculative starter blocked → blocked
      6. F18 Tier 3 blocked → blocked
      7. F18 data unknown → blocked (conservative)
      8. F19 NVDA kill switch → blocked

    Pure function — no I/O.
    """
    if tier == Tier.BELOW_GATE:
        return (False, "Below gate — no capital permitted")
    if beta_cap_active:
        return (False, "Beta cap (F13) blocking adds")
    if concentration_cap:
        return (False, "Concentration cap (F14) blocking adds")
    if f15_blocks is True:
        return (False, "F15 VIX session halt active — no new orders this session")
    if f15_blocks is None:
        return (False, "F15 status unknown — VIX data unavailable")
    if f18_speculative_blocked:
        return (False, "F18 active — no new positions on non-portfolio tickers")
    if f18_tier3_blocked:
        return (False, "F18 active — Tier 3 adds blocked during 4-week trend gate")
    if f18_unknown_blocks:
        return (False, "F18 status unknown — SPY data unavailable (conservative block)")
    return (True, None)


def _score_band(tier: Tier) -> tuple[int, int | None]:
    """Return (band_min, band_max) for the tier.

    TIER_1_CORE has no ceiling → band_max = None.

    Pure function — no I/O.
    """
    band: dict[Tier, tuple[int, int | None]] = {
        Tier.T1_ELITE: (85, None),
        Tier.T1: (80, 84),
        Tier.T2: (70, 79),
        Tier.T3: (50, 69),
        Tier.BELOW_GATE: (0, 49),
    }
    return band[tier]


def _build_rationale(tier: Tier, exit_triggered: bool) -> str:
    """Return the bottom-line one-liner action message.

    Pure function — no I/O.
    """
    if exit_triggered:
        return "Exit triggered — delegate to Framework 16"
    messages: dict[Tier, str] = {
        Tier.T1_ELITE: "Hold full position and add on dips — LEAPS eligible",
        Tier.T1: "Core position — GTC adds permitted",
        Tier.T2: "GTC adds permitted — size within tier",
        Tier.T3: "Speculative small position only — max 0.5% NAV",
        Tier.BELOW_GATE: "No capital — monitor every Friday",
    }
    return messages[tier]


# ---------------------------------------------------------------------------
# In-memory state helpers — no I/O, but mutate module-level stores
# ---------------------------------------------------------------------------


def get_exit_cycle_count(ticker: str) -> int:
    """Return the current exit cycle count for *ticker*."""
    return _exit_cycle_store.get(ticker.strip().upper(), 0)


def update_exit_cycle(ticker: str, score: float) -> int:
    """Increment or reset the exit cycle counter based on *score*.

    Called every Friday close.
      score < 55  → increment counter
      score ≥ 55  → reset counter to 0

    Returns the updated count.
    """
    upper = ticker.strip().upper()
    if score < _SCORE_EXIT_THRESHOLD:
        _exit_cycle_store[upper] = _exit_cycle_store.get(upper, 0) + 1
    else:
        _exit_cycle_store[upper] = 0
    return _exit_cycle_store[upper]


def reset_exit_cycle(ticker: str) -> None:
    """Reset the exit cycle counter to 0 for *ticker*."""
    _exit_cycle_store.pop(ticker.strip().upper(), None)


def set_consensus_status(ticker: str, status: ConsensusStatus) -> None:
    """Persist *status* for *ticker* in the in-memory consensus store."""
    _consensus_store[ticker.strip().upper()] = status


def get_consensus_status_for_tier(ticker: str, tier: Tier) -> ConsensusStatus:
    """Consensus concept removed in v7.3.5 — always returns NOT_REQUIRED."""
    return ConsensusStatus.NOT_REQUIRED


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class ConvictionActionService:
    """Computes Framework 6 conviction-action guidance for a single ticker.

    Calls Framework 2 (Regime Modifier) to obtain the regime-adjusted score,
    then applies the v7.3.5 tier logic.  Framework 13 (beta cap) and
    Framework 14 (concentration cap + cluster) are consulted for blocking
    conditions and display data.
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
        self._session = session

    async def compute_conviction_action(
        self,
        ticker: str,
        provided_adjusted_score: float | None = None,
    ) -> ConvictionActionResponse:
        """Return the full Framework 6 conviction-action result for *ticker*.

        When *provided_adjusted_score* is given (the score already displayed
        by the F1 panel — regime modifier already applied) the regime service
        is skipped entirely to avoid double-penalising the score.
        """
        upper = ticker.strip().upper()

        # ── Step 1: Resolve final score ──────────────────────────────────
        if provided_adjusted_score is not None:
            final_score = float(max(0.0, min(100.0, provided_adjusted_score)))
        else:
            regime_result = await self._regime_service.compute_regime_modifier(
                upper, geopolitical_state="NONE"
            )
            if isinstance(regime_result, RegimeModifierResponse):
                final_score = float(regime_result.adjusted_score)
            else:
                logger.warning(
                    "Regime modifier returned unexpected type; defaulting to 50",
                    extra={"ticker": upper, "result": repr(regime_result)},
                )
                final_score = 50.0

        # ── Step 2: Assign tier ──────────────────────────────────────────
        tier = assign_tier(final_score)
        details = get_tier_details(tier)

        # ── Step 3: Position weight from DB ──────────────────────────────
        position_weight, _pos_dollars, _nav = await get_position_weight_and_nav(
            upper, self._session
        )

        # -- Step 4: Size status
        size_min = details["size_min"]
        size_max = details["size_max"]
        size_status, room_to_add, trim_suggested = _compute_size_status(
            tier, position_weight, size_min, size_max
        )

        # ── Step 5: Beta cap (pure, no I/O) ───────────────────────────────
        beta_check = is_beta_capped(upper, position_weight)
        beta_cap_active = bool(beta_check.get("cap_active", False))

        # ── Step 6: Concentration cap (pure, no I/O) ──────────────────────
        conc = evaluate_concentration(upper, position_weight)
        concentration_cap = bool(conc["cap_active"])

        # ── Step 7: Cluster info ──────────────────────────────────────────
        cluster_name = TICKER_CLUSTER_MAP.get(upper, "Unknown")
        cluster_weight = await get_cluster_weight(cluster_name, self._session)
        cluster_info = evaluate_cluster(upper, cluster_weight)

        # ── Step 8: Consensus ─────────────────────────────────────────────
        consensus_status = get_consensus_status_for_tier(upper, tier)

        # ── Step 9: Adds permitted ────────────────────────────────────────
        from atlas.services.framework15_service import get_f15_simple as _get_f15_simple

        _f15 = _get_f15_simple()
        _f15_blocks: bool | None = None if _f15 is None else bool(_f15.new_market_orders_blocked)

        # ── Step 9b: Framework 18 — 4-Week Trend Gate ────────────────────
        from atlas.services.framework18_service import get_f18_simple as _get_f18_simple

        _f18 = _get_f18_simple()

        # Defaults: no F18 effect until we inspect the cached result.
        _f18_active: bool | None = None
        _f18_speculative_blocked = False
        _f18_tier3_blocked = False
        _f18_size_max_reduced = False
        _f18_note: str | None = None
        _f18_unknown_blocks = False

        if _f18 is not None:
            _f18_active = _f18.f18_active

            if _f18.f18_active is True:
                # No new positions on tickers NOT already in the portfolio.
                if position_weight == 0.0:
                    _f18_speculative_blocked = True
                    _f18_note = (
                        f"F18 active — no new speculative starters. "
                        f"{_f18.consecutive_weeks_down} consecutive down weeks "
                        f"(threshold: {_f18.consecutive_threshold})."
                    )

                # Tier 3 adds are blocked when gate is active.
                if tier == Tier.T3:
                    _f18_tier3_blocked = True
                    _f18_note = (
                        f"F18 active — Tier 3 adds blocked. "
                        f"{_f18.consecutive_weeks_down} consecutive down weeks "
                        f"(threshold: {_f18.consecutive_threshold})."
                    )

                # Reduce size_max by add_reduction_pct for permitted tiers
                # (Tier 1 and Tier 2 existing positions only).
                if (
                    not _f18_speculative_blocked
                    and not _f18_tier3_blocked
                    and _f18.add_reduction_pct is not None
                    and _f18.add_reduction_pct > 0
                ):
                    reduction_factor = 1.0 - (_f18.add_reduction_pct / 100.0)
                    size_max = size_max * reduction_factor
                    room_to_add = max(0.0, size_max - position_weight)
                    _f18_size_max_reduced = True
                    _f18_note = (
                        f"F18 active — add size reduced by {_f18.add_reduction_pct:.0f}%. "
                        f"{_f18.consecutive_weeks_down} consecutive down weeks."
                    )

            elif _f18.f18_active is None:
                # SPY data unavailable — conservative block.
                _f18_unknown_blocks = True
                _f18_note = (
                    "F18 status unknown — SPY weekly data unavailable. "
                    "Adds blocked as conservative precaution."
                )

        adds_permitted, adds_blocked_reason = _compute_adds_permitted(
            tier,
            beta_cap_active,
            concentration_cap,
            consensus_status,
            _f15_blocks,
            f18_speculative_blocked=_f18_speculative_blocked,
            f18_tier3_blocked=_f18_tier3_blocked,
            f18_unknown_blocks=_f18_unknown_blocks,
        )

        # ── Step 10: Exit cycle ───────────────────────────────────────────
        exit_count = get_exit_cycle_count(upper)
        exit_triggered = tier == Tier.BELOW_GATE and exit_count >= _EXIT_CYCLE_TRIGGER

        # ── Step 11: Score band ───────────────────────────────────────────
        band_min, band_max = _score_band(tier)

        return ConvictionActionResponse(
            ticker=upper,
            final_score=final_score,
            tier=tier,
            tier_label=details["label"],
            tier_color=details["color"],
            score_band_min=band_min,
            score_band_max=band_max,
            size_min_pct=size_min * 100.0,
            size_max_pct=size_max * 100.0,
            action=details["action"],
            leaps_eligible=details["leaps"],
            current_weight_pct=round(position_weight * 100.0, 2),
            position_size_status=size_status,
            room_to_add_pct=round(room_to_add * 100.0, 2),
            trim_suggested=trim_suggested,
            adds_permitted=adds_permitted,
            adds_blocked_reason=adds_blocked_reason,
            beta_cap_active=beta_cap_active,
            concentration_cap=concentration_cap,
            exit_triggered=exit_triggered,
            exit_cycle_count=exit_count,
            cluster=str(cluster_info["cluster"]),
            cluster_weight_pct=round(cluster_weight * 100.0, 2),
            cluster_status=str(cluster_info["cluster_status"]),
            rationale=_build_rationale(tier, exit_triggered),
            f18_active=_f18_active,
            f18_speculative_blocked=_f18_speculative_blocked,
            f18_tier3_blocked=_f18_tier3_blocked,
            f18_size_max_reduced=_f18_size_max_reduced,
            f18_note=_f18_note,
        )

    async def update_consensus(
        self,
        ticker: str,
        request: ConsensusUpdateRequest,
    ) -> ConvictionActionResponse:
        """Set the consensus status for *ticker* and return updated result."""
        set_consensus_status(ticker, request.status)
        return await self.compute_conviction_action(ticker)

    async def record_exit_cycle(self, ticker: str, score: float) -> ExitCycleResponse:
        """Update the Friday-close exit cycle counter for *ticker*.

        If *score* < 55, increment; otherwise reset to 0.
        Returns (ticker, exit_cycle_count, exit_triggered).
        """
        count = update_exit_cycle(ticker, score)
        exit_triggered = count >= _EXIT_CYCLE_TRIGGER
        return ExitCycleResponse(
            ticker=ticker.strip().upper(),
            exit_cycle_count=count,
            exit_triggered=exit_triggered,
        )
