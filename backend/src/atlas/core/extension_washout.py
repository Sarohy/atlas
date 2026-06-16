"""ATLAS Extension & Washout Overlay — pure posture/state engine (Spec v2).

A DISPLAY / POSTURE overlay only. It decides WHEN to protect / trim a position
and at what posture; it never modifies F1-F5 or the 0-100 ATLAS score (Edit 1).
RSI and extension distance never write into the score path — this module reads
price/flow metrics and emits one of nine posture states.

Architecture (HIGH confidence) vs constants (DELIBERATELY provisional): every
threshold lives in ``WashoutConfig`` and is meant to be paper-traded and
re-checked each quarterly recompute (Edit 8). The logic here is firm; the numbers
are starting hypotheses.

Sections refer to the spec:
  * Two management tracks (§2): TRACK WINS over tier on conflict.
  * Extension arming ladder (§3) — +40% is an ARMING line, not a sell line.
  * Position-size rule (§3.1) — below target re-labels trim states to Stop-Add.
  * Absorption (§4), Breadth (§5), Reactive DP-confirm (§6).
  * Share trims require a trigger (§7) — never RSI/50d alone (Edit 9).
  * Nine output states + precedence (§9).

Pure functions only — no I/O, no globals. The service supplies the measured
inputs (50d distance, RSI/moves, DP sell%, breadth counts, position size).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# ---------------------------------------------------------------------------
# Enums (string constants — stable wire values)
# ---------------------------------------------------------------------------


class OverlayState:
    STOP_ADD: Final[str] = "STOP_ADD"
    ARM_PROTECTION: Final[str] = "ARM_PROTECTION"
    ACTIVE_PROTECTION: Final[str] = "ACTIVE_PROTECTION"
    HEDGE: Final[str] = "HEDGE"
    TRIM_WATCH: Final[str] = "TRIM_WATCH"
    TRIM: Final[str] = "TRIM"
    FORCED_DE_RISK_REVIEW: Final[str] = "FORCED_DE_RISK_REVIEW"
    BOOK_LEVEL_HEDGE: Final[str] = "BOOK_LEVEL_HEDGE"
    WAIT: Final[str] = "WAIT"


# §9 precedence, highest first. Used to resolve when several states fire.
_STATE_PRECEDENCE: Final[tuple[str, ...]] = (
    OverlayState.BOOK_LEVEL_HEDGE,
    OverlayState.FORCED_DE_RISK_REVIEW,
    OverlayState.TRIM,
    OverlayState.HEDGE,
    OverlayState.ACTIVE_PROTECTION,
    OverlayState.ARM_PROTECTION,
    OverlayState.STOP_ADD,
    OverlayState.TRIM_WATCH,
    OverlayState.WAIT,
)


class Track:
    EXTENSION: Final[str] = "EXTENSION"  # extension is the primary anticipatory trigger
    BREADTH_FLOW: Final[str] = "BREADTH_FLOW"  # breadth + reactive DP govern; ext only arms


class Overshoot:
    # SPEC v2 §3.2 (overshoot calibration) is unchanged. See the SPEC v2.1
    # additive amendment in ``atlas.core.overshoot_elasticity`` for the finer
    # Overshoot-Elasticity tiers that adjust +40 behaviour / trim-rung spacing.
    MASSIVE: Final[str] = "MASSIVE"  # +71% to +140% past the 50d before topping
    MODERATE: Final[str] = "MODERATE"  # +42% to +52%
    SHARP_FALLER: Final[str] = "SHARP_FALLER"  # tops ~+40-44%, +40 IS the trim line
    EXCLUDED: Final[str] = "EXCLUDED"  # squeeze artifact — do not calibrate
    UNKNOWN: Final[str] = "UNKNOWN"


class BreadthLevel:
    WATCH: Final[str] = "BREADTH_WATCH"
    HEDGE: Final[str] = "BREADTH_HEDGE"


# ---------------------------------------------------------------------------
# Editable configuration (§10 — every threshold a parameter)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WashoutConfig:
    """All overlay thresholds. Defaults are provisional (Edit 8)."""

    # Extension ladder lines (50d distance %, §3 / §10).
    stop_add_50d: float = 25.0
    arm_protection_50d: float = 40.0
    active_protection_50d: float = 60.0
    forced_derisk_50d: float = 80.0
    sharp_faller_trim_50d: float = 40.0

    # Breadth monitor (§5) — counts within the 32-name complex over 1-2 sessions.
    breadth_universe_size: int = 32
    breadth_watch_min: int = 8
    breadth_watch_max: int = 11
    breadth_watch_down_pct: float = 5.0
    breadth_hedge_min: int = 12
    breadth_hedge_down_pct: float = 7.0

    # Reactive DP confirmation (§6) + sell confirmation count (§7).
    reactive_dp_sell_pct: float = 80.0
    sell_confirmation_count: int = 2

    # Moderate metric legs (§10). 21d/14d/RSI count only when 50d >= mod_50d.
    mod_rsi: float = 75.0
    mod_21d: float = 25.0
    mod_14d: float = 20.0
    mod_20d: float = 15.0
    mod_50d: float = 25.0

    # Extreme metric legs (§10).
    ext_rsi: float = 80.0
    ext_21d: float = 35.0
    ext_20d: float = 20.0
    ext_50d: float = 40.0


DEFAULT_CONFIG: Final[WashoutConfig] = WashoutConfig()


# ---------------------------------------------------------------------------
# Per-name metadata (§2 tracks, §3.2 overshoot calibration)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NameMeta:
    """Per-name overlay tags. ``track`` wins over ``tier`` on conflict (§2)."""

    track: str
    tier: str
    overshoot: str
    peak_50d: float | None
    washout_count: int
    low_confidence: bool


# Curated from the spec. Names with <3 historical washouts (or not explicitly
# placed) default to the tier-implied track and are flagged low-confidence (§2).
_NAME_META: Final[dict[str, NameMeta]] = {
    # --- Extension-managed (§2) ---
    "SNDK": NameMeta(Track.EXTENSION, "overshooter", Overshoot.MASSIVE, 116.0, 3, False),
    "LITE": NameMeta(Track.EXTENSION, "overshooter", Overshoot.MASSIVE, 71.0, 3, False),
    "AAOI": NameMeta(Track.EXTENSION, "overshooter", Overshoot.MASSIVE, 140.0, 3, False),
    "COHR": NameMeta(Track.EXTENSION, "moderate", Overshoot.MODERATE, 43.0, 3, False),
    "ARM": NameMeta(Track.EXTENSION, "overshooter", Overshoot.MASSIVE, 100.0, 2, True),
    "MXL": NameMeta(Track.EXTENSION, "ext-predictive", Overshoot.EXCLUDED, 218.0, 1, True),
    "ONTO": NameMeta(Track.EXTENSION, "ext-predictive", Overshoot.UNKNOWN, None, 1, True),
    "TSEM": NameMeta(Track.EXTENSION, "moderate", Overshoot.MODERATE, 49.0, 2, True),
    "AMD": NameMeta(Track.EXTENSION, "overshooter", Overshoot.MASSIVE, 79.0, 2, True),
    # --- Breadth/Flow-managed (§2) ---
    "MU": NameMeta(Track.BREADTH_FLOW, "flow-driven", Overshoot.MASSIVE, 83.0, 3, False),
    "MRVL": NameMeta(Track.BREADTH_FLOW, "flow-driven", Overshoot.MASSIVE, 95.0, 3, False),
    "BE": NameMeta(Track.BREADTH_FLOW, "flow-driven", Overshoot.MASSIVE, 113.0, 2, True),
    "CLS": NameMeta(Track.BREADTH_FLOW, "flow-driven", Overshoot.MODERATE, 52.0, 3, False),
    "NBIS": NameMeta(Track.BREADTH_FLOW, "sharp-faller", Overshoot.SHARP_FALLER, 42.0, 3, False),
    "CRWV": NameMeta(Track.BREADTH_FLOW, "flow-driven", Overshoot.MASSIVE, 130.0, 1, True),
    "AVGO": NameMeta(Track.BREADTH_FLOW, "flow-driven", Overshoot.MODERATE, 42.0, 2, True),
    "CRDO": NameMeta(Track.BREADTH_FLOW, "flow-driven", Overshoot.MASSIVE, 76.0, 2, True),
    # --- Override case (§2): ext-predictive tier but breadth-managed; track wins ---
    "VICR": NameMeta(Track.BREADTH_FLOW, "ext-predictive", Overshoot.MASSIVE, 75.0, 1, True),
}

# Default for an unmapped ticker: extension-managed, unknown overshoot, flagged.
_DEFAULT_META: Final[NameMeta] = NameMeta(
    Track.EXTENSION, "unknown", Overshoot.UNKNOWN, None, 0, True
)


def name_meta(ticker: str) -> NameMeta:
    """Return curated metadata for *ticker*, or a low-confidence default."""
    return _NAME_META.get(ticker.upper(), _DEFAULT_META)


def all_name_meta() -> dict[str, NameMeta]:
    """All curated per-name metadata — for the Risk-exceptions view."""
    return dict(_NAME_META)


# ---------------------------------------------------------------------------
# Extension arming ladder (§3) + per-name overshoot nuance (§3.2)
# ---------------------------------------------------------------------------


def ladder_rung(dist_50d: float, overshoot: str, cfg: WashoutConfig = DEFAULT_CONFIG) -> str:
    """Map 50d distance to a ladder action label (§3).

    Sharp-faller names treat +40% as the trim/hedge line (§3.2); for all others
    +40% only ARMS protection. Returns the action label string.
    """
    if dist_50d >= cfg.forced_derisk_50d:
        return "Forced De-Risk Review"
    if dist_50d >= cfg.active_protection_50d:
        return "Active Protection"
    if overshoot == Overshoot.SHARP_FALLER and dist_50d >= cfg.sharp_faller_trim_50d:
        return "Trim/Hedge (sharp-faller line)"
    if dist_50d >= cfg.arm_protection_50d:
        return "Arm Protection"
    if dist_50d >= cfg.stop_add_50d:
        return "Stop-Add / No-Chase"
    return "No action"


# ---------------------------------------------------------------------------
# Metric legs (§10) — extension-severity classification (display/context only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricLegs:
    moderate: list[str]
    extreme: list[str]

    @property
    def moderate_count(self) -> int:
        return len(self.moderate)

    @property
    def extreme_count(self) -> int:
        return len(self.extreme)


def metric_legs(
    *,
    rsi14: float | None,
    move21: float | None,
    move14: float | None,
    move20: float | None,
    dist_50d: float | None,
    cfg: WashoutConfig = DEFAULT_CONFIG,
) -> MetricLegs:
    """Classify extension severity from RSI/move metrics (§10).

    Gating: 21d / 14d / RSI count toward the moderate set only when 50d >= 25%
    (a single hot RSI without underlying extension is not a leg).
    """
    gated = dist_50d is not None and dist_50d >= cfg.mod_50d

    moderate: list[str] = []
    if dist_50d is not None and dist_50d >= cfg.mod_50d:
        moderate.append("50d>=25%")
    if move20 is not None and move20 >= cfg.mod_20d:
        moderate.append("20d>=15%")
    if gated:
        if rsi14 is not None and rsi14 >= cfg.mod_rsi:
            moderate.append("RSI>=75")
        if move21 is not None and move21 >= cfg.mod_21d:
            moderate.append("21d>=25%")
        if move14 is not None and move14 >= cfg.mod_14d:
            moderate.append("14d>=20%")

    extreme: list[str] = []
    if dist_50d is not None and dist_50d >= cfg.ext_50d:
        extreme.append("50d>=40%")
    if move20 is not None and move20 >= cfg.ext_20d:
        extreme.append("20d>=20%")
    if rsi14 is not None and rsi14 >= cfg.ext_rsi:
        extreme.append("RSI>=80")
    if move21 is not None and move21 >= cfg.ext_21d:
        extreme.append("21d>=35%")

    return MetricLegs(moderate=moderate, extreme=extreme)


# ---------------------------------------------------------------------------
# Confirmation legs + trim authorization (§7) — share trims need a trigger
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfirmationLegs:
    """Behavioural confirmation legs (§7). 2-of-N authorizes a share trim."""

    flow_distribution: bool = False  # flow flips to distribution (DP sell% >= 80)
    vwap_lost: bool = False  # VWAP lost & not reclaimed on a CLOSING basis
    opening_range_fail: bool = False
    group_rolling: bool = False  # group rolling together (breadth)
    late_session_distribution: bool = False
    absorption: bool = False  # absorption without follow-through (§4)

    def count(self) -> int:
        return sum(
            (
                self.flow_distribution,
                self.vwap_lost,
                self.opening_range_fail,
                self.group_rolling,
                self.late_session_distribution,
                self.absorption,
            )
        )

    def present(self) -> list[str]:
        names = (
            ("flow_distribution", self.flow_distribution),
            ("vwap_lost", self.vwap_lost),
            ("opening_range_fail", self.opening_range_fail),
            ("group_rolling", self.group_rolling),
            ("late_session_distribution", self.late_session_distribution),
            ("absorption", self.absorption),
        )
        return [n for n, present in names if present]


def trim_authorized(
    *,
    legs: ConfirmationLegs,
    negative_catalyst: bool,
    hard_override: bool,
    cfg: WashoutConfig = DEFAULT_CONFIG,
) -> bool:
    """A share trim is authorized only with a real trigger (§7, Edit 9).

    Any one of: >= sell_confirmation_count behavioural legs, OR a negative
    catalyst, OR a hard override (confirmed close back below 20d/50d, or the
    Jun-5 four-condition trigger). RSI / 50d distance ALONE never authorize a
    trim. Position size is a GATE handled separately (§3.1): an at/above-target
    position may be trimmed when triggered; a below-target one never is.
    """
    return (
        legs.count() >= cfg.sell_confirmation_count or negative_catalyst or hard_override
    )


# ---------------------------------------------------------------------------
# Breadth monitor (§5) — two levels over the 32-name complex
# ---------------------------------------------------------------------------


def breadth_level(
    *,
    count_down_watch: int,
    count_down_hedge: int,
    cfg: WashoutConfig = DEFAULT_CONFIG,
) -> str | None:
    """Return the breadth level (§5).

    ``count_down_watch``  = names down within the watch band (-5 to -7%).
    ``count_down_hedge``  = names down by the hedge threshold (-7%+).
    The hedge trigger takes priority over watch.
    """
    if count_down_hedge >= cfg.breadth_hedge_min:
        return BreadthLevel.HEDGE
    if count_down_watch >= cfg.breadth_watch_min:
        return BreadthLevel.WATCH
    return None


# ---------------------------------------------------------------------------
# Master resolver (§9) — nine states with precedence + §3.1 size re-labeling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WashoutInputs:
    """Measured inputs assembled by the service."""

    ticker: str
    dist_50d: float | None
    rsi14: float | None = None
    move21: float | None = None
    move14: float | None = None
    move20: float | None = None
    # Position sizing (§3.1). below_target=None means "unknown" → no re-label.
    below_target: bool | None = None
    at_or_above_target: bool = False
    # Confirmation / catalysts (§7).
    confirmation: ConfirmationLegs = field(default_factory=ConfirmationLegs)
    negative_catalyst: bool = False
    hard_override: bool = False
    absorption: bool = False
    # Macro (§5).
    breadth: str | None = None
    data_ok: bool = True


@dataclass(frozen=True)
class WashoutResult:
    state: str
    track: str
    overshoot: str
    rung: str
    trim_authorized: bool
    confirmation_count: int
    confirmation_present: list[str]
    metric_legs: MetricLegs
    breadth: str | None
    low_confidence: bool
    size_relabeled: bool
    reason: str


def resolve_overlay(inp: WashoutInputs, cfg: WashoutConfig = DEFAULT_CONFIG) -> WashoutResult:
    """Resolve the nine-state posture for a single name (§9).

    Order of operations: build candidate states, apply the §3.1 size re-label
    (below-target → trim states become Stop-Add) BEFORE precedence, then pick
    the highest-precedence state.
    """
    meta = name_meta(inp.ticker)
    legs = metric_legs(
        rsi14=inp.rsi14,
        move21=inp.move21,
        move14=inp.move14,
        move20=inp.move20,
        dist_50d=inp.dist_50d,
        cfg=cfg,
    )

    # Data gap → WAIT (Edit: never act on unverifiable data).
    if not inp.data_ok or inp.dist_50d is None:
        return WashoutResult(
            state=OverlayState.WAIT,
            track=meta.track,
            overshoot=meta.overshoot,
            rung="No action",
            trim_authorized=False,
            confirmation_count=inp.confirmation.count(),
            confirmation_present=inp.confirmation.present(),
            metric_legs=legs,
            breadth=inp.breadth,
            low_confidence=meta.low_confidence,
            size_relabeled=False,
            reason="Live data could not be verified — no action.",
        )

    dist = inp.dist_50d
    rung = ladder_rung(dist, meta.overshoot, cfg)
    authorized = trim_authorized(
        legs=inp.confirmation,
        negative_catalyst=inp.negative_catalyst,
        hard_override=inp.hard_override,
        cfg=cfg,
    )

    candidates: set[str] = set()

    # Book-level hedge (§5) — independent of any single name.
    if inp.breadth == BreadthLevel.HEDGE:
        candidates.add(OverlayState.BOOK_LEVEL_HEDGE)

    # Extension ladder (§3).
    if dist >= cfg.stop_add_50d:
        candidates.add(OverlayState.STOP_ADD)
    if dist >= cfg.arm_protection_50d:
        candidates.add(OverlayState.ARM_PROTECTION)
    if dist >= cfg.active_protection_50d:
        candidates.add(OverlayState.ACTIVE_PROTECTION)
    if dist >= cfg.forced_derisk_50d:
        candidates.add(OverlayState.FORCED_DE_RISK_REVIEW)

    # Single-name hedge (§4 absorption, or sharp-faller at its trim line).
    sharp_at_line = meta.overshoot == Overshoot.SHARP_FALLER and dist >= cfg.sharp_faller_trim_50d
    if inp.absorption or sharp_at_line:
        candidates.add(OverlayState.HEDGE)

    # Trim authorization (§7) — never extension alone.
    if authorized:
        candidates.add(OverlayState.TRIM)

    # Trim-watch: one leg forming, or +60 on an at-target position not yet authorized.
    one_leg_forming = 0 < inp.confirmation.count() < cfg.sell_confirmation_count
    near_trim_at_target = (
        dist >= cfg.active_protection_50d and inp.at_or_above_target and not authorized
    )
    if one_leg_forming or near_trim_at_target:
        candidates.add(OverlayState.TRIM_WATCH)

    if not candidates:
        candidates.add(OverlayState.WAIT)

    state = next(s for s in _STATE_PRECEDENCE if s in candidates)

    # §3.1 size re-label: a below-target position can never be trimmed — any trim
    # state (TRIM, FORCED_DE_RISK, or ACTIVE_PROTECTION's trim tranche) displays
    # as Stop-Add / Pullback-Only instead. Book-level hedge and single-name HEDGE
    # (buying protection, not selling) are unaffected.
    size_relabeled = False
    if inp.below_target and state in (
        OverlayState.TRIM,
        OverlayState.FORCED_DE_RISK_REVIEW,
        OverlayState.ACTIVE_PROTECTION,
    ):
        state = OverlayState.STOP_ADD
        size_relabeled = True
    reason = _reason_for(state, inp, meta, dist, authorized, size_relabeled, cfg)

    return WashoutResult(
        state=state,
        track=meta.track,
        overshoot=meta.overshoot,
        rung=rung,
        trim_authorized=authorized and not size_relabeled,
        confirmation_count=inp.confirmation.count(),
        confirmation_present=inp.confirmation.present(),
        metric_legs=legs,
        breadth=inp.breadth,
        low_confidence=meta.low_confidence,
        size_relabeled=size_relabeled,
        reason=reason,
    )


def _reason_for(
    state: str,
    inp: WashoutInputs,
    meta: NameMeta,
    dist: float,
    authorized: bool,
    size_relabeled: bool,
    cfg: WashoutConfig,
) -> str:
    """Plain-English rationale for the resolved state."""
    if size_relabeled:
        return "Position below target — trim states re-labeled to Stop-Add / Pullback-Only (§3.1)."
    reasons = {
        OverlayState.BOOK_LEVEL_HEDGE: "Breadth hedge trigger — index hedge the whole book (§5).",
        OverlayState.FORCED_DE_RISK_REVIEW: (
            f"+{dist:.0f}% over 50d — forced de-risk review unless flow/catalyst supportive (§3)."
        ),
        OverlayState.TRIM: "Trim authorized — a real trigger is present (§7).",
        OverlayState.HEDGE: "Single-name defined-risk hedge — absorption / escalation (§4).",
        OverlayState.ACTIVE_PROTECTION: (
            f"+{dist:.0f}% over 50d — tighten hedge; trim only if at/above target (§3.1)."
        ),
        OverlayState.ARM_PROTECTION: f"+{dist:.0f}% over 50d — arm defined-risk; trim 0% (§3).",
        OverlayState.STOP_ADD: f"+{dist:.0f}% over 50d — stop adding / no chase (§3).",
        OverlayState.TRIM_WATCH: "Confirmation forming — monitor for the 2nd leg (§7).",
        OverlayState.WAIT: "No condition met.",
    }
    base = reasons.get(state, "")
    if meta.track == Track.BREADTH_FLOW and state in (
        OverlayState.ARM_PROTECTION,
        OverlayState.ACTIVE_PROTECTION,
    ):
        base += " Breadth/Flow name — extension only arms; sell needs breadth + DP (§2)."
    return base
