"""Unit tests for the Forward Growth Score (FGS) engine + service."""

from __future__ import annotations

from atlas.core import forward_growth as fg
from atlas.core.forward_growth import GrowthBucket
from atlas.services.forward_growth_service import ForwardGrowthService

# ---------------------------------------------------------------------------
# G1 — revenue acceleration
# ---------------------------------------------------------------------------


class TestRevenueAcceleration:
    def test_strong_accelerating_growth_scores_high(self) -> None:
        # newest-first; YoY = (200-90)/90 = 122%, and accelerating vs prior YoY.
        score, yoy, accel = fg.score_revenue_acceleration([200, 150, 120, 100, 90, 80])
        assert score == 100
        assert yoy is not None and yoy > 100
        assert accel is True

    def test_flat_revenue_scores_low(self) -> None:
        score, _yoy, accel = fg.score_revenue_acceleration([105, 104, 103, 102, 101, 100])
        assert score is not None and score < 40
        assert accel is False

    def test_insufficient_history_returns_none(self) -> None:
        assert fg.score_revenue_acceleration([100, 90]) == (None, None, None)

    def test_decline_scores_bottom(self) -> None:
        score, yoy, _ = fg.score_revenue_acceleration([80, 85, 90, 95, 100, 105])
        assert yoy is not None and yoy < 0
        assert score is not None and score <= 20

    def test_guidance_raised_nudges_up(self) -> None:
        base, _, _ = fg.score_revenue_acceleration([130, 120, 110, 100, 100, 100])
        raised, _, _ = fg.score_revenue_acceleration(
            [130, 120, 110, 100, 100, 100], guidance_raised=True
        )
        assert raised is not None and base is not None and raised == min(100, base + 5)


# ---------------------------------------------------------------------------
# G5 — TAM / bottleneck lookup
# ---------------------------------------------------------------------------


class TestTamBottleneck:
    def test_known_ticker_returns_wave(self) -> None:
        score, wave, status = fg.lookup_tam_bottleneck("CRDO")
        assert score == 95
        assert "Optics" in wave
        assert status == "ACTIVE"

    def test_case_insensitive(self) -> None:
        assert fg.lookup_tam_bottleneck("amat")[0] == fg.lookup_tam_bottleneck("AMAT")[0]

    def test_unknown_ticker_is_neutral_gap(self) -> None:
        assert fg.lookup_tam_bottleneck("ZZZZ") == (fg.NEUTRAL_SCORE, "UNCLASSIFIED", "UNKNOWN")


# ---------------------------------------------------------------------------
# Composite & grade
# ---------------------------------------------------------------------------


class TestComposite:
    def test_mean_over_instrumented(self) -> None:
        assert fg.compute_fgs([100, 100, 100, 100, 100]) == 100
        assert fg.compute_fgs([0, 0]) == 0
        # CRDO Phase 1: only G1 + G5 instrumented (gaps excluded, not averaged in).
        assert fg.compute_fgs([100, 95]) == 98

    def test_empty_returns_neutral(self) -> None:
        assert fg.compute_fgs([]) == fg.NEUTRAL_SCORE

    def test_confidence(self) -> None:
        assert fg.confidence_pct(2) == 40  # G1 + G5 of 5
        assert fg.confidence_pct(5) == 100
        assert fg.confidence_pct(0) == 0

    def test_grades(self) -> None:
        assert fg.fgs_grade(90) == "ELITE"
        assert fg.fgs_grade(70) == "HIGH"
        assert fg.fgs_grade(50) == "MODERATE"
        assert fg.fgs_grade(49) == "LOW"


# ---------------------------------------------------------------------------
# Action matrix
# ---------------------------------------------------------------------------


