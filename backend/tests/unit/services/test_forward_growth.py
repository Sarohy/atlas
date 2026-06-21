"""Unit tests for the Forward Growth Score (FGS) engine + service."""

from __future__ import annotations

from atlas.core import forward_growth as fg
from atlas.core.forward_growth import GrowthBucket
from atlas.services.edgar_fundamentals import CustomerConcentration, _parse_customer_concentration
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

    def test_add_blocked_when_real_growth_but_flow_extension_block(self) -> None:
        # MRVL-shaped: high FGS grade (72) + mediocre F5 (57) + weak F4 → real
        # forward growth, adds blocked. Must be ADD_BLOCKED, never AVOID.
        bucket, action = fg.classify_bucket(57, 72, 40)
        assert bucket == GrowthBucket.ADD_BLOCKED
        assert action is not None and "no fresh add" in action.lower()
        assert "avoid" not in action.lower()

    def test_meaningful_growth_never_avoids_even_with_low_f5(self) -> None:
        # FGS at the HIGH-grade floor (70) rescues the name from AVOID.
        assert fg.classify_bucket(45, 70, None)[0] == GrowthBucket.ADD_BLOCKED

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
            "crdo", income, "",  # empty transcript → G2/G3/G4 stay DATA_GAP
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
        )
        assert resp.ticker == "CRDO"
        assert resp.revenue_acceleration.source == "alpha_vantage"
        assert resp.revenue_acceleration.score >= 90
        assert resp.tam_bottleneck.wave.startswith("Optics")
        # G2/G3/G4 default to neutral DATA_GAP with no transcript.
        assert "BACKLOG_BOOKINGS" in resp.data_gaps
        assert resp.backlog_bookings.score == fg.NEUTRAL_SCORE
        # Low F5 + strong FGS + confirming F4 → growth tactical.
        assert resp.bucket == GrowthBucket.GROWTH_TACTICAL

    def test_operator_overrides_applied(self) -> None:
        income = _income([400, 300, 220, 160, 130, 110])
        resp = ForwardGrowthService._build_response(
            "crdo", income, "",
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=90, customer_quality_override=88, product_ramp_override=92,
        )
        assert resp.backlog_bookings.score == 90
        assert resp.backlog_bookings.source == "override"
        assert "BACKLOG_BOOKINGS" not in resp.data_gaps
        # All sub-factors high now → FGS should be elite-ish.
        assert resp.fgs_score >= 85

    def test_transcript_signals_fill_the_gaps(self) -> None:
        # AAOI-like transcript snippet — has backlog, hyperscaler, and ramp language.
        transcript = (
            "MOCVD is on complete backlog. We saw strong engagement around our 800G "
            "and 1.6T products from a third hyperscale 10% customer, with a "
            "significantly larger volume ramp expected starting in Q3."
        )
        income = _income([400, 300, 220, 160, 130, 110])
        resp = ForwardGrowthService._build_response(
            "crdo", income, transcript,
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
        )
        assert resp.backlog_bookings.source == "transcript"
        assert resp.customer_quality.source == "transcript"
        assert resp.product_ramp.source == "transcript"
        assert "BACKLOG_BOOKINGS" not in resp.data_gaps
        assert "CUSTOMER_QUALITY" not in resp.data_gaps
        assert "PRODUCT_RAMP" not in resp.data_gaps
        # All 5 axes now instrumented → confidence 100%.
        assert resp.confidence_pct == 100

    def test_override_beats_transcript(self) -> None:
        transcript = "We have a record backlog and strong hyperscaler ramp."
        income = _income([400, 300, 220, 160, 130, 110])
        resp = ForwardGrowthService._build_response(
            "crdo", income, transcript,
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=40, customer_quality_override=None, product_ramp_override=None,
        )
        assert resp.backlog_bookings.score == 40
        assert resp.backlog_bookings.source == "override"
        # The others fall through to the transcript signal.
        assert resp.customer_quality.source == "transcript"

    def test_no_revenue_data_gap(self) -> None:
        resp = ForwardGrowthService._build_response(
            "crdo", {}, "",
            f5_score=None, f4_score=None, atlas_score=None,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
        )
        assert "REVENUE_ACCELERATION" in resp.data_gaps
        assert resp.revenue_acceleration.score == fg.NEUTRAL_SCORE
        # No F5 → no bucket.
        assert resp.bucket is None

    def test_unknown_ticker_tam_gap(self) -> None:
        resp = ForwardGrowthService._build_response(
            "zzzz", _income([130, 120, 110, 100, 100, 100]), "",
            f5_score=80, f4_score=70, atlas_score=80,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
        )
        assert "TAM_BOTTLENECK" in resp.data_gaps
        assert resp.tam_bottleneck.wave == "UNCLASSIFIED"


# ---------------------------------------------------------------------------
# Transcript signal extractors
# ---------------------------------------------------------------------------


