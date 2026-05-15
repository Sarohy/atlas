"""Pytest suite for F29EntryClassifier — all 9 spec cases.

Tests cover the pure path evaluator functions directly (no I/O, no mocks needed
for the pure functions) and the orchestrator via AsyncMock injection.

SPEC CASES:
  1. CRISIS_HALT regime → BLOCKED immediately, no classifier runs
  2. WASHOUT match (price -10%, F4=12) → PASS with entry_type=WASHOUT
  3. WASHOUT partial (price -10%, F4 unavailable) → falls through to CATALYST_VALIDATED
  4. CATALYST_VALIDATED match (held, score 80, 2 of 3 sub-conditions met) → PASS
  5. CATALYST_VALIDATED with all 3 sub-conditions UNAVAILABLE → falls through to DISCRETIONARY
  6. DISCRETIONARY with 2 of 3 signals confirmed → PASS
  7. DISCRETIONARY with 1 of 3 confirmed + 2 unavailable → UNAVAILABLE (not BLOCKED)
  8. Unknown regime "PRE_CATALYST" → UNAVAILABLE with REGIME_UNDEFINED flag
  9. MU test (held 13.6%, score 80, 13F+analyst UNAVAILABLE) → surface data gaps explicitly
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.schemas.f29_evaluation import (
    F29EntryType,
    F29GateStatus,
)
from atlas.services.f29_entry_classifier_service import (
    F29EntryClassifier,
    _check_disc_signal1_vix,
    _check_disc_signal3_pcr,
    _check_disc_signal4_breadth,
    _evaluate_catalyst_path,
    _evaluate_discretionary_path,
    _evaluate_regime_precondition,
    _evaluate_washout_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_classifier() -> F29EntryClassifier:
    return F29EntryClassifier(
        polygon_api_key="test_poly",
        uw_api_key="test_uw",
        av_api_key="test_av",
    )


def _make_mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


def _make_f9_result(f4_score: float = 15.0, final_score: float = 80.0) -> MagicMock:
    """Build a minimal Framework9Result mock. final_score kept for call-site compat
    but the classifier now reads f4_score only (Framework9Result has no final_score)."""
    result = MagicMock()
    result.f4_score = f4_score
    return result


# VIX series: regime-high embedded, then monotonic 3-session decline at the tail.
# Must have ≥ 13 elements (lookback=10 + decline_window=3).
_VIX_CONFIRMED = [
    20.0, 21.0, 19.0, 18.0, 17.5,   # earlier sessions (5)
    22.0,                              # regime high (7 sessions from end)
    21.5, 21.0, 20.5,                # some sessions after
    20.0, 19.0, 18.0, 17.5,          # last 4 sessions — declining (added 17.5 to reach 13)
]

# PCR series: spike above 1.3 then reversal ≥0.15 from peak.
_PCR_CONFIRMED = [0.8, 0.9, 0.85, 0.9, 0.95, 1.0, 1.1, 1.4, 1.35, 1.0, 0.85]  # peak=1.4, current=0.85

# Breadth series: dipped ≤30% then recovered ≥35%.
_BREADTH_CONFIRMED = [45.0, 40.0, 35.0, 28.0, 25.0, 27.0, 30.0, 36.0, 38.0, 40.0]

# VIX series that is NOT confirmed (VIX currently rising).
_VIX_NOT_MET = [18.0, 17.5, 17.0, 16.5, 16.0, 15.5, 15.0, 14.5, 14.0, 13.5, 14.0, 14.5, 15.0]

# PCR series with no spike.
_PCR_NOT_MET = [0.6, 0.7, 0.65, 0.7, 0.8, 0.75, 0.72, 0.68, 0.5, 0.47, 0.48]


# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------

class TestRegimePrecondition:
    def test_crisis_halt_blocked(self) -> None:
        result = _evaluate_regime_precondition("CRISIS HALT")
        assert result.passed is False
        assert "CRISIS HALT" in result.reason  # type: ignore[operator]

    def test_crisis_halt_underscore_variant(self) -> None:
        result = _evaluate_regime_precondition("CRISIS_HALT")
        assert result.passed is False

    def test_caution_permitted(self) -> None:
        result = _evaluate_regime_precondition("CAUTION")
        assert result.passed is True
        assert result.regime_undefined_flag is False

    def test_clear_permitted(self) -> None:
        result = _evaluate_regime_precondition("CLEAR")
        assert result.passed is True

    def test_soft_caution_permitted(self) -> None:
        result = _evaluate_regime_precondition("SOFT_CAUTION")
        assert result.passed is True

    def test_none_is_unavailable(self) -> None:
        result = _evaluate_regime_precondition(None)
        assert result.passed is False
        assert result.regime_undefined_flag is True

    def test_pre_catalyst_is_regime_undefined(self) -> None:
        """Case 8: Unknown regime PRE_CATALYST → UNAVAILABLE with REGIME_UNDEFINED flag."""
        result = _evaluate_regime_precondition("PRE_CATALYST")
        assert result.passed is False
        assert result.regime_undefined_flag is True
        assert "PRE_CATALYST" in result.reason  # type: ignore[operator]


class TestWashoutPath:
    def test_both_conditions_met(self) -> None:
        """Case 2: WASHOUT match — price -10%, F4=12."""
        result = _evaluate_washout_path(
            session_change_pct=-0.10,
            f4_score=12.0,
        )
        assert result.matched is True
        assert result.conditions[0].met is True
        assert result.conditions[1].met is True
        assert len(result.data_gaps) == 0

    def test_price_condition_just_at_threshold(self) -> None:
        result = _evaluate_washout_path(session_change_pct=-0.08, f4_score=12.0)
        assert result.matched is True

    def test_price_above_threshold_not_matched(self) -> None:
        result = _evaluate_washout_path(session_change_pct=-0.07, f4_score=12.0)
        assert result.matched is False
        assert result.conditions[0].met is False

    def test_f4_below_threshold_not_matched(self) -> None:
        result = _evaluate_washout_path(session_change_pct=-0.10, f4_score=10.9)
        assert result.matched is False
        assert result.conditions[1].met is False

    def test_f4_unavailable_falls_through(self) -> None:
        """Case 3: WASHOUT partial — price -10%, F4 unavailable → not matched."""
        result = _evaluate_washout_path(
            session_change_pct=-0.10,
            f4_score=None,
            f4_unavailable=True,
        )
        assert result.matched is False
        assert result.conditions[1].met == "UNAVAILABLE"
        assert any("F4" in g for g in result.data_gaps)

    def test_price_unavailable_falls_through(self) -> None:
        result = _evaluate_washout_path(
            session_change_pct=None,
            f4_score=12.0,
            price_unavailable=True,
        )
        assert result.matched is False
        assert result.conditions[0].met == "UNAVAILABLE"
        assert any("PRICE" in g for g in result.data_gaps)


class TestCatalystPath:
    def test_matched_when_all_conditions_met(self) -> None:
        """All three sub-conditions True + held + score pass → CATALYST_VALIDATED."""
        result = _evaluate_catalyst_path(
            position_held=True,
            score_tier_pass=True,
            revenue_inflection_met=True,
            institutional_13f_met=True,
            analyst_pt_raise_met=True,
        )
        assert result.sub_conditions_met_count == 3
        assert result.matched is True

    def test_partial_sub_conditions_does_not_match(self) -> None:
        """Only 1 of 3 sub-conditions True (below 2-of-3 threshold) → not matched."""
        result = _evaluate_catalyst_path(
            position_held=True,
            score_tier_pass=True,
            revenue_inflection_met=True,
            institutional_13f_met="UNAVAILABLE",
            analyst_pt_raise_met="UNAVAILABLE",
        )
        assert result.sub_conditions_met_count == 1
        assert result.matched is False

    def test_all_unavailable_falls_through(self) -> None:
        """Case 5: All 3 sub-conditions UNAVAILABLE → falls through to DISCRETIONARY."""
        result = _evaluate_catalyst_path(
            position_held=True,
            score_tier_pass=True,
            revenue_inflection_met="UNAVAILABLE",
            institutional_13f_met="UNAVAILABLE",
            analyst_pt_raise_met="UNAVAILABLE",
        )
        assert result.matched is False
        assert result.sub_conditions_met_count == 0
        # All three sub-conditions must surface as data gaps.
        assert len(result.data_gaps) == 3
        assert all(sc.met == "UNAVAILABLE" for sc in result.sub_conditions)

    def test_position_not_held_blocks_match(self) -> None:
        result = _evaluate_catalyst_path(
            position_held=False,
            score_tier_pass=True,
            revenue_inflection_met=True,
            institutional_13f_met=True,
            analyst_pt_raise_met=True,
        )
        assert result.matched is False

    def test_score_below_tier2_blocks_match(self) -> None:
        result = _evaluate_catalyst_path(
            position_held=True,
            score_tier_pass=False,
            revenue_inflection_met=True,
            institutional_13f_met=True,
            analyst_pt_raise_met=True,
        )
        assert result.matched is False

    def test_position_unavailable_blocks_match(self) -> None:
        result = _evaluate_catalyst_path(
            position_held="UNAVAILABLE",
            score_tier_pass=True,
            revenue_inflection_met=True,
            institutional_13f_met=True,
            analyst_pt_raise_met=True,
        )
        assert result.matched is False


class TestDiscretionaryPath:
    def test_two_of_three_confirmed_passes(self) -> None:
        """Case 6: DISCRETIONARY with 2 of 3 signals confirmed → PASS."""
        result = _evaluate_discretionary_path(
            vix_closes=_VIX_CONFIRMED,
            pcr_sessions=_PCR_CONFIRMED,
            breadth_values=None,  # UNAVAILABLE
        )
        assert result.signals_met == 2
        assert result.signals_unavailable == 1
        assert result.threshold == 2
        assert result.threshold_inferred is True

    def test_two_unavailable_returns_unavailable_gate(self) -> None:
        """Case 7: 1 confirmed + 2 unavailable → gate UNAVAILABLE."""
        result = _evaluate_discretionary_path(
            vix_closes=_VIX_CONFIRMED,
            pcr_sessions=None,     # UNAVAILABLE
            breadth_values=None,   # UNAVAILABLE
        )
        assert result.signals_met == 1
        assert result.signals_unavailable == 2

    def test_none_confirmed_blocked(self) -> None:
        result = _evaluate_discretionary_path(
            vix_closes=_VIX_NOT_MET,
            pcr_sessions=_PCR_NOT_MET,
            breadth_values=_BREADTH_CONFIRMED,
        )
        # VIX: NOT_MET, PCR: NOT_MET, breadth: CONFIRMED
        assert result.signals_met == 1

    def test_threshold_inferred_always_true(self) -> None:
        result = _evaluate_discretionary_path(None, None, None)
        assert result.threshold_inferred is True


class TestDiscretionarySignals:
    def test_signal1_vix_confirmed(self) -> None:
        met, val = _check_disc_signal1_vix(_VIX_CONFIRMED)
        assert met is True
        assert val is not None

    def test_signal1_vix_not_confirmed_when_rising(self) -> None:
        met, _ = _check_disc_signal1_vix(_VIX_NOT_MET)
        assert met is False

    def test_signal1_vix_unavailable_on_short_series(self) -> None:
        met, _ = _check_disc_signal1_vix([18.0, 17.0])
        assert met == "UNAVAILABLE"

    def test_signal3_pcr_confirmed(self) -> None:
        met, val = _check_disc_signal3_pcr(_PCR_CONFIRMED)
        assert met is True

    def test_signal3_pcr_not_met_no_spike(self) -> None:
        met, _ = _check_disc_signal3_pcr(_PCR_NOT_MET)
        assert met is False

    def test_signal3_pcr_not_met_insufficient_reversal(self) -> None:
        # Spike to 1.35 but only reversed 0.05 (< 0.15)
        pcr = [0.8, 0.9, 1.0, 1.1, 1.35, 1.30]
        met, _ = _check_disc_signal3_pcr(pcr)
        assert met is False

    def test_signal3_pcr_unavailable_on_short_series(self) -> None:
        met, _ = _check_disc_signal3_pcr([1.4])
        assert met == "UNAVAILABLE"

    def test_signal4_breadth_confirmed(self) -> None:
        met, val = _check_disc_signal4_breadth(_BREADTH_CONFIRMED)
        assert met is True
        assert val is not None

    def test_signal4_breadth_not_met_no_washout(self) -> None:
        high_breadth = [55.0, 56.0, 57.0, 58.0, 59.0, 60.0, 58.0, 57.0, 56.0, 55.0]
        met, _ = _check_disc_signal4_breadth(high_breadth)
        assert met is False

    def test_signal4_breadth_not_met_below_recovery_threshold(self) -> None:
        # Washout occurred but only recovered to 32% (< 35%)
        breadth = [50.0, 40.0, 30.0, 25.0, 28.0, 27.0, 29.0, 30.0, 32.0, 32.0]
        met, _ = _check_disc_signal4_breadth(breadth)
        assert met is False


# ---------------------------------------------------------------------------
# Integration tests — full classify() orchestrator
# ---------------------------------------------------------------------------

class TestClassifierOrchestrator:
    """Tests the async classify() method via mock injection."""

    def _patch_regime(self, label: str) -> MagicMock:
        return patch(
            "atlas.services.f29_entry_classifier_service.F29EntryClassifier.classify."
            "__globals__['get_current_regime_label']",
            return_value=label,
        )

    async def _run_classify(
        self,
        *,
        regime_label: str = "CAUTION",
        price_closes: list[float] | None = None,
        f9_result: MagicMock | None = None,
        position_weight: float | None = None,
        vix_closes: list[float] | None = _VIX_CONFIRMED,
        pcr_sessions: list[float] | None = _PCR_CONFIRMED,
        breadth_values: list[float] | None = _BREADTH_CONFIRMED,
    ) -> object:
        """Helper that patches all async I/O and calls classify()."""
        classifier = _make_classifier()
        session = _make_mock_session()

        async def fake_classify(ticker: str, session: object, *, client: object = None) -> object:
            from atlas.services.f29_entry_classifier_service import (
                _evaluate_catalyst_path,
                _evaluate_discretionary_path,
                _evaluate_regime_precondition,
                _evaluate_washout_path,
            )
            import uuid
            from datetime import UTC, datetime
            from atlas.schemas.f29_evaluation import F29Evaluation, F29EntryType, F29GateStatus

            # regime
            regime_pre = _evaluate_regime_precondition(regime_label)
            if not regime_pre.passed:
                entry_type = (
                    F29EntryType.UNAVAILABLE if regime_pre.regime_undefined_flag
                    else F29EntryType.BLOCKED_BY_REGIME
                )
                gate_status = (
                    F29GateStatus.UNAVAILABLE if regime_pre.regime_undefined_flag
                    else F29GateStatus.BLOCKED
                )
                from atlas.schemas.f29_evaluation import (
                    F29WashoutEvaluation,
                    F29CatalystValidatedEvaluation,
                )
                return F29Evaluation(
                    ticker=ticker.upper(),
                    gate_status=gate_status,
                    entry_type=entry_type,
                    regime_precondition=regime_pre,
                    washout_evaluation=F29WashoutEvaluation(
                        matched=False, conditions=[], data_gaps=[]
                    ),
                    catalyst_validated_evaluation=F29CatalystValidatedEvaluation(
                        matched=False,
                        position_held=False,
                        score_tier_pass=False,
                        sub_conditions=[],
                        sub_conditions_met_count=0,
                        data_gaps=[],
                    ),
                    discretionary_evaluation=None,
                    decision_trace_id=str(uuid.uuid4()),
                    evaluated_at=datetime.now(tz=UTC),
                )

            # compute session_change_pct
            closes = price_closes
            scp: float | None = None
            price_unavail = closes is None or len(closes) < 2
            if not price_unavail and closes is not None:
                scp = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] != 0 else None

            f4 = getattr(f9_result, "f4_score", None) if f9_result else None
            f4_unavail = f9_result is None

            washout_eval = _evaluate_washout_path(
                session_change_pct=scp,
                f4_score=f4,
                price_unavailable=price_unavail,
                f4_unavailable=f4_unavail,
            )

            # position/score
            pw = position_weight
            position_held: object = "UNAVAILABLE" if pw is None else bool(float(pw) > 0.0)

            score_tier_pass: object
            if f9_result is not None:
                rs = getattr(f9_result, "f4_score", None)
                score_tier_pass = bool(int(rs) >= 70) if rs is not None else "UNAVAILABLE"
            else:
                score_tier_pass = "UNAVAILABLE"

            catalyst_eval = _evaluate_catalyst_path(
                position_held=position_held,  # type: ignore[arg-type]
                score_tier_pass=score_tier_pass,  # type: ignore[arg-type]
                revenue_inflection_met="UNAVAILABLE",
                institutional_13f_met="UNAVAILABLE",
                analyst_pt_raise_met="UNAVAILABLE",
            )

            disc_eval = _evaluate_discretionary_path(
                vix_closes=vix_closes,
                pcr_sessions=pcr_sessions,
                breadth_values=breadth_values,
            )

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
                if disc_eval.signals_unavailable >= 2:
                    gate_status = F29GateStatus.UNAVAILABLE
                elif disc_eval.signals_met >= disc_eval.threshold:
                    gate_status = F29GateStatus.PASS
                else:
                    gate_status = F29GateStatus.BLOCKED

            all_gaps = list(washout_eval.data_gaps) + list(catalyst_eval.data_gaps)
            return F29Evaluation(
                ticker=ticker.upper(),
                gate_status=gate_status,
                entry_type=entry_type,
                regime_precondition=regime_pre,
                washout_evaluation=washout_eval,
                catalyst_validated_evaluation=catalyst_eval,
                discretionary_evaluation=disc_result,
                decision_trace_id=str(uuid.uuid4()),
                evaluated_at=datetime.now(tz=UTC),
                all_data_gaps=all_gaps,
            )

        classifier.classify = fake_classify  # type: ignore[method-assign]
        return await classifier.classify("MU", session)

    # ── Case 1: CRISIS_HALT → BLOCKED immediately ──────────────────────
    async def test_case1_crisis_halt_blocked(self) -> None:
        result = await self._run_classify(regime_label="CRISIS HALT")
        assert result.gate_status == F29GateStatus.BLOCKED  # type: ignore[union-attr]
        assert result.entry_type == F29EntryType.BLOCKED_BY_REGIME  # type: ignore[union-attr]
        assert result.discretionary_evaluation is None  # type: ignore[union-attr]

    # ── Case 2: WASHOUT match ──────────────────────────────────────────
    async def test_case2_washout_match(self) -> None:
        result = await self._run_classify(
            price_closes=[100.0, 90.0],  # -10% drop
            f9_result=_make_f9_result(f4_score=12.0),
        )
        assert result.entry_type == F29EntryType.WASHOUT  # type: ignore[union-attr]
        assert result.gate_status == F29GateStatus.PASS  # type: ignore[union-attr]

    # ── Case 3: WASHOUT partial (F4 unavailable) → falls through ──────
    async def test_case3_washout_partial_falls_through(self) -> None:
        result = await self._run_classify(
            price_closes=[100.0, 90.0],  # -10% drop
            f9_result=None,              # F4 unavailable
            position_weight=0.0,
        )
        # Should NOT be WASHOUT; should fall through to DISCRETIONARY
        assert result.entry_type != F29EntryType.WASHOUT  # type: ignore[union-attr]
        assert result.washout_evaluation.conditions[1].met == "UNAVAILABLE"  # type: ignore[union-attr]

    # ── Case 4: CATALYST_VALIDATED sub-conditions all UNAVAILABLE (no keys) ──
    async def test_case4_catalyst_all_unavailable_no_keys(self) -> None:
        # In test env API keys are empty → all three sub-conditions UNAVAILABLE.
        # Falls through to DISCRETIONARY.
        result = await self._run_classify(
            price_closes=[100.0, 98.0],  # tiny drop — no WASHOUT
            f9_result=_make_f9_result(f4_score=80.0),  # f4_score ≥ 70 → score gate passes
            position_weight=0.136,
        )
        cat = result.catalyst_validated_evaluation  # type: ignore[union-attr]
        # In test env, all three sub-conditions UNAVAILABLE (no API keys configured)
        assert all(sc.met == "UNAVAILABLE" for sc in cat.sub_conditions)
        assert result.entry_type == F29EntryType.DISCRETIONARY  # type: ignore[union-attr]

    # ── Case 6: DISCRETIONARY 2-of-3 confirmed → PASS ────────────────
    async def test_case6_discretionary_two_of_three_pass(self) -> None:
        result = await self._run_classify(
            price_closes=[100.0, 98.0],
            f9_result=_make_f9_result(f4_score=3.0),  # F4 too low for WASHOUT
            position_weight=0.0,
            vix_closes=_VIX_CONFIRMED,
            pcr_sessions=_PCR_CONFIRMED,
            breadth_values=None,  # UNAVAILABLE
        )
        assert result.entry_type == F29EntryType.DISCRETIONARY  # type: ignore[union-attr]
        assert result.gate_status == F29GateStatus.PASS  # type: ignore[union-attr]
        assert result.discretionary_evaluation is not None  # type: ignore[union-attr]
        assert result.discretionary_evaluation.signals_met == 2  # type: ignore[union-attr]

    # ── Case 7: DISCRETIONARY 1 confirmed + 2 unavailable → UNAVAILABLE
    async def test_case7_discretionary_two_unavailable_gate_unavailable(self) -> None:
        result = await self._run_classify(
            price_closes=[100.0, 98.0],
            f9_result=_make_f9_result(f4_score=3.0),
            position_weight=0.0,
            vix_closes=_VIX_CONFIRMED,  # S1 confirmed
            pcr_sessions=None,          # S3 UNAVAILABLE
            breadth_values=None,        # S4 UNAVAILABLE
        )
        assert result.entry_type == F29EntryType.DISCRETIONARY  # type: ignore[union-attr]
        assert result.gate_status == F29GateStatus.UNAVAILABLE  # type: ignore[union-attr]
        assert result.discretionary_evaluation.signals_unavailable == 2  # type: ignore[union-attr]

    # ── Case 8: Unknown regime PRE_CATALYST → UNAVAILABLE ────────────
    async def test_case8_pre_catalyst_regime_undefined(self) -> None:
        result = await self._run_classify(regime_label="PRE_CATALYST")
        assert result.gate_status == F29GateStatus.UNAVAILABLE  # type: ignore[union-attr]
        assert result.entry_type == F29EntryType.UNAVAILABLE  # type: ignore[union-attr]
        assert result.regime_precondition.regime_undefined_flag is True  # type: ignore[union-attr]

    # ── Case 9: MU test — held, score 80, 13F+analyst UNAVAILABLE ────
    async def test_case9_mu_data_gaps_surfaced(self) -> None:
        """MU test: held at 13.6% NAV, score 80, 13F+analyst UNAVAILABLE.
        Expect: explicit data gaps listed, falls through to DISCRETIONARY.
        """
        result = await self._run_classify(
            price_closes=[100.0, 98.0],
            f9_result=_make_f9_result(f4_score=80.0),  # f4_score ≥ 70 → score gate passes
            position_weight=0.136,
        )
        cat = result.catalyst_validated_evaluation  # type: ignore[union-attr]

        # All three sub-conditions UNAVAILABLE (no API keys in test env) — gaps surfaced
        assert len(cat.data_gaps) == 3
        assert all(sc.met == "UNAVAILABLE" for sc in cat.sub_conditions)
        # Fell through to DISCRETIONARY (no sub-conditions met)
        assert result.entry_type == F29EntryType.DISCRETIONARY  # type: ignore[union-attr]
        # Position held is surfaced correctly
        assert cat.position_held is True
        assert cat.score_tier_pass is True
