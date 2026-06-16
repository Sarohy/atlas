"""Unit tests for the Overshoot Elasticity sub-module (SPEC v2.1)."""

from __future__ import annotations

from atlas.core.extension_washout import OverlayState
from atlas.core.overshoot_elasticity import DEFAULT_ELASTICITY_CONFIG as CFG
from atlas.core.overshoot_elasticity import (
    Confidence,
    ElasticityInputs,
    ElasticityTier,
    classify_tier,
    compute_elasticity,
    elasticity_score,
    name_elasticity,
)

# ---------------------------------------------------------------------------
# Scoring + tiers
# ---------------------------------------------------------------------------


class TestScore:
    def test_none_without_rv60(self) -> None:
        assert elasticity_score(ElasticityInputs(rv20=50), CFG) is None

    def test_high_inputs_score_high(self) -> None:
        s = elasticity_score(
            ElasticityInputs(rv20=140, rv60=100, beta=2.1, mom21=55, burner=True), CFG
        )
        assert s is not None and s >= 90

    def test_calm_inputs_score_low(self) -> None:
        s = elasticity_score(ElasticityInputs(rv20=20, rv60=25, beta=0.7, mom21=2), CFG)
        assert s is not None and s < 30

    def test_classify_tier_bands(self) -> None:
        assert classify_tier(90, CFG) == ElasticityTier.EXTREME
        assert classify_tier(70, CFG) == ElasticityTier.HIGH
        assert classify_tier(50, CFG) == ElasticityTier.MODERATE
        assert classify_tier(20, CFG) == ElasticityTier.LOW


# ---------------------------------------------------------------------------
# Per-name overrides (A4)
# ---------------------------------------------------------------------------


class TestOverrides:
    def test_nbis_hard_override_sharp_faller(self) -> None:
        r = compute_elasticity("NBIS", ElasticityInputs(rv60=90), event_count=3)
        assert r.tier == ElasticityTier.SHARP_FALLER
        assert r.hard_override is True
        assert r.plus40_state == OverlayState.HEDGE

    def test_anet_never_cross(self) -> None:
        r = compute_elasticity("ANET", ElasticityInputs(rv60=90))
        assert r.tier == ElasticityTier.NEVER_CROSS
        assert r.plus40_state == OverlayState.ACTIVE_PROTECTION

    def test_wfe_name_never_cross(self) -> None:
        amat = compute_elasticity("AMAT", ElasticityInputs(rv60=90))
        assert amat.tier == ElasticityTier.NEVER_CROSS
        assert name_elasticity("LRCX") is not None

    def test_mxl_anomaly_excluded_from_recalibration(self) -> None:
        r = compute_elasticity("MXL", ElasticityInputs(rv60=200))
        assert r.tier == ElasticityTier.ANOMALY
        assert r.exclude_recalibration is True

    def test_dell_moderate_provisional_watch_promote(self) -> None:
        r = compute_elasticity("DELL", ElasticityInputs(rv60=55), event_count=3)
        assert r.tier == ElasticityTier.MODERATE
        assert r.provisional is True
        assert r.watch_promote is True


# ---------------------------------------------------------------------------
# +40 behaviour + ladder spacing + confidence + data gaps
# ---------------------------------------------------------------------------


class TestResult:
    def test_extreme_protect_only_and_wide_ladder(self) -> None:
        r = compute_elasticity(
            "ZZZ", ElasticityInputs(rv20=130, rv60=120, beta=2.2, mom21=60), event_count=3
        )
        assert r.tier == ElasticityTier.EXTREME
        assert r.plus40_label == "protect only"
        assert r.ladder == (40.0, 65.0, 85.0)  # trims pushed out
        assert r.confidence == Confidence.HIGH

    def test_low_tier_trim_watch_and_compressed_ladder(self) -> None:
        r = compute_elasticity("ZZZ", ElasticityInputs(rv20=20, rv60=22, beta=0.7, mom21=1))
        assert r.tier == ElasticityTier.LOW
        assert r.plus40_state == OverlayState.TRIM_WATCH
        assert r.ladder == (40.0, 50.0, 70.0)

    def test_confidence_from_events(self) -> None:
        hi = compute_elasticity("ZZZ", ElasticityInputs(rv60=90), event_count=3)
        mod = compute_elasticity("ZZZ", ElasticityInputs(rv60=90), event_count=2)
        lo = compute_elasticity("ZZZ", ElasticityInputs(rv60=90), event_count=1)
        assert hi.confidence == Confidence.HIGH
        assert mod.confidence == Confidence.MODERATE
        assert lo.confidence == Confidence.LOW

    def test_data_gap_falls_back_to_peak(self) -> None:
        r = compute_elasticity("ZZZ", ElasticityInputs(), peak_50d=110, event_count=1)
        assert r.score is None
        assert "ELASTICITY_INPUTS" in r.data_gaps
        assert r.tier == ElasticityTier.EXTREME  # from historical peak fallback

    def test_extra_data_gaps_surface(self) -> None:
        r = compute_elasticity(
            "ZZZ", ElasticityInputs(rv60=90), extra_data_gaps=["SHORT_INTEREST", "FLOAT"]
        )
        assert "SHORT_INTEREST" in r.data_gaps and "FLOAT" in r.data_gaps
