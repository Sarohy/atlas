"""Unit tests for Framework 14 - Position Sizing Rules service.

Tests exercise pure functions only (no I/O). Async DB-query functions are
tested indirectly through integration tests.

ATLAS v7.3.4 spec (CLAUDE.md, Framework #13 / Section 2.1):
  Soft cap:     8% NAV  — no new adds
  Hard review: 10% NAV  — consider trimming 20%
  Score display cap: 85 (display only, not a scoring change)

Grandfathered positions (April 2026):
  MU   13.6% → expires at 17.0%
  TSM  11.7% → expires at 14.6%
  COHR  9.5% → expires at 11.9%

Cluster thresholds:
  AI Optics:        yellow 27%, red 30%
  AI Memory:        yellow 22%, red 25%
  Foundry:          yellow 17%, red 20%
  AI Power/Thermal: yellow 12%, red 15%
  AI Custom Silicon: yellow 12%, red 15%
  AI Infrastructure: yellow 12%, red 15%
"""

from __future__ import annotations

import pytest

from atlas.services.framework14_service import (
    CLUSTER_THRESHOLDS,
    GRANDFATHERED_POSITIONS,
    TICKER_CLUSTER_MAP,
    ConcentrationStatus,
    ClusterStatus,
    SizingTier,
    evaluate_cluster,
    evaluate_concentration,
    get_sizing_tier,
    get_target_weight,
)


# ---------------------------------------------------------------------------
# Sizing tier mapping
# ---------------------------------------------------------------------------


class TestGetSizingTier:
    def test_tsm_is_foundry_not_china_risk(self) -> None:
        # TSM listed in Foundry cluster — not CHINA_RISK
        tier = get_sizing_tier("TSM")
        assert tier != SizingTier.CHINA_RISK

    def test_mu_is_high_conviction_t2_or_core(self) -> None:
        tier = get_sizing_tier("MU")
        assert tier in {SizingTier.CORE_ANCHOR, SizingTier.HIGH_CONVICTION_T2}

    def test_aaoi_is_high_beta(self) -> None:
        tier = get_sizing_tier("AAOI")
        assert tier == SizingTier.HIGH_BETA

    def test_ticker_case_insensitive(self) -> None:
        assert get_sizing_tier("mu") == get_sizing_tier("MU")

    def test_unknown_ticker_returns_standard_t2(self) -> None:
        tier = get_sizing_tier("UNKNOWN_XYZ")
        assert tier == SizingTier.STANDARD_T2


# ---------------------------------------------------------------------------
# Target weight ranges
# ---------------------------------------------------------------------------


class TestGetTargetWeight:
    def test_core_anchor_range(self) -> None:
        low, high = get_target_weight(SizingTier.CORE_ANCHOR)
        assert low == pytest.approx(0.03)
        assert high == pytest.approx(0.05)

    def test_high_conviction_t2_range(self) -> None:
        low, high = get_target_weight(SizingTier.HIGH_CONVICTION_T2)
        assert low == pytest.approx(0.015)
        assert high == pytest.approx(0.025)

    def test_standard_t2_range(self) -> None:
        low, high = get_target_weight(SizingTier.STANDARD_T2)
        assert low == pytest.approx(0.005)
        assert high == pytest.approx(0.010)

    def test_t3_satellite_range(self) -> None:
        low, high = get_target_weight(SizingTier.T3_SATELLITE)
        assert low == pytest.approx(0.0025)
        assert high == pytest.approx(0.005)

    def test_china_risk_range(self) -> None:
        low, high = get_target_weight(SizingTier.CHINA_RISK)
        assert low == pytest.approx(0.0)
        assert high == pytest.approx(0.0025)

    def test_high_beta_range(self) -> None:
        low, high = get_target_weight(SizingTier.HIGH_BETA)
        assert low == pytest.approx(0.005)
        assert high == pytest.approx(0.010)


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_grandfathered_mu_expires_at_17pct(self) -> None:
        assert GRANDFATHERED_POSITIONS["MU"]["expires_at"] == pytest.approx(0.170)

    def test_grandfathered_tsm_expires_at_14_6pct(self) -> None:
        assert GRANDFATHERED_POSITIONS["TSM"]["expires_at"] == pytest.approx(0.146)

    def test_grandfathered_cohr_expires_at_11_9pct(self) -> None:
        assert GRANDFATHERED_POSITIONS["COHR"]["expires_at"] == pytest.approx(0.119)

    def test_cluster_thresholds_ai_optics(self) -> None:
        thresholds = CLUSTER_THRESHOLDS["AI Optics"]
        assert thresholds["yellow"] == pytest.approx(0.27)
        assert thresholds["red"] == pytest.approx(0.30)

    def test_cluster_thresholds_ai_memory(self) -> None:
        thresholds = CLUSTER_THRESHOLDS["AI Memory"]
        assert thresholds["yellow"] == pytest.approx(0.22)
        assert thresholds["red"] == pytest.approx(0.25)

    def test_mu_in_ai_memory_cluster(self) -> None:
        assert TICKER_CLUSTER_MAP["MU"] == "AI Memory"

    def test_nbis_in_ai_infrastructure_cluster(self) -> None:
        assert TICKER_CLUSTER_MAP["NBIS"] == "AI Infrastructure"

    def test_tsm_in_foundry_cluster(self) -> None:
        assert TICKER_CLUSTER_MAP["TSM"] == "Foundry"


