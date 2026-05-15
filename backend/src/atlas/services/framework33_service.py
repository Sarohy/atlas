"""Framework 33 — LEAPS Entry Conditions V2.

Three purely functional entry gates for LEAPS positions:

  Condition A — Calm Accumulation:
      Ticker is ≥ 20% below its all-time high AND VIX is in the calm
      15-18 range (fear has settled; accumulate into the dip quietly).

  Condition B — Washout:
      Sector is ≥ 25% below its peak AND confirmed capitulation volume
      has printed AND VIX is elevated but DECLINING from its recent
      peak (panic has peaked; the washout is over).

  Condition C — Bull Market Path:
      T1E composite score ≥ 85 AND dark pool flow is bullish AND options
      flow confirms bullish positioning AND no large overnight gap today.
      Enables LEAPS entry in a rising market without requiring a crash.

Position sizing:
  - Standard: 0.3-1.0% of total portfolio per name.
  - F30 drawdown-gate active (NAV 15-25% below 90-day peak): hard cap
    at 0.5% per name.
  - AND gate: entries above $10 000 require CLEAR regime + F29 3-of-5
    signals (caller is responsible for evaluating the gate; pass the
    result via ``and_gate_passed``).

Static exclusions (OTC / foreign / thin US options chains):
  SIVE, IQE, ALRIB, SHUNSIN, POET.
  SNDK is excluded dynamically via the IV-block threshold (handled by
  the LEAPS service, not here).

All functions are pure — no I/O, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tickers permanently excluded from LEAPS (OTC or foreign listings without
# liquid US options chains).
_EXCLUDED_TICKERS: Final[frozenset[str]] = frozenset(
    {"SIVE", "IQE", "ALRIB", "SHUNSIN", "POET"}
)

# Condition A thresholds
_COND_A_DRAWDOWN_MIN_PCT: Final[float] = 20.0  # ≥20% drawdown from ATH
_COND_A_VIX_LOW: Final[float] = 15.0  # VIX calm range lower bound
_COND_A_VIX_HIGH: Final[float] = 18.0  # VIX calm range upper bound

# Condition B thresholds
_COND_B_SECTOR_DRAWDOWN_MIN_PCT: Final[float] = 25.0  # ≥25% sector drawdown

# Size guidance — percentage of total NAV per position name
_SIZE_STANDARD_MAX_PCT: Final[float] = 1.0  # Maximum per name (no gate)
_SIZE_STANDARD_BASELINE_PCT: Final[float] = 0.3  # Lower end of baseline range (no gate)
# Upper end of baseline range (spec: 0.3-0.75% per name)
_SIZE_STANDARD_BASELINE_MAX_PCT: Final[float] = 0.75
_SIZE_CARVEOUT_MAX_PCT: Final[float] = 0.5  # Max per name under F30 drawdown gate

# AND gate threshold — entries above this amount require the AND gate
_AND_GATE_THRESHOLD_USD: Final[float] = 10_000.0

# Condition C — Bull Market Path thresholds
# Minimum T1E (Framework 1 Earnings / composite) score to qualify
_COND_C_T1E_MIN_SCORE: Final[int] = 85  # score out of 100


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SizeGuidance:
    """Per-name position size guidance based on F30 drawdown gate state."""

    standard_max_pct: float
    """Maximum allocation per name as % of NAV."""

    baseline_pct: float
    """Lower end of suggested baseline range per name as % of NAV."""

    baseline_max_pct: float
    """Upper end of suggested baseline range per name as % of NAV (spec: 0.3-0.75%)."""

    carveout_active: bool
    """True when F30 drawdown gate forces the 0.5% carveout cap."""

    data_missing: bool = False
    """True when F30 gate state was unknown; conservative cap was applied."""


@dataclass(frozen=True)
class ConditionAResult:
    """Result of the Calm Accumulation entry gate evaluation."""

    confirmed: bool | None
    """True = qualifies; False = does not qualify; None = data unavailable."""

    drawdown_qualifies: bool
    """True when drawdown_from_high_pct ≥ 20%."""

    vix_in_calm_range: bool
    """True when VIX is in the 15-18 calm window."""

    data_missing: bool
    """True when one or more required inputs were None."""

    detail: str
    """Human-readable status summary."""


@dataclass(frozen=True)
class ConditionBResult:
    """Result of the Washout entry gate evaluation."""

    confirmed: bool | None
    """True = qualifies; False = does not qualify; None = data unavailable."""

    sector_drawdown_qualifies: bool
    """True when sector_drawdown_pct ≥ 25%."""

    capitulation_volume_confirmed: bool | None
    """Whether confirmed capitulation volume was reported by caller."""

    vix_elevated: bool | None
    """Whether VIX is currently elevated, as reported by caller."""

    vix_declining: bool | None
    """True when VIX is declining from its recent peak (fear has peaked)."""

    data_missing: bool
    """True when one or more required inputs were None."""

    detail: str
    """Human-readable status summary."""


@dataclass(frozen=True)
class ConditionCResult:
    """Result of the Bull Market Path entry gate evaluation."""

    confirmed: bool | None
    """True = qualifies; False = does not qualify; None = data unavailable."""

    t1e_qualifies: bool
    """True when t1e_score >= _COND_C_T1E_MIN_SCORE."""

    dark_pool_bullish: bool | None
    """Whether dark pool flow is directionally bullish (caller-evaluated)."""

    options_flow_bullish: bool | None
    """Whether options flow is bullish (caller-evaluated from F4 score)."""

    no_gap_day: bool | None
    """True when there is no large overnight gap in the ticker today."""

    data_missing: bool
    """True when one or more required inputs were None."""

    detail: str
    """Human-readable status summary."""


@dataclass(frozen=True)
class F33EntryResult:
    """Composite F33 entry evaluation result."""

    qualifies: bool | None
    """True = entry permitted; False = blocked; None = data unavailable."""

    qualifying_condition: str | None
    """'A', 'B', 'C', or None when not qualifying. A takes precedence."""

    excluded: bool
    """True when ticker is on the static exclusion list."""

    data_missing: bool
    """True when critical inputs were missing and a decision cannot be made."""

    and_gate_required: bool
    """True when the entry exceeds $10 K AND the AND gate was not passed."""

    block_reason: str | None
    """Explanation when qualifies is False."""

    size_guidance: SizeGuidance
    """Per-name sizing recommendation."""

    condition_a: ConditionAResult
    """Detailed Condition A sub-evaluation."""

    condition_b: ConditionBResult
    """Detailed Condition B sub-evaluation."""

    condition_c: ConditionCResult
    """Detailed Condition C (Bull Market Path) sub-evaluation."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_excluded_ticker(ticker: str) -> bool:
    """Return True when *ticker* is on the static LEAPS exclusion list.

    Comparison is case-insensitive.
    """
    return ticker.upper() in _EXCLUDED_TICKERS


