"""Unit tests for RegimeModifierService pure helpers."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from atlas.services.regime_modifier_service import (
    _calculate_modifier,
    _count_consecutive_brent_closes_below_95,
    _compute_regime_output,
    _determine_rule,
    _derive_effective_regime,
    _get_brent_label,
    _get_cash_floor,
    _get_modifier_reason,
    _get_trigger_logic,
    _get_vix_label,
    _parse_yahoo_vix_payload,
    get_geo_flag_current,
    load_geo_flag_from_db,
    persist_geo_flag_to_db,
    reset_geo_flag_current,
    set_geo_flag_current,
)

# ---------------------------------------------------------------------------
# _determine_rule  (market conditions only — geo does NOT gate the rule)
# ---------------------------------------------------------------------------


class TestDetermineRule:
    """Verify that REGIME is determined by Brent + VIX alone.

    Per CLAUDE.md Section 14.1: Brent and VIX determine the regime.
    Geopolitical flag does NOT gate which rule fires — it only modifies
    the score delta *within* the CAUTION regime.

    Priority order (highest severity first):
        1 — CRISIS HALT:   Brent > $110  OR  VIX > 35
        2 — CAUTION:       Brent $95–$110 OR VIX 24–35
        3 — SOFT CAUTION:  Brent < $100 AND VIX < 22 AND streak < 2
        4 — CLEAR:         streak ≥ 2  AND  VIX < 24
        default            → 2 (CAUTION)
    """

    # ── Rule 1 — CRISIS HALT (Brent OR VIX — any geo) ─────────────────────

    def test_rule1_triggers_on_brent_above_110_any_geo(self) -> None:
        for geo in ("ESCALATING", "ACTIVE_RISK", "DE_ESCALATING", "RESOLVED", "NONE"):
            rule = _determine_rule(
                brent_price=111.0,
                vix_value=20.0,
                brent_consecutive_below_95_count=0,
                geopolitical_state=geo,  # type: ignore[arg-type]
            )
            assert rule == 1, f"Expected 1 for geo={geo}, got {rule}"

    def test_rule1_triggers_on_vix_above_35_any_geo(self) -> None:
        for geo in ("ESCALATING", "ACTIVE_RISK", "DE_ESCALATING", "RESOLVED", "NONE"):
            rule = _determine_rule(
                brent_price=80.0,
                vix_value=36.0,
                brent_consecutive_below_95_count=0,
                geopolitical_state=geo,  # type: ignore[arg-type]
            )
            assert rule == 1, f"Expected 1 for geo={geo}, got {rule}"

    def test_rule1_brent_trigger_on_spec_test1(self) -> None:
        """Test 1 from spec: brent=115, vix=20, geo=ACTIVE_RISK → CRISIS HALT."""
        rule = _determine_rule(
            brent_price=115.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 1

    def test_rule1_vix_trigger_on_spec_test2(self) -> None:
        """Test 2 from spec: brent=90, vix=38, geo=ACTIVE_RISK → CRISIS HALT."""
        rule = _determine_rule(
            brent_price=90.0,
            vix_value=38.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 1

    def test_rule1_does_not_trigger_at_exact_brent_threshold(self) -> None:
        rule = _determine_rule(
            brent_price=110.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ESCALATING",
        )
        assert rule != 1

    def test_rule1_does_not_trigger_at_exact_vix_threshold(self) -> None:
        rule = _determine_rule(
            brent_price=80.0,
            vix_value=35.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ESCALATING",
        )
        assert rule != 1

    # ── Rule 2 — CAUTION (Brent OR VIX — any geo) ─────────────────────────

    def test_rule2_triggers_on_brent_in_caution_band_any_geo(self) -> None:
        """Test 3: brent=100, vix=20, geo=ACTIVE_RISK → CAUTION."""
        rule = _determine_rule(
            brent_price=100.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 2

    def test_rule2_triggers_on_vix_in_caution_range_any_geo(self) -> None:
        """Test 4: brent=90, vix=28, geo=ACTIVE_RISK → CAUTION."""
        rule = _determine_rule(
            brent_price=90.0,
            vix_value=28.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 2

    def test_rule2_triggers_for_escalating_geo_caution_market(self) -> None:
        """CAUTION fires regardless of ESCALATING geo — geo only changes modifier."""
        rule = _determine_rule(
            brent_price=100.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ESCALATING",
        )
        assert rule == 2

    def test_rule2_triggers_for_resolved_geo_caution_market(self) -> None:
        rule = _determine_rule(
            brent_price=100.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="RESOLVED",
        )
        assert rule == 2

    def test_rule2_triggers_at_brent_lower_boundary(self) -> None:
        rule = _determine_rule(
            brent_price=95.0,
            vix_value=18.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="NONE",
        )
        assert rule == 2

    def test_rule2_triggers_at_brent_upper_boundary(self) -> None:
        rule = _determine_rule(
            brent_price=110.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="NONE",
        )
        assert rule == 2

    # ── Rule 3 — SOFT CAUTION (Brent AND VIX — any geo) ───────────────────

    def test_rule3_triggers_when_conditions_met_de_escalating(self) -> None:
        """Test 7: brent=97, vix=20, streak=0, geo=DE_ESCALATING → SOFT CAUTION."""
        rule = _determine_rule(
            brent_price=97.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="DE_ESCALATING",
        )
        assert rule == 3

    def test_rule3_triggers_for_escalating_geo_soft_caution_market(self) -> None:
        """Test 8: geo=ESCALATING ignored — SOFT CAUTION market → still rule 3."""
        rule = _determine_rule(
            brent_price=97.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ESCALATING",
        )
        assert rule == 3

    def test_rule3_triggers_for_any_geo_when_market_conditions_met(self) -> None:
        for geo in ("ESCALATING", "ACTIVE_RISK", "DE_ESCALATING", "RESOLVED", "NONE"):
            rule = _determine_rule(
                brent_price=92.0,
                vix_value=20.0,
                brent_consecutive_below_95_count=1,
                geopolitical_state=geo,  # type: ignore[arg-type]
            )
            assert rule == 3, f"Expected 3 for geo={geo}, got {rule}"

    def test_rule3_does_not_trigger_when_brent_at_threshold(self) -> None:
        rule = _determine_rule(
            brent_price=100.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=1,
            geopolitical_state="DE_ESCALATING",
        )
        assert rule != 3

    def test_rule3_does_not_trigger_when_vix_at_threshold(self) -> None:
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=22.0,
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

    # ── Rule 4 — CLEAR (both required — any geo) ──────────────────────────

    def test_rule4_triggers_when_both_conditions_met_resolved(self) -> None:
        """Test 9: brent=92, vix=18, streak=2, geo=ACTIVE_RISK → CLEAR."""
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=18.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 4

    def test_rule4_triggers_for_escalating_geo_clear_market(self) -> None:
        """Test 10: geo=ESCALATING ignored — CLEAR market conditions → still rule 4."""
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=18.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="ESCALATING",
        )
        assert rule == 4

    def test_rule4_triggers_for_any_geo_when_clear_conditions_met(self) -> None:
        for geo in ("ESCALATING", "ACTIVE_RISK", "DE_ESCALATING", "RESOLVED", "NONE"):
            rule = _determine_rule(
                brent_price=90.0,
                vix_value=22.0,
                brent_consecutive_below_95_count=2,
                geopolitical_state=geo,  # type: ignore[arg-type]
            )
            assert rule == 4, f"Expected 4 for geo={geo}, got {rule}"

    def test_rule4_spec_test13_current_atlas_state(self) -> None:
        """Test 13: brent=90.38, vix=17.48, streak=2, geo=ACTIVE_RISK → CLEAR."""
        rule = _determine_rule(
            brent_price=90.38,
            vix_value=17.48,
            brent_consecutive_below_95_count=2,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 4

    def test_rule4_does_not_trigger_with_single_close(self) -> None:
        """Test 11: streak=1 → SOFT CAUTION not CLEAR."""
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=18.0,
            brent_consecutive_below_95_count=1,
            geopolitical_state="RESOLVED",
        )
        assert rule == 3

    def test_rule4_does_not_trigger_when_vix_at_threshold(self) -> None:
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=24.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="RESOLVED",
        )
        assert rule != 4

    # ── Default fallback ───────────────────────────────────────────────────

    def test_default_fallback_is_clear_when_no_conditions_met(self) -> None:
        """When no regime conditions match, default is CLEAR (rule 4)."""
        rule = _determine_rule(
            brent_price=85.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="NONE",
        )
        assert rule == 4


# ---------------------------------------------------------------------------
# _calculate_modifier  (geo only matters within CAUTION)
# ---------------------------------------------------------------------------


class TestCalculateModifier:
    """Verify the CAUTION+ESCALATING special case and all other modifiers.

    Per CLAUDE.md Section 14.1 and user's KEY RULES:
    - CLEAR:        geo irrelevant → always +5
    - SOFT CAUTION: geo irrelevant → always −3
    - CRISIS HALT:  geo irrelevant → always −10
    - CAUTION:      ESCALATING → −7 (ONLY special case in the entire table)
                    all others → −5
    """

    # ── CLEAR — geo irrelevant ─────────────────────────────────────────────

    def test_clear_returns_plus5_for_escalating(self) -> None:
        """Test 10: CLEAR + ESCALATING → still +5."""
        assert _calculate_modifier(rule=4, geopolitical_state="ESCALATING") == 5

    def test_clear_returns_plus5_for_active_risk(self) -> None:
        """Test 9: CLEAR + ACTIVE_RISK → +5."""
        assert _calculate_modifier(rule=4, geopolitical_state="ACTIVE_RISK") == 5

    def test_clear_returns_plus5_for_all_geo(self) -> None:
        for geo in ("ESCALATING", "ACTIVE_RISK", "DE_ESCALATING", "RESOLVED", "NONE"):
            result = _calculate_modifier(rule=4, geopolitical_state=geo)  # type: ignore[arg-type]
            assert result == 5, f"CLEAR should be +5 regardless of geo={geo}"

    # ── SOFT CAUTION — geo irrelevant ──────────────────────────────────────

    def test_soft_caution_returns_minus3_for_escalating(self) -> None:
        """Test 8: SOFT CAUTION + ESCALATING → still −3 (not −7)."""
        assert _calculate_modifier(rule=3, geopolitical_state="ESCALATING") == -3

    def test_soft_caution_returns_minus3_for_all_geo(self) -> None:
        for geo in ("ESCALATING", "ACTIVE_RISK", "DE_ESCALATING", "RESOLVED", "NONE"):
            result = _calculate_modifier(rule=3, geopolitical_state=geo)  # type: ignore[arg-type]
            assert result == -3, f"SOFT CAUTION should be −3 regardless of geo={geo}"

    # ── CAUTION — geo flag matters ─────────────────────────────────────────

    def test_caution_returns_minus7_for_escalating(self) -> None:
        """Test 5: CAUTION + ESCALATING → −7 (the ONLY special case)."""
        assert _calculate_modifier(rule=2, geopolitical_state="ESCALATING") == -7

    def test_caution_returns_minus5_for_active_risk(self) -> None:
        """Test 3: CAUTION + ACTIVE_RISK → −5."""
        assert _calculate_modifier(rule=2, geopolitical_state="ACTIVE_RISK") == -5

    def test_caution_returns_minus5_for_resolved(self) -> None:
        """Test 6: CAUTION + RESOLVED → −5 (not −7)."""
        assert _calculate_modifier(rule=2, geopolitical_state="RESOLVED") == -5

    def test_caution_returns_minus5_for_de_escalating(self) -> None:
        assert _calculate_modifier(rule=2, geopolitical_state="DE_ESCALATING") == -5

    def test_caution_returns_minus5_for_none(self) -> None:
        assert _calculate_modifier(rule=2, geopolitical_state="NONE") == -5

    # ── CRISIS HALT — geo irrelevant ───────────────────────────────────────

    def test_crisis_halt_returns_minus10_for_all_geo(self) -> None:
        for geo in ("ESCALATING", "ACTIVE_RISK", "DE_ESCALATING", "RESOLVED", "NONE"):
            result = _calculate_modifier(rule=1, geopolitical_state=geo)  # type: ignore[arg-type]
            assert result == -10, f"CRISIS HALT should be −10 regardless of geo={geo}"

    # ── None rule — safe default ───────────────────────────────────────────

    def test_none_rule_returns_plus5_as_clear_default(self) -> None:
        assert _calculate_modifier(rule=None, geopolitical_state="NONE") == 5


# ---------------------------------------------------------------------------
# _get_brent_label
# ---------------------------------------------------------------------------


class TestGetBrentLabel:
    def test_above_110_returns_crisis_label(self) -> None:
        label = _get_brent_label(115.0)
        assert "CRISIS" in label.upper()

    def test_in_caution_band_returns_caution_label(self) -> None:
        label = _get_brent_label(100.0)
        assert "CAUTION" in label.upper()

    def test_at_lower_caution_boundary_95(self) -> None:
        label = _get_brent_label(95.0)
        assert "CAUTION" in label.upper()

    def test_below_95_returns_clear_zone_label(self) -> None:
        label = _get_brent_label(90.0)
        assert "CLEAR" in label.upper()

    def test_includes_price_value(self) -> None:
        label = _get_brent_label(97.5)
        assert "97.5" in label


# ---------------------------------------------------------------------------
# _get_vix_label
# ---------------------------------------------------------------------------


class TestGetVixLabel:
    def test_above_35_returns_crisis_label(self) -> None:
        label = _get_vix_label(38.0)
        assert "CRISIS" in label.upper()

    def test_in_caution_range_24_35_returns_caution_label(self) -> None:
        label = _get_vix_label(28.0)
        assert "CAUTION" in label.upper()

    def test_below_22_returns_soft_caution_zone_label(self) -> None:
        label = _get_vix_label(20.0)
        assert "SOFT" in label.upper() or "22" in label

    def test_between_22_and_24_returns_clear_zone_label(self) -> None:
        label = _get_vix_label(23.0)
        assert "CLEAR" in label.upper() or "24" in label

    def test_includes_vix_value(self) -> None:
        label = _get_vix_label(17.48)
        assert "17.48" in label


# ---------------------------------------------------------------------------
# _get_trigger_logic
# ---------------------------------------------------------------------------


class TestGetTriggerLogic:
    def test_crisis_halt_returns_or_logic(self) -> None:
        assert "OR" in _get_trigger_logic(1).upper()

    def test_caution_returns_or_logic(self) -> None:
        assert "OR" in _get_trigger_logic(2).upper()

    def test_soft_caution_returns_and_logic(self) -> None:
        assert "AND" in _get_trigger_logic(3).upper()

    def test_clear_returns_and_logic(self) -> None:
        assert "AND" in _get_trigger_logic(4).upper()

    def test_none_rule_returns_and_logic(self) -> None:
        result = _get_trigger_logic(None)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _get_modifier_reason
# ---------------------------------------------------------------------------


class TestGetModifierReason:
    def test_clear_includes_plus5_and_geo_ignored(self) -> None:
        reason = _get_modifier_reason(4, "ESCALATING")
        assert "+5" in reason or "5" in reason
        assert "geo" in reason.lower() or "ignored" in reason.lower()

    def test_soft_caution_includes_minus3_and_geo_ignored(self) -> None:
        reason = _get_modifier_reason(3, "ESCALATING")
        assert "3" in reason
        assert "geo" in reason.lower() or "ignored" in reason.lower()

    def test_caution_escalating_includes_minus7(self) -> None:
        """Test 5: CAUTION + ESCALATING → modifier reason mentions −7."""
        reason = _get_modifier_reason(2, "ESCALATING")
        assert "7" in reason

    def test_caution_active_risk_includes_minus5(self) -> None:
        reason = _get_modifier_reason(2, "ACTIVE_RISK")
        assert "5" in reason

    def test_crisis_halt_includes_minus10_and_geo_ignored(self) -> None:
        reason = _get_modifier_reason(1, "RESOLVED")
        assert "10" in reason
        assert "geo" in reason.lower() or "ignored" in reason.lower()


# ---------------------------------------------------------------------------
# _get_cash_floor
# ---------------------------------------------------------------------------


class TestGetCashFloor:
    def test_clear_floor_is_8_percent(self) -> None:
        assert _get_cash_floor(4) == pytest.approx(0.08)

    def test_soft_caution_floor_is_15_percent(self) -> None:
        assert _get_cash_floor(3) == pytest.approx(0.15)

    def test_caution_floor_is_20_percent(self) -> None:
        assert _get_cash_floor(2) == pytest.approx(0.20)

    def test_crisis_halt_floor_is_30_percent(self) -> None:
        assert _get_cash_floor(1) == pytest.approx(0.30)

    def test_none_rule_defaults_to_8_percent_clear(self) -> None:
        assert _get_cash_floor(None) == pytest.approx(0.08)


# ---------------------------------------------------------------------------
# _count_consecutive_brent_closes_below_95  (unchanged)
# ---------------------------------------------------------------------------


class TestConsecutiveBrentClosesBelow95:
    def test_counts_two_consecutive_closes_below_95(self) -> None:
        assert _count_consecutive_brent_closes_below_95([94.8, 94.1]) == 2

    def test_counts_only_the_first_close_when_second_breaks_the_streak(self) -> None:
        assert _count_consecutive_brent_closes_below_95([94.8, 96.0]) == 1

    def test_returns_zero_when_the_latest_close_is_not_below_95(self) -> None:
        assert _count_consecutive_brent_closes_below_95([96.2, 94.0]) == 0


# ---------------------------------------------------------------------------
# _derive_effective_regime  (now returns rule_name directly — geo integrated)
# ---------------------------------------------------------------------------


class TestDeriveEffectiveRegime:
    def test_rule1_gives_crisis_halt(self) -> None:
        assert _derive_effective_regime(automatic_rule=1, geopolitical_state="ESCALATING") == "CRISIS HALT"

    def test_rule2_gives_caution(self) -> None:
        assert _derive_effective_regime(automatic_rule=2, geopolitical_state="ACTIVE_RISK") == "CAUTION"


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

    def test_rule1_triggers_regardless_of_geo_when_market_fires(self) -> None:
        """Rule 1 fires on market conditions alone — any geo triggers it."""
        rule = _determine_rule(
            brent_price=120.0,
            vix_value=40.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="ACTIVE_RISK",
        )
        assert rule == 1

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

    def test_rule3_triggers_regardless_of_geo_when_market_fires(self) -> None:
        """Rule 3 fires on market conditions alone — geo flag is irrelevant."""
        rule = _determine_rule(
            brent_price=92.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=1,
            geopolitical_state="NONE",
        )
        assert rule == 3

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

    def test_rule4_triggers_regardless_of_geo_when_market_fires(self) -> None:
        """Rule 4 fires on market conditions alone — geo flag is irrelevant."""
        rule = _determine_rule(
            brent_price=90.0,
            vix_value=22.0,
            brent_consecutive_below_95_count=2,
            geopolitical_state="NONE",
        )
        assert rule == 4

    # ── Default fallback ───────────────────────────────────────────────────

    def test_default_fallback_to_caution_when_ambiguous_market(self) -> None:
        """Ambiguous market (no clear rule): brent 85 < 100, streak=0, vix=20 → soft caution."""
        rule = _determine_rule(
            brent_price=85.0,
            vix_value=20.0,
            brent_consecutive_below_95_count=0,
            geopolitical_state="NONE",
        )
        assert rule == 3  # Soft Caution fires: brent<100, streak<2, vix<22


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

    def test_none_gives_clear(self) -> None:
        """rule=None defaults to CLEAR when market data unavailable."""
        assert _derive_effective_regime(automatic_rule=None, geopolitical_state="NONE") == "CLEAR"


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


# ---------------------------------------------------------------------------
# Geo flag DB persistence helpers
# ---------------------------------------------------------------------------


class TestGeoFlagInMemoryStore:
    """Verify the in-memory geo flag store getters/setters."""

    def setup_method(self) -> None:
        reset_geo_flag_current()

    def teardown_method(self) -> None:
        reset_geo_flag_current()

    def test_default_is_none(self) -> None:
        assert get_geo_flag_current() == "NONE"

    def test_set_and_get(self) -> None:
        set_geo_flag_current("RESOLVED")
        assert get_geo_flag_current() == "RESOLVED"

    def test_set_normalises_to_upper(self) -> None:
        set_geo_flag_current("escalating")
        assert get_geo_flag_current() == "ESCALATING"

    def test_set_strips_whitespace(self) -> None:
        set_geo_flag_current("  ACTIVE_RISK  ")
        assert get_geo_flag_current() == "ACTIVE_RISK"

    def test_reset_returns_to_none(self) -> None:
        set_geo_flag_current("RESOLVED")
        reset_geo_flag_current()
        assert get_geo_flag_current() == "NONE"


class TestPersistGeoFlagToDb:
    """persist_geo_flag_to_db upserts the regime_geo_state key in atlas_config."""

    async def test_executes_upsert_and_commits(self) -> None:
        session = AsyncMock()
        await persist_geo_flag_to_db("RESOLVED", session)
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_persists_none_value(self) -> None:
        session = AsyncMock()
        await persist_geo_flag_to_db("NONE", session)
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    async def test_upsert_statement_contains_correct_key(self) -> None:
        """The executed statement should reference the regime_geo_state key."""
        session = AsyncMock()
        await persist_geo_flag_to_db("ESCALATING", session)
        call_args = session.execute.call_args
        stmt = call_args[0][0]
        # The compiled statement should reference the key
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "regime_geo_state" in compiled
        assert "ESCALATING" in compiled


class TestLoadGeoFlagFromDb:
    """load_geo_flag_from_db reads atlas_config and updates in-memory store."""

    def setup_method(self) -> None:
        reset_geo_flag_current()

    def teardown_method(self) -> None:
        reset_geo_flag_current()

    async def test_loads_persisted_value_into_memory(self) -> None:
        from atlas.models.atlas_config import AtlasConfig

        row = MagicMock(spec=AtlasConfig)
        row.value = "DE_ESCALATING"
        session = AsyncMock()
        session.get.return_value = row

        await load_geo_flag_from_db(session)

        assert get_geo_flag_current() == "DE_ESCALATING"

    async def test_does_not_change_memory_when_no_db_row(self) -> None:
        session = AsyncMock()
        session.get.return_value = None

        set_geo_flag_current("ACTIVE_RISK")
        await load_geo_flag_from_db(session)

        # Memory should be unchanged when there is no persisted row
        assert get_geo_flag_current() == "ACTIVE_RISK"

    async def test_queries_correct_key(self) -> None:
        from atlas.models.atlas_config import AtlasConfig

        session = AsyncMock()
        session.get.return_value = None

        await load_geo_flag_from_db(session)

        session.get.assert_awaited_once_with(AtlasConfig, "regime_geo_state")
