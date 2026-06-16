"""Overshoot Elasticity — SPEC v2.1 additive amendment to the Extension &
Washout Overlay.

A sub-module of the overlay ONLY. Hard constraints (from the amendment):
  * No coupling to F1-F5 (this module reads price/flow-derived inputs only).
  * Does NOT replace Track — Track still wins (handled in the engine).
  * The position-size rule (§3.1) still governs add/trim eligibility.
  * Elasticity ONLY adjusts protection sizing, no-chase severity, trim-rung
    spacing, and core/satellite/tactical sizing. It never changes the resolved
    9-state precedence, the track, or the size gate.

It refines the v2 "+40 arms protection" line: in v2.1 the +40 *behaviour*
depends on a name's overshoot elasticity tier (how far past the 50-day it tends
to run before topping):

  Tier          +40 behaviour
  Extreme       protect only
  High          protect + stop-add
  Moderate      protect; trim-watch near +55/+60
  Low           trim-watch
  Sharp-Faller  trim-line / hedge-line
  Never-Cross   abnormal extension -> trim-watch / active-protection review

Constants are provisional (paper-trade + quarterly recompute), exposed via
``ElasticityConfig``. Per-name overrides come from the audit sheet (A4); the
explicit ones are encoded here and flagged.

NOTE: SPEC v2 §3.2 is unchanged by this amendment except for a cross-reference
(see ``atlas.core.extension_washout``); the elasticity tiers live here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from atlas.core.extension_washout import OverlayState


class ElasticityTier:
    EXTREME: Final[str] = "EXTREME"
    HIGH: Final[str] = "HIGH"
    MODERATE: Final[str] = "MODERATE"
    LOW: Final[str] = "LOW"
    SHARP_FALLER: Final[str] = "SHARP_FALLER"
    NEVER_CROSS: Final[str] = "NEVER_CROSS"
    ANOMALY: Final[str] = "ANOMALY"
    UNKNOWN: Final[str] = "UNKNOWN"


class Confidence:
    HIGH: Final[str] = "HIGH"
    MODERATE: Final[str] = "MODERATE"
    LOW: Final[str] = "LOW"


# ---------------------------------------------------------------------------
# Editable configuration (all provisional)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElasticityConfig:
    # score -> tier thresholds (0-100 elasticity score)
    extreme_min: float = 82.0
    high_min: float = 66.0
    moderate_min: float = 42.0

    # Realized-vol (annualized %) -> base vol component of the score.
    rv_low: float = 35.0  # below -> minimal elasticity
    rv_mid: float = 60.0
    rv_high: float = 90.0
    rv_extreme: float = 120.0

    # Beta / momentum / burner adjustments.
    beta_high: float = 1.5
    beta_extreme: float = 2.0
    beta_low: float = 0.8
    mom_strong: float = 30.0
    mom_extreme: float = 50.0
    burner_rv_ratio: float = 1.6  # rv20 > ratio*rv60 -> burning hot

    # Confidence from historical washout/overshoot event count.
    confidence_high_events: int = 3
    confidence_mod_events: int = 2

    # Trim-rung spacing per tier (50d %). Higher elasticity -> trims pushed out.
    ladder_extreme: tuple[float, float, float] = (40.0, 65.0, 85.0)  # arm, active, forced
    ladder_high: tuple[float, float, float] = (40.0, 60.0, 80.0)
    ladder_moderate: tuple[float, float, float] = (40.0, 55.0, 75.0)
    ladder_low: tuple[float, float, float] = (40.0, 50.0, 70.0)
    ladder_sharp: tuple[float, float, float] = (40.0, 48.0, 60.0)
    ladder_never: tuple[float, float, float] = (40.0, 50.0, 70.0)
    ladder_default: tuple[float, float, float] = (40.0, 60.0, 80.0)


DEFAULT_ELASTICITY_CONFIG: Final[ElasticityConfig] = ElasticityConfig()


# ---------------------------------------------------------------------------
# +40 behaviour table (the amendment's headline) — display guidance per tier
# ---------------------------------------------------------------------------

# (recommended posture state at +40, plain-English label). The resolved 9-state
# still follows the (elasticity-spaced) ladder + precedence; this is the posture
# guidance the operator reads at the +40 rung.
_PLUS40_BEHAVIOUR: Final[dict[str, tuple[str, str]]] = {
    ElasticityTier.EXTREME: (OverlayState.ARM_PROTECTION, "protect only"),
    ElasticityTier.HIGH: (OverlayState.ARM_PROTECTION, "protect + stop-add"),
    ElasticityTier.MODERATE: (OverlayState.ARM_PROTECTION, "protect; trim-watch near +55/+60"),
    ElasticityTier.LOW: (OverlayState.TRIM_WATCH, "trim-watch"),
    ElasticityTier.SHARP_FALLER: (OverlayState.HEDGE, "trim-line / hedge-line"),
    ElasticityTier.NEVER_CROSS: (
        OverlayState.ACTIVE_PROTECTION,
        "abnormal extension -> trim-watch / active-protection review",
    ),
    ElasticityTier.ANOMALY: (OverlayState.ARM_PROTECTION, "anomaly -> manual review"),
    ElasticityTier.UNKNOWN: (OverlayState.ARM_PROTECTION, "arm protection (default)"),
}

# Core / satellite / tactical sizing guidance per tier (display only).
_SIZING_GUIDANCE: Final[dict[str, str]] = {
    ElasticityTier.EXTREME: "Core-size; push trim tranches to +70/+80; widest no-chase band.",
    ElasticityTier.HIGH: "Core-size; protect + stop-add; trims +60/+70.",
    ElasticityTier.MODERATE: "Core/satellite; first trim tranche +55-60.",
    ElasticityTier.LOW: "Satellite-size; act early — little overshoot cushion.",
    ElasticityTier.SHARP_FALLER: "Tactical-size; +40 is the trim/hedge line.",
    ElasticityTier.NEVER_CROSS: "Tactical-size; +40 is abnormal — review thesis.",
    ElasticityTier.ANOMALY: "Excluded from auto-recalibration; manual sizing only.",
    ElasticityTier.UNKNOWN: "Default sizing; low confidence.",
}


# ---------------------------------------------------------------------------
# Per-name overrides (audit sheet A4). Track is unaffected (see engine).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NameElasticity:
    override_tier: str | None
    provisional: bool = False
    watch_promote: bool = False
    exclude_recalibration: bool = False
    hard_override: bool = False
    burner: bool = False
    note: str = ""


# Wafer-Fab-Equipment cohort treated as Never-Cross / anomaly (rarely cross +40;
# when they do it is abnormal). NOTE: this membership is an implementation
# assumption pending the A4 sheet — confirm/extend the list there.
_WFE_NAMES: Final[tuple[str, ...]] = (
    "AMAT", "LRCX", "KLAC", "ASML", "TER", "ONTO", "UCTT", "ICHR", "AEHR", "COHU", "ACLS",
)

# Per-name treatment is a DAILY LIVE-FLOW SNAPSHOT, not permanent (SPEC v2.2 lock):
# the live elasticity score (rv/beta/momentum) drives the tier when inputs exist;
# these entries are seeds/overrides re-checked each recompute. Calibration-excluded
# names (exclude_recalibration=True) are held out of automated recalibration only.
_NAME_ELASTICITY: Final[dict[str, NameElasticity]] = {
    # Hard override: NBIS is a Sharp-Faller; +40 = trim/hedge line.
    "NBIS": NameElasticity(
        ElasticityTier.SHARP_FALLER, hard_override=True, note="Sharp-faller (A4)"
    ),
    # ANET + the WFE cohort: Never-Cross / Anomaly.
    "ANET": NameElasticity(ElasticityTier.NEVER_CROSS, note="Never-cross (A4)"),
    # MXL: anomaly — excluded from automated recalibration unless manually included.
    "MXL": NameElasticity(
        ElasticityTier.ANOMALY, exclude_recalibration=True, note="Squeeze artifact (+218) — anomaly"
    ),
    # DELL: Moderate-Provisional / Watch-Promote (n=3 but peaks ran hotter than tier).
    "DELL": NameElasticity(
        ElasticityTier.MODERATE,
        provisional=True,
        watch_promote=True,
        note="n=3; historical peaks hotter than tier — watch-promote",
    ),
    # SNDK: calibration-excluded pending corporate-action reconciliation (SPEC v2.2
    # lock). Tier still resolves from live/peak; just not used for auto-recalibration.
    "SNDK": NameElasticity(
        override_tier=None,
        exclude_recalibration=True,
        note="calibration-excluded pending corporate-action reconciliation (v2.2)",
    ),
    **{n: NameElasticity(ElasticityTier.NEVER_CROSS, note="WFE cohort (A4)") for n in _WFE_NAMES},
}


def name_elasticity(ticker: str) -> NameElasticity | None:
    return _NAME_ELASTICITY.get(ticker.upper())


def all_overrides() -> dict[str, NameElasticity]:
    """All per-name elasticity overrides (A4) — for the Risk-exceptions view."""
    return dict(_NAME_ELASTICITY)


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElasticityInputs:
    rv20: float | None = None  # annualized realized vol, 20d (%)
    rv60: float | None = None  # annualized realized vol, 60d (%)
    beta: float | None = None
    mom21: float | None = None  # 21-day momentum / return (%)
    burner: bool = False


@dataclass(frozen=True)
class ElasticityResult:
    score: int | None
    tier: str
    confidence: str
    event_count: int
    plus40_state: str
    plus40_label: str
    ladder: tuple[float, float, float]  # arm, active, forced (50d %)
    sizing_guidance: str
    provisional: bool
    watch_promote: bool
    exclude_recalibration: bool
    hard_override: bool
    burner: bool
    data_gaps: list[str]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _vol_component(rv60: float, cfg: ElasticityConfig) -> float:
    """Map baseline realized vol (rv60) to a 0-100 elasticity base."""
    if rv60 >= cfg.rv_extreme:
        return 95.0
    if rv60 >= cfg.rv_high:
        return 80.0
    if rv60 >= cfg.rv_mid:
        return 58.0
    if rv60 >= cfg.rv_low:
        return 35.0
    return 12.0


def elasticity_score(inputs: ElasticityInputs, cfg: ElasticityConfig) -> int | None:
    """0-100 elasticity score from live inputs. None when rv60 is unavailable."""
    if inputs.rv60 is None:
        return None
    score = _vol_component(inputs.rv60, cfg)

    if inputs.beta is not None:
        if inputs.beta >= cfg.beta_extreme:
            score += 15
        elif inputs.beta >= cfg.beta_high:
            score += 8
        elif inputs.beta < cfg.beta_low:
            score -= 10

    if inputs.mom21 is not None:
        if inputs.mom21 >= cfg.mom_extreme:
            score += 12
        elif inputs.mom21 >= cfg.mom_strong:
            score += 6

    # Burner: rv20 spiking far above rv60, or an explicit flag.
    burning = inputs.burner or (
        inputs.rv20 is not None
        and inputs.rv60 is not None
        and inputs.rv60 > 0
        and inputs.rv20 > cfg.burner_rv_ratio * inputs.rv60
    )
    if burning:
        score += 12

    return max(0, min(100, round(score)))


def classify_tier(score: int, cfg: ElasticityConfig) -> str:
    if score >= cfg.extreme_min:
        return ElasticityTier.EXTREME
    if score >= cfg.high_min:
        return ElasticityTier.HIGH
    if score >= cfg.moderate_min:
        return ElasticityTier.MODERATE
    return ElasticityTier.LOW


def _tier_from_peak(peak_50d: float | None) -> str:
    """Fallback tier from the historical peak-50d when live inputs are missing."""
    if peak_50d is None:
        return ElasticityTier.UNKNOWN
    if peak_50d >= 100:
        return ElasticityTier.EXTREME
    if peak_50d >= 66:
        return ElasticityTier.HIGH
    if peak_50d >= 42:
        return ElasticityTier.MODERATE
    return ElasticityTier.LOW


def _ladder_for(tier: str, cfg: ElasticityConfig) -> tuple[float, float, float]:
    return {
        ElasticityTier.EXTREME: cfg.ladder_extreme,
        ElasticityTier.HIGH: cfg.ladder_high,
        ElasticityTier.MODERATE: cfg.ladder_moderate,
        ElasticityTier.LOW: cfg.ladder_low,
        ElasticityTier.SHARP_FALLER: cfg.ladder_sharp,
        ElasticityTier.NEVER_CROSS: cfg.ladder_never,
    }.get(tier, cfg.ladder_default)


def _confidence(event_count: int, score_available: bool, cfg: ElasticityConfig) -> str:
    if event_count >= cfg.confidence_high_events and score_available:
        return Confidence.HIGH
    if event_count >= cfg.confidence_mod_events:
        return Confidence.MODERATE
    return Confidence.LOW


def compute_elasticity(
    ticker: str,
    inputs: ElasticityInputs,
    *,
    peak_50d: float | None = None,
    event_count: int = 0,
    extra_data_gaps: list[str] | None = None,
    cfg: ElasticityConfig = DEFAULT_ELASTICITY_CONFIG,
) -> ElasticityResult:
    """Resolve the overshoot-elasticity tier + recommended posture for a name.

    Precedence: per-name override (A4) > live-score tier > historical-peak
    fallback. Overrides never change Track or the size gate.
    """
    override = name_elasticity(ticker)
    score = elasticity_score(inputs, cfg)

    data_gaps = list(extra_data_gaps or [])
    if score is None:
        data_gaps.append("ELASTICITY_INPUTS")

    if override is not None and override.override_tier is not None:
        tier = override.override_tier
    elif score is not None:
        tier = classify_tier(score, cfg)
    else:
        tier = _tier_from_peak(peak_50d)

    plus40_state, plus40_label = _PLUS40_BEHAVIOUR.get(
        tier, _PLUS40_BEHAVIOUR[ElasticityTier.UNKNOWN]
    )

    return ElasticityResult(
        score=score,
        tier=tier,
        confidence=_confidence(event_count, score is not None, cfg),
        event_count=event_count,
        plus40_state=plus40_state,
        plus40_label=plus40_label,
        ladder=_ladder_for(tier, cfg),
        sizing_guidance=_SIZING_GUIDANCE.get(tier, _SIZING_GUIDANCE[ElasticityTier.UNKNOWN]),
        provisional=bool(override and override.provisional),
        watch_promote=bool(override and override.watch_promote),
        exclude_recalibration=bool(override and override.exclude_recalibration),
        hard_override=bool(override and override.hard_override),
        burner=inputs.burner,
        data_gaps=data_gaps,
    )