def evaluate_condition_a(
    drawdown_from_high_pct: float | None,
    vix_current: float | None,
) -> ConditionAResult:
    """Evaluate Condition A — Calm Accumulation.

    Parameters
    ----------
    drawdown_from_high_pct:
        Current drawdown from the ticker's all-time high (positive number, e.g.
        ``22.0`` means 22% below ATH).  Pass ``None`` when unavailable.
    vix_current:
        Most recent VIX closing level.  Pass ``None`` when unavailable.

    Returns
    -------
    ConditionAResult
        ``confirmed`` is ``None`` when either input is ``None``.
    """
    if drawdown_from_high_pct is None or vix_current is None:
        return ConditionAResult(
            confirmed=None,
            drawdown_qualifies=False,
            vix_in_calm_range=False,
            data_missing=True,
            detail="Data unavailable — drawdown or VIX missing",
        )

    drawdown_qualifies = drawdown_from_high_pct >= _COND_A_DRAWDOWN_MIN_PCT
    vix_in_calm_range = _COND_A_VIX_LOW <= vix_current <= _COND_A_VIX_HIGH
    confirmed = drawdown_qualifies and vix_in_calm_range

    if confirmed:
        detail = (
            f"Calm Accumulation: drawdown={drawdown_from_high_pct:.1f}% "
            f"(≥{_COND_A_DRAWDOWN_MIN_PCT}%) and VIX={vix_current:.1f} "
            f"in [{_COND_A_VIX_LOW}, {_COND_A_VIX_HIGH}]"
        )
    else:
        reasons: list[str] = []
        if not drawdown_qualifies:
            reasons.append(
                f"drawdown {drawdown_from_high_pct:.1f}% < {_COND_A_DRAWDOWN_MIN_PCT}%"
            )
        if not vix_in_calm_range:
            reasons.append(
                f"VIX {vix_current:.1f} outside [{_COND_A_VIX_LOW}, {_COND_A_VIX_HIGH}]"
            )
        detail = "Not met: " + "; ".join(reasons)

    return ConditionAResult(
        confirmed=confirmed,
        drawdown_qualifies=drawdown_qualifies,
        vix_in_calm_range=vix_in_calm_range,
        data_missing=False,
        detail=detail,
    )