class TestTranscriptSignals:
    def test_backlog_strong_on_sold_out_or_dollar(self) -> None:
        assert fg.score_backlog_signal("Our product is sold out for the year.") == 90
        assert fg.score_backlog_signal("We have a backlog of $324 million in orders.") == 90

    def test_backlog_moderate_on_plain_mention(self) -> None:
        assert fg.score_backlog_signal("Bookings were steady this quarter.") == 65

    def test_backlog_none_when_absent(self) -> None:
        assert fg.score_backlog_signal("Margins improved on cost control.") is None
        assert fg.score_backlog_signal("") is None

    def test_customer_quality_named_and_hyperscaler(self) -> None:
        named_and_hyper = "Shipments to NVIDIA and a hyperscaler ramped."
        assert fg.score_customer_quality_signal(named_and_hyper) == 90
        assert fg.score_customer_quality_signal("A hyperscaler became a 10% customer.") == 78
        assert fg.score_customer_quality_signal("Our largest customer grew.") == 62
        assert fg.score_customer_quality_signal("Revenue was up.") is None

    def test_product_ramp(self) -> None:
        assert fg.score_product_ramp_signal("Volume ramp of 1.6T begins in Q3.") == 90
        assert fg.score_product_ramp_signal("We expect to ramp through the year.") == 78
        assert fg.score_product_ramp_signal("Our 800G product is qualifying.") == 65
        assert fg.score_product_ramp_signal("No change to guidance.") is None


# ---------------------------------------------------------------------------
# EDGAR-derived: backlog (RPO) scoring + customer concentration
# ---------------------------------------------------------------------------


class TestBacklogFromRpo:
    def test_coverage_tiers(self) -> None:
        assert fg.score_backlog_from_rpo(1_200, 1_000) == 95  # >1x revenue
        assert fg.score_backlog_from_rpo(700, 1_000) == 85    # 0.5-1x
        assert fg.score_backlog_from_rpo(300, 1_000) == 75    # 0.25-0.5x
        assert fg.score_backlog_from_rpo(100, 1_000) == 60    # <0.25x

    def test_none_when_missing(self) -> None:
        assert fg.score_backlog_from_rpo(None, 1_000) is None
        assert fg.score_backlog_from_rpo(500, None) is None
        assert fg.score_backlog_from_rpo(500, 0) is None


class TestConcentrationCap:
    def test_caps(self) -> None:
        assert fg.concentration_quality_cap(55.0) == 60
        assert fg.concentration_quality_cap(42.0) == 72
        assert fg.concentration_quality_cap(30.0) is None
        assert fg.concentration_quality_cap(None) is None


class TestCustomerConcentrationParser:
    def test_exact_pct(self) -> None:
        text = "Customer A accounted for 18.5% of our net revenue in fiscal 2025."
        cc = _parse_customer_concentration(text)
        assert cc is not None and cc.largest_customer_pct == 18.5

    def test_takes_largest_when_multiple(self) -> None:
        text = (
            "One customer represented 22% of revenue; another customer was 11% of net sales."
        )
        cc = _parse_customer_concentration(text)
        assert cc is not None and cc.largest_customer_pct == 22.0

    def test_count_only_aaoi_style(self) -> None:
        text = "We had two customers that accounted for more than 10% of our revenue in 2025."
        cc = _parse_customer_concentration(text)
        assert cc is not None
        assert cc.customers_over_10pct == 2
        assert cc.largest_customer_pct is None  # only a count is disclosed

    def test_none_when_absent(self) -> None:
        assert _parse_customer_concentration("Margins expanded on operating leverage.") is None


# ---------------------------------------------------------------------------
# FGS service: EDGAR figures flow through
# ---------------------------------------------------------------------------


class TestServiceEdgarIntegration:
    def test_edgar_backlog_drives_g2_over_transcript(self) -> None:
        income = _income([400, 300, 220, 160, 130, 110])  # TTM ≈ 1080
        resp = ForwardGrowthService._build_response(
            "crdo", income, "we mentioned backlog once",  # transcript would score 65
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
            backlog_usd=1_500.0,  # > 1x TTM revenue → coverage 95, EDGAR wins
        )
        assert resp.backlog_bookings.source == "edgar"
        assert resp.backlog_bookings.score == 95
        assert resp.backlog_usd == 1500.0

    def test_concentration_caps_customer_quality(self) -> None:
        income = _income([400, 300, 220, 160, 130, 110])
        # Transcript names a hyperscaler (would score 90), but one customer is 55%.
        resp = ForwardGrowthService._build_response(
            "crdo", income, "ramping with a hyperscaler and NVIDIA",
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
            concentration=CustomerConcentration(
                largest_customer_pct=55.0, customers_over_10pct=1, summary="one customer 55%"
            ),
        )
        assert resp.customer_concentration_pct == 55.0
        assert resp.customer_quality.score == 60  # capped down from 90 by 55% concentration
        assert resp.customer_quality.source == "transcript"

    def test_concentration_count_surfaced_without_cap(self) -> None:
        income = _income([400, 300, 220, 160, 130, 110])
        resp = ForwardGrowthService._build_response(
            "crdo", income, "shipping to a hyperscaler",
            f5_score=60, f4_score=70, atlas_score=84,
            backlog_override=None, customer_quality_override=None, product_ramp_override=None,
            concentration=CustomerConcentration(
                largest_customer_pct=None, customers_over_10pct=2, summary="two customers >10%"
            ),
        )
        assert resp.customers_over_10pct == 2
        assert resp.customer_concentration_pct is None
        # No exact % → no cap → transcript hyperscaler quality stands.
        assert resp.customer_quality.score == 78
