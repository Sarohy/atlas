"""Unit tests for Framework 8 — Insider Activity Flag (pure helpers only).

All tests are synchronous and cover only the pure functions:
  - _is_financial_sponsor
  - _has_10b51_language
  - _classify_filer_tier
  - _is_hard_pass
  - _resolve_f5_cap
  - _build_insider_analysis

The async network methods (_fetch_rss, compute) are tested via integration
tests that mock httpx.
"""

from __future__ import annotations

import pytest

from atlas.services.framework8_service import (
    InsiderTier,
    _build_insider_analysis,
    _classify_filer_tier,
    _has_10b51_language,
    _is_financial_sponsor,
    _is_hard_pass,
    _parse_form4_xml,
    _resolve_f5_cap,
)


# ---------------------------------------------------------------------------
# _is_financial_sponsor
# ---------------------------------------------------------------------------


class TestIsFinancialSponsor:
    """PE/financial-sponsor filer names bypass discretionary sale logic."""

    def test_bain_capital_is_sponsor(self) -> None:
        assert _is_financial_sponsor("Bain Capital Investors LLC") is True

    def test_blackstone_is_sponsor(self) -> None:
        assert _is_financial_sponsor("Blackstone Group Holdings") is True

    def test_kkr_is_sponsor(self) -> None:
        assert _is_financial_sponsor("KKR & Co Inc") is True

    def test_kkr_lowercase_is_sponsor(self) -> None:
        assert _is_financial_sponsor("kkr management l.p.") is True

    def test_carlyle_is_sponsor(self) -> None:
        assert _is_financial_sponsor("The Carlyle Group LP") is True

    def test_apollo_is_sponsor(self) -> None:
        assert _is_financial_sponsor("Apollo Global Management LLC") is True

    def test_ceo_is_not_sponsor(self) -> None:
        assert _is_financial_sponsor("John Smith, Chief Executive Officer") is False

    def test_empty_string_is_not_sponsor(self) -> None:
        assert _is_financial_sponsor("") is False

    def test_random_individual_is_not_sponsor(self) -> None:
        assert _is_financial_sponsor("Jane Doe") is False


# ---------------------------------------------------------------------------
# _has_10b51_language
# ---------------------------------------------------------------------------


class TestHas10b51Language:
    """Pre-planned sales under Rule 10b5-1 are excluded."""

    def test_detects_10b5_dash_1_notation(self) -> None:
        assert _has_10b51_language("Sold pursuant to 10b5-1 plan adopted in Jan") is True

    def test_detects_rule_10b51_variant(self) -> None:
        assert _has_10b51_language("Rule 10b5-1 trading plan") is True

    def test_detects_10b51_without_dash(self) -> None:
        assert _has_10b51_language("Transaction under Rule 10b51 plan") is True

    def test_detects_preplanned_phrase(self) -> None:
        assert _has_10b51_language("Sale pursuant to pre-planned trading plan") is True

    def test_detects_prearranged(self) -> None:
        assert _has_10b51_language("This is a prearranged sale") is True

    def test_ordinary_footnote_is_false(self) -> None:
        assert _has_10b51_language("Shares sold in open market transaction") is False

    def test_empty_footnote_is_false(self) -> None:
        assert _has_10b51_language("") is False

    def test_case_insensitive(self) -> None:
        assert _has_10b51_language("PURSUANT TO RULE 10B5-1 PLAN") is True


# ---------------------------------------------------------------------------
# _classify_filer_tier
# ---------------------------------------------------------------------------


class TestClassifyFilerTier:
    """Filer titles map to Tier 1, 2, or 3."""

    # Tier 1
    def test_ceo_is_tier1(self) -> None:
        assert _classify_filer_tier("Chief Executive Officer") == InsiderTier.TIER1

    def test_cfo_is_tier1(self) -> None:
        assert _classify_filer_tier("Chief Financial Officer") == InsiderTier.TIER1

    def test_coo_is_tier1(self) -> None:
        assert _classify_filer_tier("Chief Operating Officer") == InsiderTier.TIER1

    def test_president_is_tier1(self) -> None:
        assert _classify_filer_tier("President") == InsiderTier.TIER1

    def test_president_and_ceo_is_tier1(self) -> None:
        assert _classify_filer_tier("President and CEO") == InsiderTier.TIER1

    # Tier 2
    def test_cto_is_tier2(self) -> None:
        assert _classify_filer_tier("Chief Technology Officer") == InsiderTier.TIER2

    def test_cpo_is_tier2(self) -> None:
        assert _classify_filer_tier("Chief Product Officer") == InsiderTier.TIER2

    def test_cmo_is_tier2(self) -> None:
        assert _classify_filer_tier("Chief Marketing Officer") == InsiderTier.TIER2

    # Tier 3
    def test_director_is_tier3(self) -> None:
        assert _classify_filer_tier("Director") == InsiderTier.TIER3

    def test_svp_is_tier3(self) -> None:
        assert _classify_filer_tier("Senior Vice President, Engineering") == InsiderTier.TIER3

    def test_general_counsel_is_tier3(self) -> None:
        assert _classify_filer_tier("General Counsel") == InsiderTier.TIER3

    def test_unknown_title_defaults_to_tier3(self) -> None:
        assert _classify_filer_tier("") == InsiderTier.TIER3

    def test_case_insensitive_for_ceo(self) -> None:
        assert _classify_filer_tier("chief executive officer") == InsiderTier.TIER1