def evaluate_condition_b(
    sector_drawdown_pct: float | None,
    capitulation_volume_confirmed: bool | None,
    vix_elevated: bool | None,
    vix_declining_from_peak: bool | None,
) -> ConditionBResult:
    """Evaluate Condition B — Washout.

    All four criteria must be True for the condition to be confirmed.  If
    any input is ``None`` the result is ``confirmed=None`` (data unavailable).

    Parameters
    ----------
    sector_drawdown_pct:
        Sector-level drawdown from its peak (positive %, e.g. ``30.0``).
    capitulation_volume_confirmed:
        Whether a capitulation-volume event has been confirmed by the caller.
    vix_elevated:
        Whether VIX is currently at an elevated level (caller-defined).
    vix_declining_from_peak:
        True when VIX is declining from its most recent multi-week peak
        (fear has peaked; panic is subsiding).  Pass False when VIX is still
        climbing.
    """
    if any(
        v is None
        for v in (
            sector_drawdown_pct,
            capitulation_volume_confirmed,
            vix_elevated,
            vix_declining_from_peak,
        )
    ):
        return ConditionBResult(
            confirmed=None,
            sector_drawdown_qualifies=False,
            capitulation_volume_confirmed=capitulation_volume_confirmed,
            vix_elevated=vix_elevated,
            vix_declining=vix_declining_from_peak,
            data_missing=True,
            detail="Data unavailable — one or more inputs missing",
        )

    sector_drawdown_qualifies = sector_drawdown_pct >= _COND_B_SECTOR_DRAWDOWN_MIN_PCT  # type: ignore[operator]
    confirmed = bool(
        sector_drawdown_qualifies
        and capitulation_volume_confirmed
        and vix_elevated
        and vix_declining_from_peak
    )

    if confirmed:
        detail = (
            f"Washout: sector drawdown={sector_drawdown_pct:.1f}% "
            f"(≥{_COND_B_SECTOR_DRAWDOWN_MIN_PCT}%), cap-volume confirmed, "
            "VIX elevated and declining"
        )
    else:
        reasons: list[str] = []
        if not sector_drawdown_qualifies:
            reasons.append(
                f"sector drawdown {sector_drawdown_pct:.1f}% < "
                f"{_COND_B_SECTOR_DRAWDOWN_MIN_PCT}%"
            )
        if not capitulation_volume_confirmed:
            reasons.append("capitulation volume not confirmed")
        if not vix_elevated:
            reasons.append("VIX not elevated")
        if not vix_declining_from_peak:
            reasons.append("VIX still climbing (fear not peaked)")
        detail = "Not met: " + "; ".join(reasons)

    return ConditionBResult(
        confirmed=confirmed,
        sector_drawdown_qualifies=sector_drawdown_qualifies,
        capitulation_volume_confirmed=capitulation_volume_confirmed,
        vix_elevated=vix_elevated,
        vix_declining=vix_declining_from_peak,
        data_missing=False,
        detail=detail,
    )


