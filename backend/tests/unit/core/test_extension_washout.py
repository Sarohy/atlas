"""Unit tests for the Extension & Washout Overlay engine (Spec v2)."""

from __future__ import annotations

from atlas.core.extension_washout import (
    DEFAULT_CONFIG,
    BreadthLevel,
    ConfirmationLegs,
    OverlayState,
    Overshoot,
    Track,
    WashoutInputs,
    breadth_level,
    ladder_rung,
    metric_legs,
    name_meta,
    resolve_overlay,
    trim_authorized,
)

# ---------------------------------------------------------------------------
# Per-name metadata (§2)
# ---------------------------------------------------------------------------


class TestNameMeta:
    def test_extension_track(self) -> None:
        assert name_meta("SNDK").track == Track.EXTENSION
        assert name_meta("sndk").overshoot == Overshoot.MASSIVE

    def test_breadth_flow_track(self) -> None:
        assert name_meta("MU").track == Track.BREADTH_FLOW

    def test_vicr_override_track_wins(self) -> None:
        # ext-predictive tier but breadth-managed — track wins (§2).
        meta = name_meta("VICR")
        assert meta.track == Track.BREADTH_FLOW
        assert meta.tier == "ext-predictive"

    def test_nbis_is_sharp_faller(self) -> None:
        assert name_meta("NBIS").overshoot == Overshoot.SHARP_FALLER

    def test_mxl_excluded(self) -> None:
        assert name_meta("MXL").overshoot == Overshoot.EXCLUDED

    def test_unknown_defaults_low_confidence(self) -> None:
        meta = name_meta("ZZZZ")
        assert meta.low_confidence is True
        assert meta.track == Track.EXTENSION


# ---------------------------------------------------------------------------
# Extension ladder (§3 / §3.2)
# ---------------------------------------------------------------------------


class TestLadder:
    def test_rungs(self) -> None:
        assert ladder_rung(10, Overshoot.MASSIVE) == "No action"
        assert ladder_rung(30, Overshoot.MASSIVE) == "Stop-Add / No-Chase"
        assert ladder_rung(45, Overshoot.MASSIVE) == "Arm Protection"
        assert ladder_rung(65, Overshoot.MASSIVE) == "Active Protection"
        assert ladder_rung(85, Overshoot.MASSIVE) == "Forced De-Risk Review"

    def test_sharp_faller_trim_line_at_40(self) -> None:
        assert ladder_rung(45, Overshoot.SHARP_FALLER) == "Trim/Hedge (sharp-faller line)"


# ---------------------------------------------------------------------------
# Metric legs (§10) — gating
# ---------------------------------------------------------------------------


class TestMetricLegs:
    def test_rsi_alone_without_extension_is_not_a_moderate_leg(self) -> None:
        legs = metric_legs(rsi14=85, move21=None, move14=None, move20=None, dist_50d=10)
        assert legs.moderate == []  # gated: 50d < 25 -> RSI doesn't count

    def test_gated_legs_count_when_extended(self) -> None:
        legs = metric_legs(rsi14=85, move21=40, move14=None, move20=None, dist_50d=30)
        assert "50d>=25%" in legs.moderate
        assert "RSI>=75" in legs.moderate
        assert "21d>=25%" in legs.moderate

    def test_extreme_legs(self) -> None:
        legs = metric_legs(rsi14=82, move21=36, move14=None, move20=22, dist_50d=45)
        assert "RSI>=80" in legs.extreme
        assert "21d>=35%" in legs.extreme
        assert "20d>=20%" in legs.extreme
        assert "50d>=40%" in legs.extreme


# ---------------------------------------------------------------------------
# Confirmation legs + trim authorization (§7)
# ---------------------------------------------------------------------------


class TestTrimAuthorization:
    def test_two_legs_authorize(self) -> None:
        legs = ConfirmationLegs(flow_distribution=True, vwap_lost=True)
        assert trim_authorized(legs=legs, negative_catalyst=False, hard_override=False) is True

    def test_one_leg_does_not_authorize(self) -> None:
        legs = ConfirmationLegs(flow_distribution=True)
        assert trim_authorized(legs=legs, negative_catalyst=False, hard_override=False) is False

    def test_negative_catalyst_authorizes(self) -> None:
        assert trim_authorized(
            legs=ConfirmationLegs(), negative_catalyst=True, hard_override=False
        ) is True

    def test_hard_override_authorizes(self) -> None:
        assert trim_authorized(
            legs=ConfirmationLegs(), negative_catalyst=False, hard_override=True
        ) is True

    def test_no_trigger_does_not_authorize(self) -> None:
        assert trim_authorized(
            legs=ConfirmationLegs(), negative_catalyst=False, hard_override=False
        ) is False


# ---------------------------------------------------------------------------
# Breadth monitor (§5)
# ---------------------------------------------------------------------------


class TestBreadth:
    def test_hedge_trigger(self) -> None:
        assert breadth_level(count_down_watch=0, count_down_hedge=12) == BreadthLevel.HEDGE

    def test_watch(self) -> None:
        assert breadth_level(count_down_watch=9, count_down_hedge=0) == BreadthLevel.WATCH

    def test_none(self) -> None:
        assert breadth_level(count_down_watch=5, count_down_hedge=0) is None

    def test_hedge_takes_priority(self) -> None:
        assert breadth_level(count_down_watch=20, count_down_hedge=12) == BreadthLevel.HEDGE


# ---------------------------------------------------------------------------
# Master resolver (§9) — states, precedence, §3.1 size rule
# ---------------------------------------------------------------------------