# ---------------------------------------------------------------------------
# evaluate_concentration — concentration cap logic (Test 1-8)
# ---------------------------------------------------------------------------


class TestEvaluateConcentration:
    # Test 1: MU at 13.6% — grandfathered
    def test_mu_at_13_6_pct_is_grandfathered(self) -> None:
        result = evaluate_concentration("MU", 0.136)
        assert result["concentration_status"] == ConcentrationStatus.GRANDFATHERED
        assert result["grandfathered"] is True
        assert result["soft_cap_breached"] is True
        assert result["hard_review_triggered"] is True
        assert result["cap_active"] is True
        assert result["adds_permitted"] is False
        assert result["score_display_cap"] == 85
        assert result["grandfathered_expires_at"] == pytest.approx(0.170)

    # Test 4: COHR at 9.5% — grandfathered
    def test_cohr_at_9_5_pct_is_grandfathered(self) -> None:
        result = evaluate_concentration("COHR", 0.095)
        assert result["concentration_status"] == ConcentrationStatus.GRANDFATHERED
        assert result["grandfathered"] is True
        assert result["grandfathered_expires_at"] == pytest.approx(0.119)
        assert result["cap_active"] is True
        assert result["adds_permitted"] is False

    # Test 7: exactly 8.0% — soft cap triggers
    def test_exactly_8_pct_triggers_soft_cap(self) -> None:
        result = evaluate_concentration("MRVL", 0.08)
        assert result["soft_cap_breached"] is True
        assert result["cap_active"] is True
        assert result["adds_permitted"] is False
        assert result["concentration_status"] == ConcentrationStatus.SOFT_CAP

    # Test 8: 7.9% — no cap
    def test_7_9_pct_no_cap(self) -> None:
        result = evaluate_concentration("MRVL", 0.079)
        assert result["soft_cap_breached"] is False
        assert result["cap_active"] is False
        assert result["adds_permitted"] is True
        assert result["concentration_status"] == ConcentrationStatus.NORMAL

    # Test 2: MRVL at 3.4% — normal
    def test_mrvl_at_3_4_pct_is_normal(self) -> None:
        result = evaluate_concentration("MRVL", 0.034)
        assert result["concentration_status"] == ConcentrationStatus.NORMAL
        assert result["soft_cap_breached"] is False
        assert result["grandfathered"] is False
        assert result["cap_active"] is False
        assert result["adds_permitted"] is True
        assert result["score_display_cap"] is None

    # Test 3: NBIS at 4.3% — normal
    def test_nbis_at_4_3_pct_is_normal(self) -> None:
        result = evaluate_concentration("NBIS", 0.043)
        assert result["concentration_status"] == ConcentrationStatus.NORMAL
        assert result["cap_active"] is False
        assert result["adds_permitted"] is True

    def test_above_10_pct_triggers_hard_review(self) -> None:
        result = evaluate_concentration("MRVL", 0.101)
        assert result["hard_review_triggered"] is True
        assert result["concentration_status"] == ConcentrationStatus.HARD_REVIEW
        assert result["trim_recommended"] is True

    def test_grandfathered_expires_when_weight_exceeds_threshold(self) -> None:
        # MU expires at 17.0%; if weight is 17.1% grandfathered status ends
        result = evaluate_concentration("MU", 0.171)
        assert result["grandfathered"] is False
        assert result["concentration_status"] == ConcentrationStatus.HARD_REVIEW

    def test_grandfathered_expiry_near_when_within_2pct(self) -> None:
        # MU expires at 17.0%; at 15.5% it is within 2pp of threshold
        result = evaluate_concentration("MU", 0.155)
        assert result["grandfathered_expiry_near"] is True

    def test_grandfathered_expiry_not_near_when_far_below_threshold(self) -> None:
        result = evaluate_concentration("MU", 0.136)
        assert result["grandfathered_expiry_near"] is False

    def test_score_display_cap_is_85_when_soft_cap_active(self) -> None:
        result = evaluate_concentration("MRVL", 0.09)
        assert result["score_display_cap"] == 85

    def test_score_display_cap_is_none_when_normal(self) -> None:
        result = evaluate_concentration("MRVL", 0.03)
        assert result["score_display_cap"] is None

    def test_trim_recommended_false_when_normal(self) -> None:
        result = evaluate_concentration("MRVL", 0.034)
        assert result["trim_recommended"] is False