def evaluate_condition_c(
    t1e_score: int | None,
    dark_pool_bullish: bool | None,
    options_flow_bullish: bool | None,
    no_gap_day: bool | None,
) -> ConditionCResult:
    """Evaluate Condition C — Bull Market Path.

    All four criteria must be True for the condition to be confirmed.
    If any input is ``None`` the result is ``confirmed=None`` (data unavailable).

    This condition enables LEAPS entry in a rising market without requiring a
    crash or drawdown.  It requires high-conviction momentum signals:
      • T1E composite score ≥ 85 — strong fundamental + technical setup
      • Dark pool flow bullish — institutional accumulation confirmed
      • Options flow bullish — smart-money call activity confirmed (F4)
      • No gap day — ticker opened without a large overnight gap (gaps
        distort entry prices and make option pricing unreliable)

    Pure function — no I/O.
    """
    if any(
        v is None
        for v in (t1e_score, dark_pool_bullish, options_flow_bullish, no_gap_day)
    ):
        return ConditionCResult(
            confirmed=None,
            t1e_qualifies=False,
            dark_pool_bullish=dark_pool_bullish,
            options_flow_bullish=options_flow_bullish,
            no_gap_day=no_gap_day,
            data_missing=True,
            detail="Data unavailable — one or more inputs missing",
        )

    t1e_qualifies = t1e_score >= _COND_C_T1E_MIN_SCORE  # type: ignore[operator]
    confirmed = bool(
        t1e_qualifies
        and dark_pool_bullish
        and options_flow_bullish
        and no_gap_day
    )

    if confirmed:
        detail = (
            f"Bull Market Path: T1E={t1e_score} (≥{_COND_C_T1E_MIN_SCORE}), "
            "dark pool bullish, options flow bullish, no gap day"
        )
    else:
        reasons: list[str] = []
        if not t1e_qualifies:
            reasons.append(
                f"T1E score {t1e_score} < {_COND_C_T1E_MIN_SCORE}"
            )
        if not dark_pool_bullish:
            reasons.append("dark pool flow not bullish")
        if not options_flow_bullish:
            reasons.append("options flow not bullish")
        if not no_gap_day:
            reasons.append("gap day detected — entry deferred")
        detail = "Not met: " + "; ".join(reasons)

    return ConditionCResult(
        confirmed=confirmed,
        t1e_qualifies=t1e_qualifies,
        dark_pool_bullish=dark_pool_bullish,
        options_flow_bullish=options_flow_bullish,
        no_gap_day=no_gap_day,
        data_missing=False,
        detail=detail,
    )


def compute_per_name_size_pct(
    f30_drawdown_gate_active: bool | None,
) -> SizeGuidance:
    """Return per-name LEAPS size guidance based on the F30 drawdown gate.

    Parameters
    ----------
    f30_drawdown_gate_active:
        ``True`` when F30 is reporting an active drawdown gate (NAV 15-25%
        below 90-day peak).  ``None`` when the gate state is unknown;
        conservative (carveout) sizing is applied in that case.
    """
    if f30_drawdown_gate_active is True:
        return SizeGuidance(
            standard_max_pct=_SIZE_CARVEOUT_MAX_PCT,
            baseline_pct=_SIZE_CARVEOUT_MAX_PCT,
            baseline_max_pct=_SIZE_CARVEOUT_MAX_PCT,
            carveout_active=True,
            data_missing=False,
        )
    if f30_drawdown_gate_active is False:
        return SizeGuidance(
            standard_max_pct=_SIZE_STANDARD_MAX_PCT,
            baseline_pct=_SIZE_STANDARD_BASELINE_PCT,
            baseline_max_pct=_SIZE_STANDARD_BASELINE_MAX_PCT,
            carveout_active=False,
            data_missing=False,
        )
    # None — gate state unknown; apply conservative carveout
    return SizeGuidance(
        standard_max_pct=_SIZE_CARVEOUT_MAX_PCT,
        baseline_pct=_SIZE_CARVEOUT_MAX_PCT,
        baseline_max_pct=_SIZE_CARVEOUT_MAX_PCT,
        carveout_active=True,
        data_missing=True,
    )