# ---------------------------------------------------------------------------
# _is_hard_pass
# ---------------------------------------------------------------------------


class TestIsHardPass:
    """Hard pass = many sales, zero purchases → remove from universe."""

    def test_many_sales_zero_purchases_is_hard_pass(self) -> None:
        assert _is_hard_pass(sale_count=8, purchase_count=0) is True

    def test_threshold_sales_zero_purchases_is_hard_pass(self) -> None:
        # Exactly at the threshold (5 sales) with no purchases
        assert _is_hard_pass(sale_count=5, purchase_count=0) is True

    def test_below_threshold_sales_is_not_hard_pass(self) -> None:
        assert _is_hard_pass(sale_count=3, purchase_count=0) is False

    def test_sales_with_any_purchase_is_not_hard_pass(self) -> None:
        assert _is_hard_pass(sale_count=10, purchase_count=1) is False

    def test_zero_sales_is_not_hard_pass(self) -> None:
        assert _is_hard_pass(sale_count=0, purchase_count=0) is False


# ---------------------------------------------------------------------------
# _resolve_f5_cap
# ---------------------------------------------------------------------------


class TestResolveF5Cap:
    """Large sales or Tier 1 filers cap F5 at 68; standard cap is 72."""

    # Large sale (above $1M) always → 68
    def test_large_sale_above_1m_gives_cap_68(self) -> None:
        assert _resolve_f5_cap(sale_usd=1_500_000.0, tier=InsiderTier.TIER3) == 68

    def test_sale_exactly_1m_gives_cap_68(self) -> None:
        assert _resolve_f5_cap(sale_usd=1_000_000.0, tier=InsiderTier.TIER3) == 68

    # Tier 1 filer regardless of amount → 68
    def test_tier1_small_sale_gives_cap_68(self) -> None:
        assert _resolve_f5_cap(sale_usd=200_000.0, tier=InsiderTier.TIER1) == 68

    # Standard: Tier 2/3 + below $1M → 72
    def test_tier2_small_sale_gives_cap_72(self) -> None:
        assert _resolve_f5_cap(sale_usd=500_000.0, tier=InsiderTier.TIER2) == 72

    def test_tier3_small_sale_gives_cap_72(self) -> None:
        assert _resolve_f5_cap(sale_usd=999_999.0, tier=InsiderTier.TIER3) == 72


# ---------------------------------------------------------------------------
# _build_insider_analysis — hardcoded tickers
# ---------------------------------------------------------------------------


