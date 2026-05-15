"""Framework 29 — Three-Path Entry-Type Classifier.

Replaces the flat 4-signal AND-gate counter with a per-ticker classifier that
evaluates three paths in order (first match wins):

  Path A — WASHOUT:            underlying ↓≥8% close-to-close + F4 ≥ 11
  Path B — CATALYST_VALIDATED: position held + score ≥ T2 (70) + ≥2-of-3 catalysts
  Path C — DISCRETIONARY:      neither path matched — 2-of-3 macro signals required

Step 0 runs first: regime precondition (CRISIS_HALT → immediate BLOCKED).

HARD RULES (from spec):
  • No dummy data — if a source is unavailable, return UNAVAILABLE explicitly.
  • Decision trace logged for every evaluation.
  • CLIENT_CLARIFICATION_REQUIRED comments preserved throughout.

Open questions (surfaced in traces and comments):
  1. PRE_CATALYST regime — not in v7.3.4 taxonomy → REGIME_UNDEFINED
  2. DISCRETIONARY threshold of 2-of-3 is inferred (flag: threshold_inferred)
  3. WASHOUT wins over CATALYST_VALIDATED if both match
  4. 13F data source not wired
  5. Analyst PT raise + management meeting linkage not available
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Final

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.schemas.f29_evaluation import (
    ConditionMet,
    F29CatalystValidatedEvaluation,
    F29ConditionResult,
    F29DiscretionaryEvaluation,
    F29DiscretionarySignal,
    F29EntryType,
    F29Evaluation,
    F29GateStatus,
    F29RegimePrecondition,
    F29WashoutEvaluation,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path A — WASHOUT thresholds
_WASHOUT_DROP_THRESHOLD: Final[float] = 0.08  # close-to-close drop ≥ 8%
_WASHOUT_F4_SCORE_MIN: Final[float] = 11.0  # F4 dark pool score ≥ 11

# Path B — CATALYST_VALIDATED thresholds
_CATALYST_T2_SCORE_MIN: Final[int] = 70  # score ≥ 70 (Tier 2+)
_CATALYST_MIN_SUB_CONDITIONS: Final[int] = 2  # ≥ 2-of-3 sub-conditions met

# Path C — DISCRETIONARY signal thresholds (updated from 4-signal counter)
_DISC_VIX_LOOKBACK_SESSIONS: Final[int] = 10  # trailing 10 sessions for regime-high
_DISC_VIX_DECLINE_SESSIONS: Final[int] = 3  # monotonic decline for 3 consecutive sessions
_DISC_PCR_PANIC_THRESHOLD: Final[float] = 1.3  # spike ≥ 1.3 triggers panic window
_DISC_PCR_LOOKBACK_SESSIONS: Final[int] = 10
_DISC_PCR_REVERSAL_MIN: Final[float] = 0.15  # most-recent session ≥ 0.15 below peak
_DISC_BREADTH_WASHOUT_THRESHOLD: Final[float] = 30.0  # % above 50-DMA marks washout
_DISC_BREADTH_LOOKBACK_SESSIONS: Final[int] = 10
_DISC_BREADTH_RECOVERY_THRESHOLD: Final[float] = 35.0  # recovery confirmed at ≥ 35%
_DISC_THRESHOLD: Final[int] = 2  # CLIENT_CLARIFICATION_REQUIRED (#2)

# Permitted regimes (non-blocking).
# CLIENT_CLARIFICATION_REQUIRED (#1): PRE_CATALYST not in v7.3.4 taxonomy.
_PERMITTED_REGIMES: Final[frozenset[str]] = frozenset(
    {"CLEAR", "SOFT_CAUTION", "CAUTION", "NONE", "NORMAL"}
)
_CRISIS_HALT_LABELS: Final[frozenset[str]] = frozenset({"CRISIS HALT", "CRISIS_HALT"})

# Polygon aggs endpoint for close-to-close WASHOUT check.
_POLYGON_AGGS_URL: Final[str] = (
    "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
)


# ---------------------------------------------------------------------------
# Pure signal helpers for Path C (DISCRETIONARY)
# ---------------------------------------------------------------------------


def _check_disc_signal1_vix(
    vix_closes: list[float],
) -> tuple[ConditionMet, float | None]:
    """S1: VIX touches regime-high in trailing 10 sessions then declines 3 consecutive.

    Returns (met, vix_latest). Pure function — no I/O.
    """
    if len(vix_closes) < _DISC_VIX_LOOKBACK_SESSIONS + _DISC_VIX_DECLINE_SESSIONS:
        return "UNAVAILABLE", None

    window = vix_closes[-_DISC_VIX_LOOKBACK_SESSIONS:]
    regime_high = max(window)

    # Most recent peak index within window (reversed = most recent first).
    peak_offset = next(i for i, v in enumerate(reversed(window)) if v == regime_high)
    sessions_since_peak = peak_offset
    touched_high = sessions_since_peak >= _DISC_VIX_DECLINE_SESSIONS

    # Check 3 consecutive declining sessions at the tail.
    tail = vix_closes[-(_DISC_VIX_DECLINE_SESSIONS + 1) :]
    declining = len(tail) == _DISC_VIX_DECLINE_SESSIONS + 1 and all(
        tail[i + 1] < tail[i] for i in range(_DISC_VIX_DECLINE_SESSIONS)
    )

    return bool(touched_high and declining), round(vix_closes[-1], 2)


def _check_disc_signal3_pcr(
    pcr_sessions: list[float],
) -> tuple[ConditionMet, float | None]:
    """S3: PCR reached ≥1.3 in trailing 10 sessions AND current ≥0.15 below peak.

    Returns (met, pcr_latest). Pure function — no I/O.
    """
    if len(pcr_sessions) < 3:
        return "UNAVAILABLE", None

    window = pcr_sessions[-_DISC_PCR_LOOKBACK_SESSIONS:]
    spiked = any(r >= _DISC_PCR_PANIC_THRESHOLD for r in window)
    if not spiked:
        return False, round(pcr_sessions[-1], 3)

    peak_pcr = max(window)
    reversal = (peak_pcr - pcr_sessions[-1]) >= _DISC_PCR_REVERSAL_MIN
    return bool(reversal), round(pcr_sessions[-1], 3)


def _check_disc_signal4_breadth(
    breadth_values: list[float],
) -> tuple[ConditionMet, float | None]:
    """S4: Breadth ≤30% in trailing 10 sessions AND most recent reading ≥35%.

    Returns (met, breadth_latest_pct). Pure function — no I/O.
    """
    if len(breadth_values) < 3:
        return "UNAVAILABLE", None

    window = breadth_values[-_DISC_BREADTH_LOOKBACK_SESSIONS:]
    washout_occurred = any(v <= _DISC_BREADTH_WASHOUT_THRESHOLD for v in window)
    recovered = breadth_values[-1] >= _DISC_BREADTH_RECOVERY_THRESHOLD

    return bool(washout_occurred and recovered), round(breadth_values[-1], 2)


# ---------------------------------------------------------------------------
# Internal path evaluators (pure — accept already-fetched data)
# ---------------------------------------------------------------------------


def _evaluate_regime_precondition(regime_label: str | None) -> F29RegimePrecondition:
    """Step 0: regime precondition check. Pure function — no I/O.

    CLIENT_CLARIFICATION_REQUIRED (#1): PRE_CATALYST treated as REGIME_UNDEFINED.
    """
    if regime_label is None:
        return F29RegimePrecondition(
            regime="UNKNOWN",
            passed=False,
            reason="Regime state unavailable — cannot classify entry type.",
            regime_undefined_flag=True,
        )

    normalised = regime_label.strip().upper().replace(" ", "_")

    if normalised in {"CRISIS_HALT", "CRISIS HALT"}:
        return F29RegimePrecondition(
            regime=regime_label,
            passed=False,
            reason="CRISIS HALT regime — no LEAPS regardless of entry type.",
        )

    # Known permitted regimes.
    known_permitted = {
        "CLEAR",
        "SOFT_CAUTION",
        "CAUTION",
        "NONE",
        "NORMAL",
    }
    if normalised in known_permitted:
        return F29RegimePrecondition(regime=regime_label, passed=True)

    # CLIENT_CLARIFICATION_REQUIRED (#1): Any unknown/undefined regime label
    # (e.g. PRE_CATALYST) is treated as REGIME_UNDEFINED, not silently mapped.
    return F29RegimePrecondition(
        regime=regime_label,
        passed=False,
        reason=(
            f"Regime '{regime_label}' is not in the permitted regime taxonomy "
            "(CLEAR / SOFT_CAUTION / CAUTION). Treating as REGIME_UNDEFINED."
        ),
        regime_undefined_flag=True,
    )


def _evaluate_washout_path(
    session_change_pct: float | None,
    f4_score: float | None,
    price_unavailable: bool = False,
    f4_unavailable: bool = False,
) -> F29WashoutEvaluation:
    """Path A evaluator. Pure function — no I/O.

    Both conditions required. If either source is UNAVAILABLE, matched=False
    and the classifier falls through to Path B.
    """
    data_gaps: list[str] = []

    # Condition 1: close-to-close drop ≥ 8%
    if price_unavailable or session_change_pct is None:
        cond1_met: ConditionMet = "UNAVAILABLE"
        data_gaps.append("WASHOUT_PRICE_DATA_UNAVAILABLE: Polygon close-to-close fetch failed")
    else:
        # session_change_pct is negative when price fell; spec says "down ≥8%"
        cond1_met = bool(session_change_pct <= -_WASHOUT_DROP_THRESHOLD)

    # Condition 2: F4 score ≥ 11
    if f4_unavailable or f4_score is None:
        cond2_met: ConditionMet = "UNAVAILABLE"
        data_gaps.append("WASHOUT_F4_DATA_UNAVAILABLE: Framework 9 evaluation failed or timed out")
    else:
        cond2_met = bool(f4_score >= _WASHOUT_F4_SCORE_MIN)

    conditions = [
        F29ConditionResult(
            id="washout_price_drop",
            met=cond1_met,
            value=round(session_change_pct * 100, 2) if session_change_pct is not None else None,
            reason=f"Required: ≤-{_WASHOUT_DROP_THRESHOLD * 100:.0f}%",
        ),
        F29ConditionResult(
            id="washout_f4_score",
            met=cond2_met,
            value=f4_score,
            reason=f"Required: ≥{_WASHOUT_F4_SCORE_MIN}",
        ),
    ]

    # WASHOUT matches only when BOTH are True (not UNAVAILABLE, not False).
    matched = cond1_met is True and cond2_met is True

    return F29WashoutEvaluation(
        matched=matched,
        session_change_pct=session_change_pct,
        f4_score=f4_score,
        conditions=conditions,
        data_gaps=data_gaps,
    )


def _evaluate_catalyst_path(
    position_held: ConditionMet,
    score_tier_pass: ConditionMet,
    revenue_inflection_met: ConditionMet,
    institutional_13f_met: ConditionMet = "UNAVAILABLE",
    analyst_pt_raise_met: ConditionMet = "UNAVAILABLE",
) -> F29CatalystValidatedEvaluation:
    """Path B evaluator. Pure function — no I/O.

    Accepts live ConditionMet values for all three sub-conditions.
    UNAVAILABLE sub-conditions count as NOT MET for the 2-of-3 threshold.
    When an upstream fetch fails or a key is not configured the caller passes
    "UNAVAILABLE" so the evaluator surfaces it as a data gap.
    """
    data_gaps: list[str] = []

    sub_conditions = [
        F29ConditionResult(
            id="catalyst_13f_concentration_buy",
            met=institutional_13f_met,
            reason=(
                "Institutional ownership increased quarter-over-quarter (13F)"
                if institutional_13f_met != "UNAVAILABLE"
                else (
                    "13F_INSTITUTIONAL_OWNERSHIP_UNAVAILABLE: sec_api_key not configured "
                    "or institutional ownership data unavailable"
                )
            ),
        ),
        F29ConditionResult(
            id="catalyst_analyst_pt_raise",
            met=analyst_pt_raise_met,
            reason=(
                "Analyst price target raise in last 30 days (Benzinga)"
                if analyst_pt_raise_met != "UNAVAILABLE"
                else (
                    "ANALYST_RATINGS_UNAVAILABLE: benzinga_api_key not configured "
                    "or ratings data unavailable"
                )
            ),
        ),
        F29ConditionResult(
            id="catalyst_revenue_inflection",
            met=revenue_inflection_met,
            reason=(
                "Revenue inflection: YoY growth acceleration vs prior quarter"
                if revenue_inflection_met != "UNAVAILABLE"
                else (
                    "REVENUE_DATA_UNAVAILABLE: alphavantage_api_key not configured "
                    "or income statement data unavailable"
                )
            ),
        ),
    ]

    data_gaps.extend(
        sc.reason for sc in sub_conditions if sc.met == "UNAVAILABLE" and sc.reason is not None
    )

    # Count only explicitly True sub-conditions; UNAVAILABLE counts as not-met.
    met_count = sum(1 for sc in sub_conditions if sc.met is True)

    # Match requires: position_held=True AND score_tier_pass=True AND met_count ≥ 2.
    matched = (
        position_held is True
        and score_tier_pass is True
        and met_count >= _CATALYST_MIN_SUB_CONDITIONS
    )

    return F29CatalystValidatedEvaluation(
        matched=matched,
        position_held=position_held,
        score_tier_pass=score_tier_pass,
        sub_conditions=sub_conditions,
        sub_conditions_met_count=met_count,
        data_gaps=data_gaps,
    )


def _evaluate_discretionary_path(
    vix_closes: list[float] | None,
    pcr_sessions: list[float] | None,
    breadth_values: list[float] | None,
) -> F29DiscretionaryEvaluation:
    """Path C evaluator. Pure function — no I/O.

    CLIENT_CLARIFICATION_REQUIRED (#2): Threshold of 2-of-3 is inferred.
    If 2+ signals UNAVAILABLE, gate_status will be UNAVAILABLE (not BLOCKED).
    """
    s1_met, s1_val = _check_disc_signal1_vix(vix_closes) if vix_closes else ("UNAVAILABLE", None)
    s3_met, s3_val = (
        _check_disc_signal3_pcr(pcr_sessions) if pcr_sessions else ("UNAVAILABLE", None)
    )
    s4_met, s4_val = (
        _check_disc_signal4_breadth(breadth_values) if breadth_values else ("UNAVAILABLE", None)
    )

    signals = [
        F29DiscretionarySignal(
            id="disc_s1_vix",
            label="VIX touches regime-high (10-session) then declines 3 consecutive",
            met=s1_met,
            value=s1_val,
        ),
        F29DiscretionarySignal(
            id="disc_s3_pcr",
            label="Put/call ratio spikes ≥1.3 then reverses ≥0.15 from peak",
            met=s3_met,
            value=s3_val,
        ),
        F29DiscretionarySignal(
            id="disc_s4_breadth",
            label="S&P 500 breadth dips ≤30% (10-session) then recovers ≥35%",
            met=s4_met,
            value=s4_val,
        ),
    ]

    signals_met = sum(1 for s in signals if s.met is True)
    signals_unavailable = sum(1 for s in signals if s.met == "UNAVAILABLE")

    return F29DiscretionaryEvaluation(
        signals=signals,
        signals_met=signals_met,
        signals_unavailable=signals_unavailable,
        threshold=_DISC_THRESHOLD,
        threshold_inferred=True,
    )


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------


class F29EntryClassifier:
    """Three-path LEAPS entry-type classifier for Framework 29.

    Instantiate with API keys; call classify() per ticker.
    classify() is async — it fetches per-ticker price and scoring data
    then delegates to pure path evaluators.
    """

    def __init__(
        self,
        polygon_api_key: str,
        uw_api_key: str,
        av_api_key: str = "",
        transcript_api_key: str = "",
        benzinga_api_key: str = "",
        sec_api_key: str = "",
    ) -> None:
        self._polygon_key = polygon_api_key
        self._uw_key = uw_api_key
        self._av_key = av_api_key
        self._transcript_key = transcript_api_key
        self._benzinga_key = benzinga_api_key
        self._sec_key = sec_api_key

    async def classify(
        self,
        ticker: str,
        session: AsyncSession,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> F29Evaluation:
        """Classify entry type for *ticker* and return a full F29Evaluation.

        Fetches data in parallel where possible.  All data-source failures are
        surfaced as UNAVAILABLE conditions — no dummy data is used.

        Decision trace is logged via structlog-compatible logger at INFO level.
        """
        import asyncio

        from atlas.services.framework29_service import (
            _YAHOO_VIX_URL,
            _fetch_sp500_breadth_series,
            _fetch_uw_pcr_from_options_volume,
            _fetch_yahoo_daily_closes,
        )
        from atlas.services.regime_modifier_service import get_current_regime_label

        trace_id = str(uuid.uuid4())
        evaluated_at = datetime.now(tz=UTC)
        normalised = ticker.strip().upper()

        # ── Step 0: Regime precondition ───────────────────────────────────
        regime_label = get_current_regime_label()
        regime_pre = _evaluate_regime_precondition(regime_label)

        if not regime_pre.passed:
            # CRISIS_HALT or REGIME_UNDEFINED — classify and return immediately.
            if regime_pre.regime_undefined_flag:
                entry_type = F29EntryType.UNAVAILABLE
                gate_status = F29GateStatus.UNAVAILABLE
            else:
                entry_type = F29EntryType.BLOCKED_BY_REGIME
                gate_status = F29GateStatus.BLOCKED

            washout_empty = F29WashoutEvaluation(
                matched=False, conditions=[], data_gaps=["Regime precondition not passed"]
            )
            catalyst_empty = F29CatalystValidatedEvaluation(
                matched=False,
                position_held=False,
                score_tier_pass=False,
                sub_conditions=[],
                sub_conditions_met_count=0,
                data_gaps=["Regime precondition not passed"],
            )
            self._log_trace(
                trace_id=trace_id,
                ticker=normalised,
                regime=regime_label or "UNKNOWN",
                entry_type=entry_type,
                gate_status=gate_status,
                path_evals={"regime_blocked": True},
                data_gaps=[regime_pre.reason or ""],
                threshold_inferred=False,
                regime_undefined=regime_pre.regime_undefined_flag,
                evaluated_at=evaluated_at,
            )
            return F29Evaluation(
                ticker=normalised,
                gate_status=gate_status,
                entry_type=entry_type,
                regime_precondition=regime_pre,
                washout_evaluation=washout_empty,
                catalyst_validated_evaluation=catalyst_empty,
                discretionary_evaluation=None,
                decision_trace_id=trace_id,
                evaluated_at=evaluated_at,
                all_data_gaps=[regime_pre.reason or ""],
            )

        # ── Parallel data fetch ───────────────────────────────────────────
        _client = client if client is not None else httpx.AsyncClient()

        try:
            (
                price_closes_raw,
                f9_result_raw,
                position_weight_raw,
                vix_closes_raw,
                pcr_raw,
                breadth_raw,
                revenue_inflection_raw,
                analyst_pt_raw,
                institutional_13f_raw,
            ) = await asyncio.gather(
                self._fetch_ticker_closes(normalised, 5, _client),
                self._fetch_f9_score(normalised, _client),
                self._fetch_position_weight(normalised, session),
                _fetch_yahoo_daily_closes(_YAHOO_VIX_URL, "3mo", _client),
                _fetch_uw_pcr_from_options_volume(self._uw_key, _client),
                _fetch_sp500_breadth_series(self._polygon_key, _client),
                self._fetch_revenue_inflection_status(normalised, _client),
                self._fetch_analyst_pt_raise_status(normalised, _client),
                self._fetch_13f_concentration_buy_status(normalised, _client),
                return_exceptions=True,
            )
        finally:
            if client is None:
                await _client.aclose()

        # Unwrap exceptions → None for graceful degradation.
        def _unwrap(v: object) -> object:
            return None if isinstance(v, BaseException) else v

        price_closes: list[float] | None = _unwrap(price_closes_raw)  # type: ignore[assignment]
        f9_result = _unwrap(f9_result_raw)
        position_weight: float | None = _unwrap(position_weight_raw)  # type: ignore[assignment]
        vix_closes: list[float] | None = _unwrap(vix_closes_raw)  # type: ignore[assignment]
        pcr_sessions: list[float] | None = _unwrap(pcr_raw)  # type: ignore[assignment]
        breadth_values: list[float] | None = _unwrap(breadth_raw)  # type: ignore[assignment]

        def _to_condition_met(v: object) -> ConditionMet:
            """Convert an unwrapped gather result to ConditionMet."""
            if isinstance(v, bool):
                return v
            if v == "UNAVAILABLE":
                return "UNAVAILABLE"
            return "UNAVAILABLE"

        revenue_inflection_val: ConditionMet = _to_condition_met(_unwrap(revenue_inflection_raw))
        analyst_pt_raise_val: ConditionMet = _to_condition_met(_unwrap(analyst_pt_raw))
        institutional_13f_val: ConditionMet = _to_condition_met(_unwrap(institutional_13f_raw))

        # ── Path A: WASHOUT ───────────────────────────────────────────────
        session_change_pct: float | None = None
        price_unavailable = price_closes is None or len(price_closes) < 2
        if not price_unavailable and price_closes is not None:
            session_change_pct = (
                (price_closes[-1] - price_closes[-2]) / price_closes[-2]
                if price_closes[-2] != 0
                else None
            )

        f4_score: float | None = None
        f4_unavailable = f9_result is None
        if f9_result is not None:
            f4_score = getattr(f9_result, "f4_score", None)
            if f4_score is None:
                f4_unavailable = True

        washout_eval = _evaluate_washout_path(
            session_change_pct=session_change_pct,
            f4_score=f4_score,
            price_unavailable=price_unavailable,
            f4_unavailable=f4_unavailable,
        )

        # ── Path B: CATALYST_VALIDATED ────────────────────────────────────
        position_held: ConditionMet
        if position_weight is None:
            position_held = "UNAVAILABLE"
        else:
            position_held = bool(float(position_weight) > 0.0)

        # Get final score from F9 result (or UNAVAILABLE)
        # NOTE: Framework9Result exposes f4_score (0-100), not final_score.
        score_tier_pass: ConditionMet
        final_score: int | None = None
        if f9_result is not None:
            raw_score = getattr(f9_result, "f4_score", None)
            if raw_score is not None:
                final_score = int(raw_score)
                score_tier_pass = bool(final_score >= _CATALYST_T2_SCORE_MIN)
            else:
                score_tier_pass = "UNAVAILABLE"
        else:
            score_tier_pass = "UNAVAILABLE"

        catalyst_eval = _evaluate_catalyst_path(
            position_held=position_held,
            score_tier_pass=score_tier_pass,
            revenue_inflection_met=revenue_inflection_val,
            institutional_13f_met=institutional_13f_val,
            analyst_pt_raise_met=analyst_pt_raise_val,
        )

        # ── Path C: DISCRETIONARY ─────────────────────────────────────────
        disc_eval = _evaluate_discretionary_path(
            vix_closes=vix_closes,
            pcr_sessions=pcr_sessions,
            breadth_values=breadth_values,
        )

        # ── Entry type determination (first match wins) ───────────────────
        # CLIENT_CLARIFICATION_REQUIRED (#3): WASHOUT wins if both paths match.
        if washout_eval.matched:
            entry_type = F29EntryType.WASHOUT
            gate_status = F29GateStatus.PASS
            disc_result = None
        elif catalyst_eval.matched:
            entry_type = F29EntryType.CATALYST_VALIDATED
            gate_status = F29GateStatus.PASS
            disc_result = None
        else:
            entry_type = F29EntryType.DISCRETIONARY
            disc_result = disc_eval
            signals_unavailable = disc_eval.signals_unavailable
            # If 2+ signals are UNAVAILABLE → gate is UNAVAILABLE (not BLOCKED).
            if signals_unavailable >= 2:
                gate_status = F29GateStatus.UNAVAILABLE
            elif disc_eval.signals_met >= disc_eval.threshold:
                gate_status = F29GateStatus.PASS
            else:
                gate_status = F29GateStatus.BLOCKED

        # ── Consolidate data gaps ─────────────────────────────────────────
        all_data_gaps = list(washout_eval.data_gaps)
        all_data_gaps.extend(catalyst_eval.data_gaps)
        if disc_result is not None and any(s.met == "UNAVAILABLE" for s in disc_result.signals):
            all_data_gaps.append("DISCRETIONARY macro signals partially unavailable")

        self._log_trace(
            trace_id=trace_id,
            ticker=normalised,
            regime=regime_label or "UNKNOWN",
            entry_type=entry_type,
            gate_status=gate_status,
            path_evals={
                "washout_matched": washout_eval.matched,
                "catalyst_matched": catalyst_eval.matched,
                "discretionary_signals_met": disc_eval.signals_met,
                "discretionary_signals_unavailable": disc_eval.signals_unavailable,
            },
            data_gaps=all_data_gaps,
            threshold_inferred=True,
            regime_undefined=False,
            evaluated_at=evaluated_at,
        )

        return F29Evaluation(
            ticker=normalised,
            gate_status=gate_status,
            entry_type=entry_type,
            regime_precondition=regime_pre,
            washout_evaluation=washout_eval,
            catalyst_validated_evaluation=catalyst_eval,
            discretionary_evaluation=disc_result,
            decision_trace_id=trace_id,
            evaluated_at=evaluated_at,
            all_data_gaps=all_data_gaps,
        )

    # ── Private helpers ───────────────────────────────────────────────────

    async def _fetch_revenue_inflection_status(
        self,
        ticker: str,
        client: httpx.AsyncClient,
    ) -> ConditionMet:
        """Return True if YoY revenue growth accelerated in the most recent quarter.

        Fetches Alpha Vantage INCOME_STATEMENT (quarterly). Requires 6 quarters to
        compare consecutive YoY growth rates:
            recent_yoy  = (q[5] - q[1]) / |q[1]|
            prior_yoy   = (q[4] - q[0]) / |q[0]|
            met = recent_yoy > prior_yoy

        Returns UNAVAILABLE when the API key is absent, the rate limit is hit,
        or fewer than 6 valid quarterly revenue figures are available.
        """
        if not self._av_key:
            return "UNAVAILABLE"
        try:
            resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "INCOME_STATEMENT",
                    "symbol": ticker,
                    "apikey": self._av_key,
                },
                timeout=15.0,
            )
            if resp.status_code != 200:
                return "UNAVAILABLE"
            data = resp.json()
            if "Note" in data or "Information" in data or "quarterlyReports" not in data:
                return "UNAVAILABLE"

            # AV returns most-recent first; reverse to chronological order.
            raw_reports: list[object] = data["quarterlyReports"]
            revenues: list[float] = []
            for report in reversed(raw_reports[:8]):
                if not isinstance(report, dict):
                    continue
                try:
                    val = float(report.get("totalRevenue") or 0)
                    if val > 0:
                        revenues.append(val)
                except (TypeError, ValueError):
                    continue

            if len(revenues) < 6:
                return "UNAVAILABLE"

            # Compare YoY growth rate for the two most recent quarters.
            base_recent = revenues[1]
            base_prior = revenues[0]
            if base_recent == 0 or base_prior == 0:
                return "UNAVAILABLE"

            recent_yoy = (revenues[5] - revenues[1]) / abs(revenues[1])
            prior_yoy = (revenues[4] - revenues[0]) / abs(revenues[0])
            return bool(recent_yoy > prior_yoy)

        except Exception as exc:
            logger.warning(
                "F29 classifier: revenue inflection fetch failed",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return "UNAVAILABLE"

    async def _fetch_analyst_pt_raise_status(
        self,
        ticker: str,
        client: httpx.AsyncClient,
    ) -> ConditionMet:
        """Return True if at least one analyst raised their PT in the last 30 days.

        Uses the Benzinga calendar/ratings endpoint (same source as F3 service).
        Returns UNAVAILABLE when benzinga_api_key is absent or the fetch fails.
        """
        if not self._benzinga_key:
            return "UNAVAILABLE"
        from datetime import date, timedelta

        date_from = (date.today() - timedelta(days=30)).isoformat()
        date_to = date.today().isoformat()
        try:
            resp = await client.get(
                "https://api.benzinga.com/api/v2.1/calendar/ratings",
                params={
                    "tickers": ticker.upper(),
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "token": self._benzinga_key,
                },
                headers={"accept": "application/json"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return "UNAVAILABLE"
            payload = resp.json()
            ratings: list[object] = payload.get("ratings") or []
            raises = sum(
                1
                for r in ratings
                if isinstance(r, dict)
                and r.get("ticker", "").upper() == ticker.upper()
                and (r.get("action_pt") or "").strip().lower() in ("raises", "announces")
            )
            return bool(raises > 0)
        except Exception as exc:
            logger.warning(
                "F29 classifier: analyst PT raise fetch failed",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return "UNAVAILABLE"

    async def _fetch_13f_concentration_buy_status(
        self,
        ticker: str,
        client: httpx.AsyncClient,
    ) -> ConditionMet:
        """Return True if total institutional ownership of *ticker* increased QoQ.

        Queries the sec-api.io Form 13F Holdings API (POST /form-13f/holdings)
        for the most recent filings disclosing *ticker*. Aggregates share counts
        per quarter (periodOfReport), then compares the two most recent quarters.
        Returns True when the most-recent-quarter aggregate exceeds the prior one.

        Returns UNAVAILABLE when:
          - sec_api_key is absent
          - the API returns non-200 (including 429 rate limit)
          - fewer than 2 distinct reporting periods are found
          - any other network/parse error occurs
        """
        if not self._sec_key:
            return "UNAVAILABLE"
        try:
            resp = await client.post(
                "https://api.sec-api.io/form-13f/holdings",
                json={
                    "query": f"holdings.ticker:{ticker.upper()}",
                    "from": "0",
                    "size": "50",
                    "sort": [{"filedAt": {"order": "desc"}}],
                },
                headers={"Authorization": self._sec_key},
                timeout=15.0,
            )
            if resp.status_code != 200:
                return "UNAVAILABLE"
            payload = resp.json()
            filings: list[object] = payload.get("data") or []
            if not filings:
                return "UNAVAILABLE"

            # Aggregate total shares per periodOfReport across all filers.
            from collections import defaultdict

            period_shares: dict[str, int] = defaultdict(int)
            for filing in filings:
                if not isinstance(filing, dict):
                    continue
                period = filing.get("periodOfReport")
                if not period:
                    continue
                for holding in filing.get("holdings", []):
                    if not isinstance(holding, dict):
                        continue
                    if holding.get("ticker") != ticker.upper():
                        continue
                    shr_obj = holding.get("shrsOrPrnAmt") or {}
                    shares = int(shr_obj.get("sshPrnamt") or 0)
                    period_shares[period] += shares

            sorted_periods = sorted(period_shares.keys(), reverse=True)
            if len(sorted_periods) < 2:
                return "UNAVAILABLE"

            current_shares = period_shares[sorted_periods[0]]
            prior_shares = period_shares[sorted_periods[1]]
            if prior_shares == 0:
                return "UNAVAILABLE"
            return bool(current_shares > prior_shares)
        except Exception as exc:
            logger.warning(
                "F29 classifier: 13F institutional ownership fetch failed",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return "UNAVAILABLE"

    async def _fetch_ticker_closes(
        self,
        ticker: str,
        num_days: int,
        client: httpx.AsyncClient,
    ) -> list[float] | None:
        """Fetch last *num_days* daily closes for *ticker* from Polygon aggs."""
        from datetime import date, timedelta

        to_date = date.today()
        from_date = to_date - timedelta(days=num_days * 3)  # buffer for weekends
        url = _POLYGON_AGGS_URL.format(
            ticker=ticker,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
        )
        try:
            resp = await client.get(
                url,
                params={"apiKey": self._polygon_key, "sort": "asc", "limit": num_days + 10},
                timeout=10.0,
            )
            if resp.status_code != 200:
                logger.warning(
                    "F29 classifier: Polygon aggs non-200",
                    extra={"ticker": ticker, "status": resp.status_code},
                )
                return None
            results = resp.json().get("results") or []
            closes = [float(b["c"]) for b in results if "c" in b]
            return closes if len(closes) >= 2 else None
        except Exception as exc:
            logger.warning(
                "F29 classifier: Polygon aggs fetch failed",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return None

    async def _fetch_f9_score(
        self,
        ticker: str,
        client: httpx.AsyncClient,
    ) -> object | None:
        """Fetch Framework 9 result for *ticker* to extract f4_score and final_score."""
        try:
            from atlas.services.framework9_service import evaluate_framework9

            return await evaluate_framework9(
                ticker=ticker,
                uw_api_key=self._uw_key,
                polygon_api_key=self._polygon_key,
                av_api_key=self._av_key,
                client=client,
            )
        except Exception as exc:
            logger.warning(
                "F29 classifier: F9 evaluation failed",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return None

    async def _fetch_position_weight(
        self,
        ticker: str,
        session: AsyncSession,
    ) -> float | None:
        """Return position weight as fraction of NAV from the live portfolio DB."""
        try:
            from atlas.services.tranche_sizing_service import get_position_weight

            return await get_position_weight(ticker, session)
        except Exception as exc:
            logger.warning(
                "F29 classifier: position weight fetch failed",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return None

    @staticmethod
    def _log_trace(
        *,
        trace_id: str,
        ticker: str,
        regime: str,
        entry_type: F29EntryType,
        gate_status: F29GateStatus,
        path_evals: dict[str, object],
        data_gaps: list[str],
        threshold_inferred: bool,
        regime_undefined: bool,
        evaluated_at: datetime,
    ) -> None:
        """Emit a structured decision trace log entry."""
        logger.info(
            "F29 evaluation",
            extra={
                "framework_id": 29,
                "decision_trace_id": trace_id,
                "ticker": ticker,
                "regime_at_evaluation": regime,
                "entry_type_classified": entry_type.value,
                "gate_result": gate_status.value,
                "path_evaluations": path_evals,
                "data_gaps": data_gaps,
                "threshold_inferred_flag": threshold_inferred,
                "regime_undefined_flag": regime_undefined,
                "timestamp": evaluated_at.isoformat(),
            },
        )