def _inp(ticker: str = "LITE", **kw: object) -> WashoutInputs:
    return WashoutInputs(ticker=ticker, **kw)  # type: ignore[arg-type]


class TestResolver:
    def test_data_gap_is_wait(self) -> None:
        assert resolve_overlay(_inp(dist_50d=None)).state == OverlayState.WAIT
        assert resolve_overlay(_inp(dist_50d=50, data_ok=False)).state == OverlayState.WAIT

    def test_no_condition_is_wait(self) -> None:
        assert resolve_overlay(_inp(dist_50d=10)).state == OverlayState.WAIT

    def test_stop_add(self) -> None:
        assert resolve_overlay(_inp(dist_50d=30)).state == OverlayState.STOP_ADD

    def test_arm_protection(self) -> None:
        assert resolve_overlay(_inp(dist_50d=45)).state == OverlayState.ARM_PROTECTION

    def test_active_protection_at_target_no_legs(self) -> None:
        r = resolve_overlay(_inp(dist_50d=65, at_or_above_target=True))
        assert r.state == OverlayState.ACTIVE_PROTECTION  # no trigger -> not TRIM

    def test_trim_when_at_target_and_two_legs(self) -> None:
        legs = ConfirmationLegs(flow_distribution=True, vwap_lost=True)
        r = resolve_overlay(_inp(dist_50d=65, at_or_above_target=True, confirmation=legs))
        assert r.state == OverlayState.TRIM
        assert r.trim_authorized is True

    def test_below_target_relabels_trim_to_stop_add(self) -> None:
        legs = ConfirmationLegs(flow_distribution=True, vwap_lost=True)
        r = resolve_overlay(_inp(dist_50d=65, below_target=True, confirmation=legs))
        assert r.state == OverlayState.STOP_ADD
        assert r.size_relabeled is True
        assert r.trim_authorized is False  # never trim a below-target position

    def test_forced_de_risk(self) -> None:
        assert resolve_overlay(_inp(dist_50d=85)).state == OverlayState.FORCED_DE_RISK_REVIEW

    def test_forced_de_risk_relabeled_when_below_target(self) -> None:
        r = resolve_overlay(_inp(dist_50d=85, below_target=True))
        assert r.state == OverlayState.STOP_ADD
        assert r.size_relabeled is True

    def test_book_level_hedge_overrides_everything(self) -> None:
        r = resolve_overlay(_inp(dist_50d=85, breadth=BreadthLevel.HEDGE))
        assert r.state == OverlayState.BOOK_LEVEL_HEDGE

    def test_absorption_triggers_single_name_hedge(self) -> None:
        r = resolve_overlay(_inp(dist_50d=45, absorption=True))
        assert r.state == OverlayState.HEDGE

    def test_sharp_faller_hedges_at_40(self) -> None:
        r = resolve_overlay(_inp(ticker="NBIS", dist_50d=45))
        assert r.state == OverlayState.HEDGE

    def test_negative_catalyst_trims_even_without_extension(self) -> None:
        r = resolve_overlay(_inp(dist_50d=10, at_or_above_target=True, negative_catalyst=True))
        assert r.state == OverlayState.TRIM

    def test_one_leg_is_trim_watch(self) -> None:
        legs = ConfirmationLegs(flow_distribution=True)
        r = resolve_overlay(_inp(dist_50d=10, confirmation=legs))
        assert r.state == OverlayState.TRIM_WATCH

    def test_breadth_flow_name_extension_only_arms(self) -> None:
        r = resolve_overlay(_inp(ticker="MU", dist_50d=45))
        assert r.state == OverlayState.ARM_PROTECTION
        assert r.track == Track.BREADTH_FLOW
        assert "extension only arms" in r.reason


# ---------------------------------------------------------------------------
# Overshoot Elasticity integration (SPEC v2.1) — ladder spacing via cfg
# ---------------------------------------------------------------------------


class TestElasticitySpacing:
    def test_extreme_spacing_keeps_plus60_in_arm(self) -> None:
        from dataclasses import replace

        from atlas.core import overshoot_elasticity as oe

        el = oe.compute_elasticity(
            "ZZZ", oe.ElasticityInputs(rv20=130, rv60=120, beta=2.2, mom21=60), event_count=3
        )
        arm, active, forced = el.ladder
        cfg = replace(
            DEFAULT_CONFIG,
            arm_protection_50d=arm,
            active_protection_50d=active,
            forced_derisk_50d=forced,
        )
        # At +60, an Extreme name (active line pushed to 65) is still ARM, not ACTIVE.
        r = resolve_overlay(_inp(dist_50d=60), cfg)
        assert r.state == OverlayState.ARM_PROTECTION

    def test_low_spacing_escalates_sooner(self) -> None:
        from dataclasses import replace

        from atlas.core import overshoot_elasticity as oe

        el = oe.compute_elasticity("ZZZ", oe.ElasticityInputs(rv20=20, rv60=22, beta=0.7, mom21=1))
        arm, active, forced = el.ladder
        cfg = replace(
            DEFAULT_CONFIG,
            arm_protection_50d=arm,
            active_protection_50d=active,
            forced_derisk_50d=forced,
        )
        # Low name (active line compressed to 50) is ACTIVE at +55, where Extreme is still ARM.
        r = resolve_overlay(_inp(dist_50d=55, at_or_above_target=True), cfg)
        assert r.state == OverlayState.ACTIVE_PROTECTION
