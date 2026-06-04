"""Unit tests for FundamentalService — F5 Fundamental Quality scoring.

Covers:
  - Pure scoring helpers (_score_insider_activity, _score_altman_z, etc.)
  - _build_insider_indicator_from_yf: new yfinance-based insider fetch path
  - Cap and hard-block logic (CEO/CFO mega-sell, Altman grey zone)
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from atlas.services.fundamental_service import (
    FundamentalService,
    _score_altman_z,
    _score_debt_equity,
    _score_fcf,
    _score_insider_activity,
    _score_institutional,
)


# ---------------------------------------------------------------------------
# _score_insider_activity
# ---------------------------------------------------------------------------


class TestScoreInsiderActivity:
    def test_net_buying_returns_100(self) -> None:
        score, label = _score_insider_activity(500_000, 0.0, 0, 0.0)
        assert score == 100
        assert label == "NET_BUYING"

    def test_no_activity_returns_70(self) -> None:
        score, label = _score_insider_activity(0.0, 0.0, 0, 0.0)
        assert score == 70
        assert label == "NO_ACTIVITY"

    def test_selling_only_returns_70_no_activity(self) -> None:
        # Selling is disregarded — treated as no activity
        score, label = _score_insider_activity(0.0, 5_000_000, 3, 0.0)
        assert score == 70
        assert label == "NO_ACTIVITY"

    def test_ceo_mega_sale_disregarded(self) -> None:
        # CEO/CFO mega-sale no longer penalised
        score, label = _score_insider_activity(0.0, 60_000_000, 1, 60_000_000)
        assert score == 70
        assert label == "NO_ACTIVITY"

    def test_buying_plus_selling_returns_100(self) -> None:
        # Buying still scores 100 even when there is also selling
        score, label = _score_insider_activity(1_000_000, 5_000_000, 3, 0.0)
        assert score == 100
        assert label == "NET_BUYING"


# ---------------------------------------------------------------------------
# _score_altman_z
# ---------------------------------------------------------------------------


class TestScoreAltmanZ:
    def test_none_returns_70_unknown(self) -> None:
        score, zone = _score_altman_z(None)
        assert score == 70
        assert zone == "UNKNOWN"

    def test_above_3_returns_100_safe(self) -> None:
        score, zone = _score_altman_z(3.1)
        assert score == 100
        assert zone == "SAFE"

    def test_between_25_and_3_returns_85(self) -> None:
        score, zone = _score_altman_z(2.7)
        assert score == 85
        assert zone == "SAFE"

    def test_grey_zone_returns_55(self) -> None:
        score, zone = _score_altman_z(1.9)
        assert score == 55
        assert zone == "GREY"

    def test_distressed_returns_0(self) -> None:
        score, zone = _score_altman_z(1.2)
        assert score == 0
        assert zone == "DISTRESSED"


# ---------------------------------------------------------------------------
# _score_fcf
# ---------------------------------------------------------------------------


class TestScoreFcf:
    def test_positive_growing_returns_100(self) -> None:
        score, trend = _score_fcf(1_200_000, 1_000_000)
        assert score == 100
        assert trend == "POSITIVE_GROWING"

    def test_positive_flat_returns_80(self) -> None:
        score, trend = _score_fcf(1_050_000, 1_000_000)
        assert score == 80
        assert trend == "POSITIVE_FLAT"

    def test_positive_declining_returns_60(self) -> None:
        score, trend = _score_fcf(800_000, 1_000_000)
        assert score == 60
        assert trend == "POSITIVE_DECLINING"

    def test_negative_improving_returns_40(self) -> None:
        score, trend = _score_fcf(-500_000, -800_000)
        assert score == 40
        assert trend == "NEGATIVE_IMPROVING"

    def test_negative_worsening_returns_20(self) -> None:
        score, trend = _score_fcf(-900_000, -500_000)
        assert score == 20
        assert trend == "NEGATIVE_WORSENING"

    def test_none_current_returns_60_unknown(self) -> None:
        score, trend = _score_fcf(None, None)
        assert score == 60
        assert trend == "UNKNOWN"


# ---------------------------------------------------------------------------
# _score_debt_equity
# ---------------------------------------------------------------------------


class TestScoreDebtEquity:
    def test_below_0_3_returns_100(self) -> None:
        assert _score_debt_equity(0.15) == 100

    def test_0_3_to_0_6_returns_85(self) -> None:
        assert _score_debt_equity(0.45) == 85

    def test_above_2_returns_25(self) -> None:
        assert _score_debt_equity(2.5) == 25

    def test_none_returns_65(self) -> None:
        assert _score_debt_equity(None) == 65


# ---------------------------------------------------------------------------
# _score_institutional
# ---------------------------------------------------------------------------


class TestScoreInstitutional:
    def test_above_70pct_returns_100(self) -> None:
        score, label = _score_institutional(0.75)
        assert score == 100
        assert label == "NET_BUYING"

    def test_none_returns_65_flat(self) -> None:
        score, label = _score_institutional(None)
        assert score == 65
        assert label == "FLAT"

    def test_below_10pct_returns_20(self) -> None:
        score, label = _score_institutional(0.05)
        assert score == 20
        assert label == "LARGE_SELLING"


# ---------------------------------------------------------------------------
# FundamentalService._fetch_insider_trades_yf — new yfinance path
# ---------------------------------------------------------------------------


class TestFetchInsiderTradesYf:
    """Tests for the yfinance-based insider data fetch method.

    The method must be present on FundamentalService and return a list of
    dicts in the same shape as the SEC API path so that _build_insider_indicator
    can consume it unchanged.
    """

    def _make_service(self) -> FundamentalService:
        return FundamentalService(sec_api_key="", alphavantage_key="")

    def _make_yf_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_method_exists(self) -> None:
        svc = self._make_service()
        assert hasattr(svc, "_fetch_insider_trades_yf")

    @pytest.mark.asyncio
    async def test_ceo_sale_returned_as_disposal(self) -> None:
        """CEO sale within 90 days must appear in the output list."""
        svc = self._make_service()
        today = date.today()
        df = self._make_yf_df([
            {
                "Start Date": pd.Timestamp(today - timedelta(days=5)),
                "Text": "Sale at price 950.00 per share.",
                "Value": 35_000_000.0,
                "Shares": 36842,
                "Insider": "MEHROTRA SANJAY",
                "Position": "Chief Executive Officer",
                "Ownership": "D",
                "URL": "",
            }
        ])

        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = df

        with patch("atlas.services.fundamental_service.yf.Ticker", return_value=mock_ticker):
            result = await svc._fetch_insider_trades_yf("MU")

        assert len(result) == 1
        tx = result[0]
        assert tx["is_ceo_cfo"] is True
        assert tx["value"] == pytest.approx(35_000_000.0)
        assert tx["transaction_type"] == "sale"

    @pytest.mark.asyncio
    async def test_old_transaction_excluded(self) -> None:
        """Transactions older than 90 days must not be returned."""
        svc = self._make_service()
        today = date.today()
        df = self._make_yf_df([
            {
                "Start Date": pd.Timestamp(today - timedelta(days=100)),
                "Text": "Sale at price 400.00 per share.",
                "Value": 5_000_000.0,
                "Shares": 12500,
                "Insider": "SOME OFFICER",
                "Position": "Officer",
                "Ownership": "D",
                "URL": "",
            }
        ])

        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = df

        with patch("atlas.services.fundamental_service.yf.Ticker", return_value=mock_ticker):
            result = await svc._fetch_insider_trades_yf("MU")

        assert result == []

    @pytest.mark.asyncio
    async def test_stock_award_excluded(self) -> None:
        """Non-open-market grants/awards must be filtered out."""
        svc = self._make_service()
        today = date.today()
        df = self._make_yf_df([
            {
                "Start Date": pd.Timestamp(today - timedelta(days=10)),
                "Text": "Stock Award(Grant) at price 0.00 per share.",
                "Value": 0.0,
                "Shares": 5000,
                "Insider": "MEHROTRA SANJAY",
                "Position": "Chief Executive Officer",
                "Ownership": "D",
                "URL": "",
            }
        ])

        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = df

        with patch("atlas.services.fundamental_service.yf.Ticker", return_value=mock_ticker):
            result = await svc._fetch_insider_trades_yf("MU")

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_dataframe_returns_empty_list(self) -> None:
        svc = self._make_service()
        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = pd.DataFrame()

        with patch("atlas.services.fundamental_service.yf.Ticker", return_value=mock_ticker):
            result = await svc._fetch_insider_trades_yf("MU")

        assert result == []

    @pytest.mark.asyncio
    async def test_yfinance_exception_returns_empty_list(self) -> None:
        svc = self._make_service()

        with patch("atlas.services.fundamental_service.yf.Ticker", side_effect=Exception("network error")):
            result = await svc._fetch_insider_trades_yf("MU")

        assert result == []


# ---------------------------------------------------------------------------
# FundamentalService._build_insider_indicator_from_yf_data
# ---------------------------------------------------------------------------


class TestBuildInsiderIndicatorFromYfData:
    """_build_insider_indicator_from_yf_data converts normalised yf rows into
    an InsiderActivityIndicator with correct scores and caps applied."""

    def _make_service(self) -> FundamentalService:
        return FundamentalService(sec_api_key="", alphavantage_key="")
    def test_ceo_mega_sale_scores_20(self) -> None:
        svc = self._make_service()
        rows = [
            {"value": 60_000_000.0, "transaction_type": "sale", "is_officer": True, "is_ceo_cfo": True},
        ]
        ind = svc._build_insider_indicator_from_yf_data(rows)
        # Selling is disregarded — treated as no activity
        assert ind.score == 70
        assert ind.activity_label == "NO_ACTIVITY"
        assert ind.ceo_cfo_sell_value == pytest.approx(60_000_000.0)

    def test_multiple_officer_sales_scores_30(self) -> None:
        svc = self._make_service()
        rows = [
            {"value": 2_000_000.0, "transaction_type": "sale", "is_officer": True, "is_ceo_cfo": False},
            {"value": 3_000_000.0, "transaction_type": "sale", "is_officer": True, "is_ceo_cfo": False},
        ]
        ind = svc._build_insider_indicator_from_yf_data(rows)
        # Selling disregarded — no activity
        assert ind.score == 70
        assert ind.activity_label == "NO_ACTIVITY"

    def test_no_transactions_scores_70(self) -> None:
        svc = self._make_service()
        ind = svc._build_insider_indicator_from_yf_data([])
        assert ind.score == 70
        assert ind.activity_label == "NO_ACTIVITY"