# ---------------------------------------------------------------------------
# evaluate_cluster — cluster concentration logic (Test 5-6)
# ---------------------------------------------------------------------------


class TestEvaluateCluster:
    # Test 5: AI Optics cluster at 31% — red zone
    def test_ai_optics_at_31_pct_is_red_zone(self) -> None:
        result = evaluate_cluster("COHR", 0.31)
        assert result["cluster_status"] == ClusterStatus.RED_ZONE
        assert result["trim_recommended"] is True

    # Test 6: AI Memory at 23% — yellow zone
    def test_ai_memory_at_23_pct_is_yellow_zone(self) -> None:
        result = evaluate_cluster("MU", 0.23)
        assert result["cluster_status"] == ClusterStatus.YELLOW_ZONE
        assert result["trim_recommended"] is False

    def test_cluster_normal_below_yellow_threshold(self) -> None:
        result = evaluate_cluster("MU", 0.20)
        assert result["cluster_status"] == ClusterStatus.NORMAL

    def test_unknown_ticker_cluster_returns_unknown(self) -> None:
        result = evaluate_cluster("ZZZTEST", 0.05)
        assert result["cluster"] == "Unknown"

    def test_cluster_name_returned_correctly(self) -> None:
        result = evaluate_cluster("NBIS", 0.10)
        assert result["cluster"] == "AI Infrastructure"

    def test_foundry_cluster_red_zone_at_21pct(self) -> None:
        result = evaluate_cluster("TSM", 0.21)
        assert result["cluster_status"] == ClusterStatus.RED_ZONE

    def test_foundry_cluster_yellow_zone_at_18pct(self) -> None:
        result = evaluate_cluster("TSM", 0.18)
        assert result["cluster_status"] == ClusterStatus.YELLOW_ZONE

    def test_foundry_cluster_normal_at_16pct(self) -> None:
        result = evaluate_cluster("TSM", 0.16)
        assert result["cluster_status"] == ClusterStatus.NORMAL

    def test_thresholds_returned_in_result(self) -> None:
        result = evaluate_cluster("MU", 0.20)
        assert result["cluster_yellow_threshold"] == pytest.approx(0.22)
        assert result["cluster_red_threshold"] == pytest.approx(0.25)