class TestActionMatrix:
    def test_core_compounder(self) -> None:
        assert fg.classify_bucket(80, 80, 70)[0] == GrowthBucket.CORE_COMPOUNDER

    def test_core_compounder_waits_for_flow_when_f4_weak(self) -> None:
        bucket, action = fg.classify_bucket(80, 80, 40)
        assert bucket == GrowthBucket.CORE_COMPOUNDER
        assert action is not None and "flow" in action.lower()

    def test_quality_hold(self) -> None:
        assert fg.classify_bucket(80, 50, 70)[0] == GrowthBucket.QUALITY_HOLD

    def test_growth_tactical_when_low_f5_high_fgs_confirming(self) -> None:
        assert fg.classify_bucket(55, 80, 70)[0] == GrowthBucket.GROWTH_TACTICAL

    def test_story_risk_when_flow_not_confirming(self) -> None:
        assert fg.classify_bucket(55, 80, 40)[0] == GrowthBucket.STORY_RISK

    def test_avoid_when_both_low(self) -> None:
        assert fg.classify_bucket(40, 40, 30)[0] == GrowthBucket.AVOID

    def test_none_f5_yields_no_bucket(self) -> None:
        assert fg.classify_bucket(None, 80, 70) == (None, None)

    def test_none_f4_treated_as_not_confirming(self) -> None:
        # low F5 + high FGS + no flow → STORY_RISK (not GROWTH_TACTICAL)
        assert fg.classify_bucket(55, 80, None)[0] == GrowthBucket.STORY_RISK


# ---------------------------------------------------------------------------
# Service response assembly (no network — synthetic AV income data)
# ---------------------------------------------------------------------------


def _income(revenues_newest_first: list[float]) -> dict:
    return {"quarterlyReports": [{"totalRevenue": str(r)} for r in revenues_newest_first]}


class TestServiceResponse:
    def test_high_flyer_growth_tactical(self) -> None:
        # CRDO-like: explosive accelerating revenue, Optics wave, but F5 weak.
        income = _income([400, 300, 220, 160, 130, 110])
        resp = ForwardGrowthService._build_response(
            "crdo", income,
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
        )
        assert resp.ticker == "CRDO"
        assert resp.revenue_acceleration.source == "alpha_vantage"
        assert resp.revenue_acceleration.score >= 90
        assert resp.tam_bottleneck.wave.startswith("Optics")
        # G2/G3/G4 default to neutral DATA_GAP.
        assert "BACKLOG_BOOKINGS" in resp.data_gaps
        assert resp.backlog_bookings.score == fg.NEUTRAL_SCORE
        # Low F5 + strong FGS + confirming F4 → growth tactical.
        assert resp.bucket == GrowthBucket.GROWTH_TACTICAL

    def test_operator_overrides_applied(self) -> None:
        income = _income([400, 300, 220, 160, 130, 110])
        resp = ForwardGrowthService._build_response(
            "crdo", income,
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=90, customer_quality_override=88, product_ramp_override=92,
        )
        assert resp.backlog_bookings.score == 90
        assert resp.backlog_bookings.source == "override"
        assert "BACKLOG_BOOKINGS" not in resp.data_gaps
        # All sub-factors high now → FGS should be elite-ish.
        assert resp.fgs_score >= 85

    def test_no_revenue_data_gap(self) -> None:
        resp = ForwardGrowthService._build_response(
            "crdo", {},
            f5_score=None, f4_score=None, atlas_score=None,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
        )
        assert "REVENUE_ACCELERATION" in resp.data_gaps
        assert resp.revenue_acceleration.score == fg.NEUTRAL_SCORE
        # No F5 → no bucket.
        assert resp.bucket is None

    def test_unknown_ticker_tam_gap(self) -> None:
        resp = ForwardGrowthService._build_response(
            "zzzz", _income([130, 120, 110, 100, 100, 100]),
            f5_score=80, f4_score=70, atlas_score=80,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
        )
        assert "TAM_BOTTLENECK" in resp.data_gaps
        assert resp.tam_bottleneck.wave == "UNCLASSIFIED"