class TestBuildInsiderAnalysis:
    """Hardcoded active-flag tickers bypass the API entirely."""

    # Hardcoded tickers: NBIS, CRDO, FN, COHR, CF
    @pytest.mark.parametrize("ticker", ["NBIS", "CRDO", "FN", "COHR", "CF"])
    def test_hardcoded_tickers_have_flag_active(self, ticker: str) -> None:
        result = _build_insider_analysis(ticker, filings=[])
        assert result.flag_active is True

    def test_hardcoded_ticker_case_insensitive(self) -> None:
        result = _build_insider_analysis("nbis", filings=[])
        assert result.flag_active is True

    def test_unknown_ticker_with_no_filings_has_flag_inactive(self) -> None:
        result = _build_insider_analysis("AAPL", filings=[])
        assert result.flag_active is False

    def test_cohr_is_sponsor_exception_preserves_flag(self) -> None:
        """COHR is hardcoded — sponsor exception does not matter here."""
        result = _build_insider_analysis("COHR", filings=[])
        assert result.flag_active is True

    def test_unknown_ticker_sponsor_sale_no_flag(self) -> None:
        """Sponsor sales are ignored — flag stays off for non-hardcoded ticker."""
        filing = {
            "transactionCode": "S",
            "reportingOwnerName": "Bain Capital Investors LLC",
            "transactionAmounts": {"transactionTotalValue": 5_000_000.0},
            "filingTitle": "Director",
            "footnotes": "",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.flag_active is False

    def test_discretionary_sale_activates_flag(self) -> None:
        filing = {
            "transactionCode": "S",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 600_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": "",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.flag_active is True

    def test_non_sale_transaction_ignored(self) -> None:
        filing = {
            "transactionCode": "A",  # Award
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 2_000_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": "",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.flag_active is False

    def test_10b51_sale_ignored(self) -> None:
        filing = {
            "transactionCode": "S",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 2_000_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": "Pursuant to a Rule 10b5-1 plan adopted in advance",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.flag_active is False

    def test_hard_pass_detected(self) -> None:
        filings = [
            {
                "transactionCode": "S",
                "reportingOwnerName": "Jane Doe",
                "transactionAmounts": {"transactionTotalValue": 200_000.0},
                "filingTitle": "Director",
                "footnotes": "",
            }
        ] * 6  # six sales, zero purchases
        result = _build_insider_analysis("XYZ", filings=filings)
        assert result.hard_pass is True
        assert result.flag_active is True

    def test_f5_cap_68_for_large_discretionary_sale(self) -> None:
        filing = {
            "transactionCode": "S",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 1_200_000.0},
            "filingTitle": "Director",
            "footnotes": "",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.f5_cap == 68

    def test_f5_cap_72_for_standard_discretionary_sale(self) -> None:
        filing = {
            "transactionCode": "S",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 400_000.0},
            "filingTitle": "Director",
            "footnotes": "",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.f5_cap == 72

    def test_f5_cap_none_when_flag_inactive(self) -> None:
        result = _build_insider_analysis("AAPL", filings=[])
        assert result.f5_cap is None

    def test_tier_set_on_active_flag(self) -> None:
        filing = {
            "transactionCode": "S",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 600_000.0},
            "filingTitle": "Chief Financial Officer",
            "footnotes": "",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.filer_tier == InsiderTier.TIER1


# ---------------------------------------------------------------------------
# _parse_form4_xml
# ---------------------------------------------------------------------------

_SALE_XML = """\
<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001779922</rptOwnerCik>
      <rptOwnerName>Doe Jane</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isOfficer>1</isOfficer>
      <officerTitle>Chief Executive Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding>
        <transactionCode>S</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>150.00</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""

_SALE_WITH_FOOTNOTE_XML = """\
<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerName>Smith Bob</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isOfficer>1</isOfficer>
      <officerTitle>Chief Financial Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding>
        <transactionCode>S</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>500</value></transactionShares>
        <transactionPricePerShare><value>200.00</value></transactionPricePerShare>
      </transactionAmounts>
      <footnoteId id="F1"/>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <footnotes>
    <footnote id="F1">This sale was made pursuant to a Rule 10b5-1 plan adopted in advance.</footnote>
  </footnotes>
</ownershipDocument>
"""

_MULTI_TXN_XML = """\
<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerName>Doe Jane</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <officerTitle>Director</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>2000</value></transactionShares>
        <transactionPricePerShare><value>100.00</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>300</value></transactionShares>
        <transactionPricePerShare><value>95.00</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


class TestParseForm4Xml:
    """_parse_form4_xml converts Form 4 XML into normalised filing dicts."""

    def test_returns_one_result_for_single_transaction(self) -> None:
        results = _parse_form4_xml(_SALE_XML)
        assert len(results) == 1

    def test_transaction_code_extracted(self) -> None:
        results = _parse_form4_xml(_SALE_XML)
        assert results[0]["transactionCode"] == "S"

    def test_owner_name_extracted(self) -> None:
        results = _parse_form4_xml(_SALE_XML)
        assert results[0]["reportingOwnerName"] == "Doe Jane"

    def test_officer_title_extracted_as_filing_title(self) -> None:
        results = _parse_form4_xml(_SALE_XML)
        assert results[0]["filingTitle"] == "Chief Executive Officer"

    def test_total_value_computed_from_shares_times_price(self) -> None:
        results = _parse_form4_xml(_SALE_XML)
        assert results[0]["transactionAmounts"]["transactionTotalValue"] == pytest.approx(150_000.0)

    def test_footnote_text_resolved_for_transaction(self) -> None:
        results = _parse_form4_xml(_SALE_WITH_FOOTNOTE_XML)
        assert "10b5-1" in results[0]["footnotes"]

    def test_no_footnote_reference_gives_empty_string(self) -> None:
        results = _parse_form4_xml(_SALE_XML)
        assert results[0]["footnotes"] == ""

    def test_multiple_transactions_returned(self) -> None:
        results = _parse_form4_xml(_MULTI_TXN_XML)
        assert len(results) == 2

    def test_multiple_transactions_have_correct_codes(self) -> None:
        results = _parse_form4_xml(_MULTI_TXN_XML)
        codes = {r["transactionCode"] for r in results}
        assert codes == {"S", "P"}

    def test_all_transactions_share_same_owner_name(self) -> None:
        results = _parse_form4_xml(_MULTI_TXN_XML)
        assert all(r["reportingOwnerName"] == "Doe Jane" for r in results)

    def test_malformed_xml_returns_empty_list(self) -> None:
        results = _parse_form4_xml("<this is not valid xml>>>")
        assert results == []

    def test_empty_string_returns_empty_list(self) -> None:
        results = _parse_form4_xml("")
        assert results == []

    def test_xml_with_no_transactions_returns_empty_list(self) -> None:
        xml = """\
<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>Nobody</rptOwnerName></reportingOwnerId>
  </reportingOwner>
</ownershipDocument>
"""
        results = _parse_form4_xml(xml)
        assert results == []

    def test_missing_price_defaults_to_zero_total(self) -> None:
        xml = """\
<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerName>A</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><officerTitle>CEO</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>100</value></transactionShares>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""
        results = _parse_form4_xml(xml)
        assert results[0]["transactionAmounts"]["transactionTotalValue"] == pytest.approx(0.0)
