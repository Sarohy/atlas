"""Framework 6 — Conviction Action service (v7.3.4 Watchlist Tier Structure).

Derives the investor conviction tier and position-size guidance from the
regime-adjusted Framework Score (Framework 1 score, modified by Framework 2).

Tier assignment (evaluated against the adjusted score):
  score >= 85  -> TIER_1_CORE  : 3-5% NAV  -- Hold full, add on dips, LEAPS eligible
  78-84        -> GREY_ZONE    : 1.5-2.5%  -- 3-AI consensus required before any adds
  70-77        -> TIER_2       : 0.5-1.5%  -- GTC adds permitted
  55-69        -> TIER_3       : 0.25-0.5% -- Satellite sizing only
  below 55    → WATCHLIST    : 0%        — No capital, monitor, trigger exit rules

Exit rule: two consecutive Friday closes below 55 → exit_triggered = True.
  Framework 16 owns exit execution; Framework 6 only sets the flag.

Consensus (GREY_ZONE only): stored in in-memory dict (swap for Redis in prod).
Exit cycle counts: same in-memory pattern.

Pure helpers (no I/O, fully unit-testable without mocks):
  assign_tier, get_tier_details, _compute_size_status, _compute_adds_permitted,
  _score_band, update_exit_cycle, get_exit_cycle_count, reset_exit_cycle,
  set_consensus_status, get_consensus_status_for_tier.
"""

from __future__ import annotations

import logging
from typing import Final, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from atlas.schemas.conviction_action import (
    ConsensusStatus,
    ConsensusUpdateRequest,
    ConvictionActionResponse,
    ExitCycleResponse,
    PositionSizeStatus,
    Tier,
)
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
# Score thresholds (named constants)
# ---------------------------------------------------------------------------

# Minimum score for TIER_1_CORE (inclusive)
_SCORE_TIER1_MIN: Final[int] = 85

# Minimum score for GREY_ZONE (inclusive)
_SCORE_GREY_MIN: Final[int] = 78

# Minimum score for TIER_2 (inclusive)
_SCORE_TIER2_MIN: Final[int] = 70

# Minimum score for TIER_3 (inclusive)
_SCORE_TIER3_MIN: Final[int] = 55

# Threshold below which exit cycle increments
_SCORE_EXIT_THRESHOLD: Final[int] = 55

# Number of consecutive below-threshold closes before exit is triggered
_EXIT_CYCLE_TRIGGER: Final[int] = 2

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# TypedDict for tier details
# ---------------------------------------------------------------------------


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

    Pure function — no I/O, fully unit-testable.
    """
    if final_score >= _SCORE_TIER1_MIN:
        return Tier.TIER_1_CORE
    if final_score >= _SCORE_GREY_MIN:
        return Tier.GREY_ZONE
    if final_score >= _SCORE_TIER2_MIN:
        return Tier.TIER_2
    if final_score >= _SCORE_TIER3_MIN:
        return Tier.TIER_3
    return Tier.WATCHLIST


def get_tier_details(tier: Tier) -> _TierDetails:
    """Return size range, label, action text and flags for a tier.

    Pure function -- no I/O.
    """
    details: dict[Tier, _TierDetails] = {
        Tier.TIER_1_CORE: {
            "label": "TIER 1 — CORE",
            "size_min": 0.030,
            "size_max": 0.050,
            "action": "Hold full — add on dips",
            "leaps": True,
            "consensus": False,
            "color": "#39d353",
        },
        Tier.GREY_ZONE: {
            "label": "GREY ZONE",
            "size_min": 0.015,
            "size_max": 0.025,
            "action": "3-AI consensus required",
            "leaps": False,
            "consensus": True,
            "color": "#a371f7",
        },
        Tier.TIER_2: {
            "label": "TIER 2",
            "size_min": 0.005,
            "size_max": 0.015,
            "action": "GTC adds permitted",
            "leaps": False,
            "consensus": False,
            "color": "#58a6ff",
        },
        Tier.TIER_3: {
            "label": "TIER 3",
            "size_min": 0.0025,
            "size_max": 0.005,
            "action": "Satellite sizing only",
            "leaps": False,
            "consensus": False,
            "color": "#f0a500",
        },
        Tier.WATCHLIST: {
            "label": "WATCHLIST",
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
    if tier == Tier.WATCHLIST:
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
) -> tuple[bool, str | None]:
    """Return (adds_permitted, blocking_reason).

    Priority order (spec §7 step 7):
      1. WATCHLIST → blocked
      2. Beta cap active → blocked
      3. Concentration cap active → blocked
      4. GREY_ZONE without CONFIRMED consensus → blocked

    Pure function — no I/O.
    """
    if tier == Tier.WATCHLIST:
        return (False, "Watchlist — no capital permitted")
    if beta_cap_active:
        return (False, "Beta cap (F13) blocking adds")
    if concentration_cap:
        return (False, "Concentration cap (F14) blocking adds")
    if tier == Tier.GREY_ZONE and consensus_status != ConsensusStatus.CONFIRMED:
        return (False, "3-AI consensus required")
    return (True, None)


def _score_band(tier: Tier) -> tuple[int, int | None]:
    """Return (band_min, band_max) for the tier.

    TIER_1_CORE has no ceiling → band_max = None.

    Pure function — no I/O.
    """
    band: dict[Tier, tuple[int, int | None]] = {
        Tier.TIER_1_CORE: (85, None),
        Tier.GREY_ZONE: (78, 84),
        Tier.TIER_2: (70, 77),
        Tier.TIER_3: (55, 69),
        Tier.WATCHLIST: (0, 54),
    }
    return band[tier]


def _build_rationale(tier: Tier, exit_triggered: bool) -> str:
    """Return the bottom-line one-liner action message.

    Pure function — no I/O.
    """
    if exit_triggered:
        return "Exit triggered — delegate to Framework 16"
    messages: dict[Tier, str] = {
        Tier.TIER_1_CORE: "Hold full position and add on dips",
        Tier.GREY_ZONE: "Run 3-AI consensus before adding",
        Tier.TIER_2: "GTC adds permitted — size within tier",
        Tier.TIER_3: "Satellite only — max 0.5% NAV",
        Tier.WATCHLIST: "No capital — monitor every Friday",
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
    """Return the consensus status, auto-initialising to PENDING for GREY_ZONE.

    Non-grey-zone tiers always return NOT_REQUIRED.
    """
    if tier != Tier.GREY_ZONE:
        return ConsensusStatus.NOT_REQUIRED
    upper = ticker.strip().upper()
    if upper not in _consensus_store:
        _consensus_store[upper] = ConsensusStatus.PENDING
    return _consensus_store[upper]


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class ConvictionActionService:
    """Computes Framework 6 conviction-action guidance for a single ticker.

    Calls Framework 2 (Regime Modifier) to obtain the regime-adjusted score,
    then applies the v7.3.4 tier logic.  Framework 13 (beta cap) and
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
        adds_permitted, adds_blocked_reason = _compute_adds_permitted(
            tier, beta_cap_active, concentration_cap, consensus_status
        )

        # ── Step 10: Exit cycle ───────────────────────────────────────────
        exit_count = get_exit_cycle_count(upper)
        exit_triggered = tier == Tier.WATCHLIST and exit_count >= _EXIT_CYCLE_TRIGGER

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
            consensus_required=details["consensus"],
            consensus_status=consensus_status,
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
