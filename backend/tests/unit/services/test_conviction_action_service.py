"""Unit tests for the Framework 6 Conviction Action service pure helpers.

Tests cover _tier_from_score — the sole pure function.  All tier boundaries
are exercised: > 80, 72-80, 65-72, 60-65, < 60.
"""

from __future__ import annotations

import pytest

from atlas.services.conviction_action_service import _tier_from_score


# ---------------------------------------------------------------------------
# Score > 80 — HOLD
# ---------------------------------------------------------------------------


class TestTierHold:
    def test_score_100(self) -> None:
        tier_key, status, actions, tone = _tier_from_score(100)
        assert tier_key == "HOLD"

    def test_score_81(self) -> None:
        _, status, _, _ = _tier_from_score(81)
        assert status == "Hold full — add on dips"

    def test_score_90_actions(self) -> None:
        _, _, actions, _ = _tier_from_score(90)
        assert "Hold full — add on dips" in actions

    def test_score_90_tone(self) -> None:
        _, _, _, tone = _tier_from_score(90)
        assert tone == "green"

    def test_score_80_is_not_hold(self) -> None:
        tier_key, _, _, _ = _tier_from_score(80)
        assert tier_key != "HOLD"


# ---------------------------------------------------------------------------
# Score 72–80 — READY
# ---------------------------------------------------------------------------


class TestTierReady:
    def test_score_80(self) -> None:
        tier_key, _, _, _ = _tier_from_score(80)
        assert tier_key == "READY"

    def test_score_72(self) -> None:
        tier_key, _, _, _ = _tier_from_score(72)
        assert tier_key == "READY"

    def test_score_76_status(self) -> None:
        _, status, _, _ = _tier_from_score(76)
        assert status == "Deploy T2/T3"

    def test_score_76_actions(self) -> None:
        _, _, actions, _ = _tier_from_score(76)
        assert "Deploy T2/T3" in actions

    def test_score_76_tone(self) -> None:
        _, _, _, tone = _tier_from_score(76)
        assert tone == "cyan"

    def test_score_71_is_not_ready(self) -> None:
        tier_key, _, _, _ = _tier_from_score(71)
        assert tier_key != "READY"


# ---------------------------------------------------------------------------
# Score 65–71 — EARLY
# ---------------------------------------------------------------------------


class TestTierEarly:
    def test_score_71(self) -> None:
        tier_key, _, _, _ = _tier_from_score(71)
        assert tier_key == "EARLY"

    def test_score_65(self) -> None:
        tier_key, _, _, _ = _tier_from_score(65)
        assert tier_key == "EARLY"

    def test_score_68_status(self) -> None:
        _, status, _, _ = _tier_from_score(68)
        assert status == "Small positions, options preferred"

    def test_score_68_actions(self) -> None:
        _, _, actions, _ = _tier_from_score(68)
        assert "Small positions, options preferred" in actions

    def test_score_68_tone(self) -> None:
        _, _, _, tone = _tier_from_score(68)
        assert tone == "yellow"

    def test_score_64_is_not_early(self) -> None:
        tier_key, _, _, _ = _tier_from_score(64)
        assert tier_key != "EARLY"


# ---------------------------------------------------------------------------
# Score 60–64 — RADAR
# ---------------------------------------------------------------------------


class TestTierRadar:
    def test_score_64(self) -> None:
        tier_key, _, _, _ = _tier_from_score(64)
        assert tier_key == "RADAR"

    def test_score_60(self) -> None:
        tier_key, _, _, _ = _tier_from_score(60)
        assert tier_key == "RADAR"

    def test_score_62_status(self) -> None:
        _, status, _, _ = _tier_from_score(62)
        assert status == "No deployment — monitor"

    def test_score_62_actions(self) -> None:
        _, _, actions, _ = _tier_from_score(62)
        assert "No deployment — monitor" in actions

    def test_score_62_tone(self) -> None:
        _, _, _, tone = _tier_from_score(62)
        assert tone == "orange"

    def test_score_59_is_not_radar(self) -> None:
        tier_key, _, _, _ = _tier_from_score(59)
        assert tier_key != "RADAR"


# ---------------------------------------------------------------------------
# Score < 60 — EXIT
# ---------------------------------------------------------------------------


class TestTierExit:
    def test_score_59(self) -> None:
        tier_key, _, _, _ = _tier_from_score(59)
        assert tier_key == "EXIT"

    def test_score_0(self) -> None:
        tier_key, _, _, _ = _tier_from_score(0)
        assert tier_key == "EXIT"

    def test_score_59_status(self) -> None:
        _, status, _, _ = _tier_from_score(59)
        assert status == "Sell on next bounce"

    def test_score_59_actions(self) -> None:
        _, _, actions, _ = _tier_from_score(59)
        assert "Sell on next bounce" in actions

    def test_score_59_tone(self) -> None:
        _, _, _, tone = _tier_from_score(59)
        assert tone == "red"
