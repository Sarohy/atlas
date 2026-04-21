"""Unit tests for RegimeModifierService pure helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from atlas.services.regime_modifier_service import (
    _count_consecutive_brent_closes_below_95,
    _compute_regime_output,
    _determine_rule,
    _derive_effective_regime,
    _parse_yahoo_vix_payload,
)

# ---------------------------------------------------------------------------
# _determine_rule
# ---------------------------------------------------------------------------


class TestDetermineRule:
    """Verify rule-trigger logic for all four regime rules.

    Each rule requires BOTH specific market conditions AND a specific
    geopolitical state.  No rule fires when conditions don't align.
    """

    # ── Rule 1 — CRISIS HALT ───────────────────────────────────────────────

    def test_rule1_triggers_on_brent_above_110_and_escalating(self) -> None:
        rule = _determine_rule(
            brent_price=111.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ESCALATING",
        )
        assert rule == 1

    def test_rule1_triggers_on_vix_above_35_and_escalating(self) -> None:
        rule = _determine_rule(
            brent_price=80.0,
            vix_value=36.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ESCALATING",
        )
        assert rule == 1

    def test_rule1_does_not_trigger_without_escalating_geo(self) -> None:
        rule = _determine_rule(
            brent_price=120.0,
            vix_value=40.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule != 1

    def test_rule1_does_not_trigger_when_market_is_calm_despite_escalating(self) -> None:
        rule = _determine_rule(
            brent_price=80.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="ESCALATING",
        )
        assert rule != 1

    # ── Rule 2 — CAUTION ───────────────────────────────────────────────────

    def test_rule2_triggers_on_brent_in_caution_band_and_active_risk(self) -> None:
        rule = _determine_rule(
            brent_price=100.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 2

    def test_rule2_triggers_on_vix_in_caution_range_and_active_risk(self) -> None:
        rule = _determine_rule(
            brent_price=80.0,
            vix_value=28.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 2

    def test_rule2_triggers_at_brent_lower_boundary(self) -> None:
        rule = _determine_rule(
            brent_price=95.0,
            vix_value=18.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 2

    def test_rule2_triggers_at_brent_upper_boundary(self) -> None:
        rule = _determine_rule(
            brent_price=110.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 2

    def test_rule2_does_not_trigger_without_active_risk_geo(self) -> None:
        """No specific rule matches → falls back to default CAUTION (rule 2)."""
        rule = _determine_rule(
            brent_price=100.0,
            vix_value=28.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="NONE",
        )
        assert rule == 2

    # ── Rule 3 — SOFT CAUTION ──────────────────────────────────────────────

    def test_rule3_triggers_when_conditions_met_and_de_escalating(self) -> None:
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=1,
            geopolitical_state="DE_ESCALATING",
        )
        assert rule == 3

    def test_rule3_does_not_trigger_when_brent_above_100(self) -> None:
        rule = _determine_rule(
            brent_price=102.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=1,
            geopolitical_state="DE_ESCALATING",
        )
        assert rule != 3

    def test_rule3_does_not_trigger_when_vix_above_22(self) -> None:
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=23.0,
            brent_consecutive_below_95_count=1,
            geopolitical_state="DE_ESCALATING",
        )
        assert rule != 3

    def test_rule3_does_not_trigger_when_streak_is_2(self) -> None:
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="DE_ESCALATING",
        )
        assert rule != 3

    def test_rule3_does_not_trigger_without_de_escalating_geo(self) -> None:
        """No specific rule matches → falls back to default CAUTION (rule 2)."""
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=1,
            geopolitical_state="NONE",
        )
        assert rule == 2

    # ── Rule 4 — CLEAR ─────────────────────────────────────────────────────

    def test_rule4_triggers_when_both_conditions_met_and_resolved(self) -> None:
        rule = _determine_rule(
            brent_price=90.0,
            vix_value=22.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="RESOLVED",
        )
        assert rule == 4

    def test_rule4_does_not_trigger_with_single_brent_close(self) -> None:
        rule = _determine_rule(
            brent_price=90.0,
            vix_value=22.0,
            brent_consecutive_below_95_count=1,
            geopolitical_state="RESOLVED",
        )
        assert rule != 4

    def test_rule4_does_not_trigger_without_resolved_geo(self) -> None:
        """No specific rule matches → falls back to default CAUTION (rule 2)."""
        rule = _determine_rule(
            brent_price=90.0,
            vix_value=22.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="NONE",
        )
        assert rule == 2

    # ── Default fallback ───────────────────────────────────────────────────

    def test_default_fallback_is_caution_when_geo_is_none(self) -> None:
        """When no rule fires, CAUTION (rule 2) is the default."""
        rule = _determine_rule(
            brent_price=85.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="NONE",
        )
        assert rule == 2


class TestConsecutiveBrentClosesBelow95:
    """Verify the streak counter used for the automatic clear regime."""

    def test_counts_two_consecutive_closes_below_95(self) -> None:
        assert _count_consecutive_brent_closes_below_95([94.8, 94.1]) == 2

    def test_counts_only_the_first_close_when_second_breaks_the_streak(self) -> None:
        assert _count_consecutive_brent_closes_below_95([94.8, 96.0]) == 1

    def test_returns_zero_when_the_latest_close_is_not_below_95(self) -> None:
        assert _count_consecutive_brent_closes_below_95([96.2, 94.0]) == 0


class TestDeriveEffectiveRegime:
    """Verify _derive_effective_regime returns _rule_name(rule).

    Geopolitical state is now integrated into rule determination, so the
    effective regime is always the automatic regime label.
    """

    def test_rule1_gives_crisis_halt(self) -> None:
        assert _derive_effective_regime(automatic_rule=1, geopolitical_state="ESCALATING") == "CRISIS HALT"

    def test_rule2_gives_caution(self) -> None:
        assert _derive_effective_regime(automatic_rule=2, geopolitical_state="ACTIVE_RISK") == "CAUTION"

    def test_rule3_gives_soft_caution(self) -> None:
        assert _derive_effective_regime(automatic_rule=3, geopolitical_state="DE_ESCALATING") == "SOFT CAUTION"

    def test_rule4_gives_clear(self) -> None:
        assert _derive_effective_regime(automatic_rule=4, geopolitical_state="RESOLVED") == "CLEAR"

    def test_none_gives_normal(self) -> None:
        assert _derive_effective_regime(automatic_rule=None, geopolitical_state="NONE") == "NORMAL"


# ---------------------------------------------------------------------------
# _compute_regime_output
# ---------------------------------------------------------------------------


class TestComputeRegimeOutput:
    """Verify score adjustment, cash bounds, and output text per rule."""

    # ── Rule 1 ──────────────────────────────────────────────────────────────

    def test_rule1_deducts_10_from_score(self) -> None:
        adjusted, *_ = _compute_regime_output(1, 75, None)
        assert adjusted == 65

    def test_rule1_clamps_score_at_zero(self) -> None:
        adjusted, *_ = _compute_regime_output(1, 8, None)
        assert adjusted == 0

    def test_rule1_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(1, 75, None)
        assert min_pct == pytest.approx(0.35)
        assert max_pct == pytest.approx(0.40)

    def test_rule1_cash_usd_from_position_value(self) -> None:
        position_value = Decimal("10000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(1, 75, position_value)
        assert min_usd == Decimal("3500.00")
        assert max_usd == Decimal("4000.00")

    def test_rule1_cash_usd_none_when_no_position(self) -> None:
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(1, 75, None)
        assert min_usd is None
        assert max_usd is None

    def test_rule1_output_text(self) -> None:
        *_, output_text = _compute_regime_output(1, 75, None)
        assert "must stay in cash" in output_text
        assert "cannot be touched" in output_text
        assert "for any trade" in output_text

    # ── Rule 2 ──────────────────────────────────────────────────────────────

    def test_rule2_deducts_5_from_score(self) -> None:
        adjusted, *_ = _compute_regime_output(2, 80, None)
        assert adjusted == 75

    def test_rule2_clamps_score_at_zero(self) -> None:
        adjusted, *_ = _compute_regime_output(2, 3, None)
        assert adjusted == 0

    def test_rule2_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(2, 80, None)
        assert min_pct == pytest.approx(0.25)
        assert max_pct == pytest.approx(0.35)

    def test_rule2_cash_usd_from_position_value(self) -> None:
        position_value = Decimal("20000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(2, 80, position_value)
        assert min_usd == Decimal("5000.00")
        assert max_usd == Decimal("7000.00")

    def test_rule2_output_text(self) -> None:
        *_, output_text = _compute_regime_output(2, 80, None)
        assert "must stay in cash" in output_text

    # ── Rule 3 — SOFT CAUTION ───────────────────────────────────────────────

    def test_rule3_deducts_3_from_score(self) -> None:
        adjusted, *_ = _compute_regime_output(3, 80, None)
        assert adjusted == 77

    def test_rule3_clamps_score_at_zero(self) -> None:
        adjusted, *_ = _compute_regime_output(3, 2, None)
        assert adjusted == 0

    def test_rule3_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(3, 80, None)
        assert min_pct == pytest.approx(0.15)
        assert max_pct == pytest.approx(0.25)

    def test_rule3_cash_usd_from_position_value(self) -> None:
        position_value = Decimal("20000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(3, 80, position_value)
        assert min_usd == Decimal("3000.00")
        assert max_usd == Decimal("5000.00")

    def test_rule3_output_text(self) -> None:
        *_, output_text = _compute_regime_output(3, 80, None)
        assert "reduce exposure" in output_text

    # ── Rule 4 — CLEAR ──────────────────────────────────────────────────────

    def test_rule4_adds_5_to_score(self) -> None:
        adjusted, *_ = _compute_regime_output(4, 70, None)
        assert adjusted == 75

    def test_rule4_clamps_score_at_100(self) -> None:
        adjusted, *_ = _compute_regime_output(4, 97, None)
        assert adjusted == 100

    def test_rule4_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(4, 70, None)
        assert min_pct == pytest.approx(0.10)
        assert max_pct == pytest.approx(0.12)

    def test_rule4_cash_usd_from_position_value(self) -> None:
        position_value = Decimal("50000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(4, 70, position_value)
        assert min_usd == Decimal("5000.00")
        assert max_usd == Decimal("6000.00")

    def test_rule4_output_text(self) -> None:
        *_, output_text = _compute_regime_output(4, 70, None)
        assert "only this stays in cash" in output_text
        assert "everything else" in output_text
        assert "can be deployed" in output_text

    # ── No rule ─────────────────────────────────────────────────────────────

    def test_no_rule_preserves_score(self) -> None:
        adjusted, *_ = _compute_regime_output(None, 82, None)
        assert adjusted == 82

    def test_no_rule_zero_cash_percentages(self) -> None:
        _, min_pct, max_pct, *_ = _compute_regime_output(None, 82, None)
        assert min_pct == pytest.approx(0.0)
        assert max_pct == pytest.approx(0.0)

    def test_no_rule_zero_cash_usd(self) -> None:
        position_value = Decimal("10000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(None, 82, position_value)
        assert min_usd is None
        assert max_usd is None


# ---------------------------------------------------------------------------
# active_war with no market data — regression for Rule 1 via _compute_regime_output
# ---------------------------------------------------------------------------


class TestActiveWarNoMarketData:
    """Verify Rule 1 output is correct when active_war=True but Brent/VIX are null.

    The service sets rule=1 directly when market data is absent but active_war
    is True.  _compute_regime_output(1, base_score, ...) must still return the
    correct crisis adjustment.
    """

    def test_rule1_fires_with_score_57(self) -> None:
        """base_score=57, active_war=True, no market data → adjusted=47."""
        adjusted, min_pct, max_pct, *_ = _compute_regime_output(1, 57, None)
        assert adjusted == 47
        assert min_pct == pytest.approx(0.35)
        assert max_pct == pytest.approx(0.40)

    def test_rule1_output_text_present_with_score_57(self) -> None:
        *_, output_text = _compute_regime_output(1, 57, None)
        assert output_text != ""

    def test_rule1_usd_guidance_when_position_known(self) -> None:
        """Position value $10 000 → min $3 500, max $4 000 cash required."""
        position = Decimal("10000")
        _, _, _, min_usd, max_usd, _ = _compute_regime_output(1, 57, position)
        assert min_usd == pytest.approx(3500.0)
        assert max_usd == pytest.approx(4000.0)


# ---------------------------------------------------------------------------
# _parse_yahoo_vix_payload — pure parser for Yahoo Finance chart API response
# ---------------------------------------------------------------------------


class TestParseYahooVixPayload:
    """Verify VIX extraction from Yahoo Finance chart API payloads."""

    def _make_payload(self, price: float | None) -> dict:
        meta: dict = {"symbol": "^VIX"}
        if price is not None:
            meta["regularMarketPrice"] = price
        return {"chart": {"result": [{"meta": meta}]}}

    def test_returns_float_from_valid_payload(self) -> None:
        payload = self._make_payload(19.99)
        assert _parse_yahoo_vix_payload(payload) == pytest.approx(19.99)

    def test_returns_none_when_result_list_is_empty(self) -> None:
        payload: dict = {"chart": {"result": []}}
        assert _parse_yahoo_vix_payload(payload) is None

    def test_returns_none_when_result_is_null(self) -> None:
        payload: dict = {"chart": {"result": None}}
        assert _parse_yahoo_vix_payload(payload) is None

    def test_returns_none_when_price_key_missing(self) -> None:
        payload = self._make_payload(None)
        assert _parse_yahoo_vix_payload(payload) is None

    def test_returns_none_on_empty_dict(self) -> None:
        assert _parse_yahoo_vix_payload({}) is None

    def test_handles_integer_price(self) -> None:
        payload = self._make_payload(20.0)
        result = _parse_yahoo_vix_payload(payload)
        assert isinstance(result, float)
        assert result == pytest.approx(20.0)