def compute_f33_entry(
    ticker: str,
    drawdown_from_high_pct: float | None,
    vix_current: float | None,
    sector_drawdown_pct: float | None,
    capitulation_volume_confirmed: bool | None,
    vix_elevated: bool | None,
    vix_declining_from_peak: bool | None,
    f30_drawdown_gate_active: bool | None,
    intended_entry_usd: float | None = None,
    and_gate_passed: bool | None = None,
    t1e_score: int | None = None,
    dark_pool_bullish: bool | None = None,
    options_flow_bullish: bool | None = None,
    no_gap_day: bool | None = None,
) -> F33EntryResult:
    """Compute the composite F33 entry decision for a LEAPS position.

    Evaluation order:
    1. Static exclusion — block immediately.
    2. Condition A (Calm Accumulation) evaluation.
    3. Condition B (Washout) evaluation.
    4. Condition C (Bull Market Path) evaluation.
    5. Data-missing guard — if no condition could be evaluated, return
       qualifies=None.
    6. Qualify when A, B, or C is confirmed (A > B > C precedence).
    7. AND gate check — entries above $10 K require ``and_gate_passed=True``.
    8. Attach size guidance.

    Parameters
    ----------
    ticker:
        Ticker symbol (case-insensitive).
    drawdown_from_high_pct:
        Individual name drawdown from ATH (positive %).
    vix_current:
        Current VIX level.
    sector_drawdown_pct:
        Sector-level drawdown from its peak (positive %).
    capitulation_volume_confirmed:
        Whether capitulation volume has been confirmed.
    vix_elevated:
        Whether VIX is currently elevated.
    vix_declining_from_peak:
        Whether VIX is declining from its most recent peak.
    f30_drawdown_gate_active:
        Whether the F30 NAV drawdown gate is currently active.
    intended_entry_usd:
        Dollar amount of the intended position entry.  When provided and
        exceeds $10 000, the AND gate is enforced.
    and_gate_passed:
        Whether the AND gate (CLEAR regime + F29 3-of-5) was passed.
        Only evaluated when ``intended_entry_usd > _AND_GATE_THRESHOLD_USD``.
    t1e_score:
        Composite T1E score (0-100).  Required for Condition C.
    dark_pool_bullish:
        Whether dark pool flow is directionally bullish (from F4/Unusual Whales).
    options_flow_bullish:
        Whether options flow confirms bullish positioning (from F4 signal tier).
    no_gap_day:
        True when the ticker opened without a large overnight gap today.
    """
    size_guidance = compute_per_name_size_pct(f30_drawdown_gate_active)
    cond_a = evaluate_condition_a(drawdown_from_high_pct, vix_current)
    cond_b = evaluate_condition_b(
        sector_drawdown_pct,
        capitulation_volume_confirmed,
        vix_elevated,
        vix_declining_from_peak,
    )
    cond_c = evaluate_condition_c(t1e_score, dark_pool_bullish, options_flow_bullish, no_gap_day)

    # -- Static exclusion ----------------------------------------------------
    if is_excluded_ticker(ticker):
        return F33EntryResult(
            qualifies=False,
            qualifying_condition=None,
            excluded=True,
            data_missing=False,
            and_gate_required=False,
            block_reason=(
                f"{ticker.upper()} is excluded from LEAPS "
                "(OTC / foreign / thin US options chain)"
            ),
            size_guidance=size_guidance,
            condition_a=cond_a,
            condition_b=cond_b,
            condition_c=cond_c,
        )

    # -- Data-missing guard --------------------------------------------------
    if cond_a.confirmed is None and cond_b.confirmed is None and cond_c.confirmed is None:
        return F33EntryResult(
            qualifies=None,
            qualifying_condition=None,
            excluded=False,
            data_missing=True,
            and_gate_required=False,
            block_reason="Insufficient data to evaluate Condition A, B, or C",
            size_guidance=size_guidance,
            condition_a=cond_a,
            condition_b=cond_b,
            condition_c=cond_c,
        )

    # -- Condition routing (A > B > C precedence) ----------------------------
    if cond_a.confirmed is True:
        qualifying_condition: str | None = "A"
        qualifies_raw = True
    elif cond_b.confirmed is True:
        qualifying_condition = "B"
        qualifies_raw = True
    elif cond_c.confirmed is True:
        qualifying_condition = "C"
        qualifies_raw = True
    else:
        qualifying_condition = None
        qualifies_raw = False

    if not qualifies_raw:
        return F33EntryResult(
            qualifies=False,
            qualifying_condition=None,
            excluded=False,
            data_missing=False,
            and_gate_required=False,
            block_reason="Neither Condition A, B, nor C is met",
            size_guidance=size_guidance,
            condition_a=cond_a,
            condition_b=cond_b,
            condition_c=cond_c,
        )

    # -- AND gate enforcement ------------------------------------------------
    needs_and_gate = (
        intended_entry_usd is not None
        and intended_entry_usd > _AND_GATE_THRESHOLD_USD
        and and_gate_passed is False
    )
    if needs_and_gate:
        return F33EntryResult(
            qualifies=False,
            qualifying_condition=qualifying_condition,
            excluded=False,
            data_missing=False,
            and_gate_required=True,
            block_reason=(
                f"Entry ${intended_entry_usd:,.0f} exceeds ${_AND_GATE_THRESHOLD_USD:,.0f} "
                "— AND gate (CLEAR regime + F29 3-of-5) required but not passed"
            ),
            size_guidance=size_guidance,
            condition_a=cond_a,
            condition_b=cond_b,
            condition_c=cond_c,
        )

    return F33EntryResult(
        qualifies=True,
        qualifying_condition=qualifying_condition,
        excluded=False,
        data_missing=False,
        and_gate_required=False,
        block_reason=None,
        size_guidance=size_guidance,
        condition_a=cond_a,
        condition_b=cond_b,
        condition_c=cond_c,
    )
