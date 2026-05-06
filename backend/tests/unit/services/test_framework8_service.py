"""Unit tests for Framework 8 — Insider Buying Detector (pure helpers only).

All tests are synchronous and cover only the pure functions:
  - _is_financial_sponsor
  - _has_10b51_language
  - _classify_filer_tier
  - _build_insider_analysis
  - _compute_buying_bonus
  - _detect_clustered_csuite_selling
  - _parse_form4_xml

The async network methods (_fetch_filings, compute) are tested via integration
tests that mock httpx.
"""

from __future__ import annotations

import pytest

from atlas.services.framework8_service import (
    InsiderTier,
    _build_insider_analysis,
    _classify_filer_tier,
    _compute_buying_bonus,
    _detect_clustered_csuite_selling,
    _has_10b51_language,
    _is_financial_sponsor,
    _parse_form4_xml,
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
# _compute_buying_bonus
# ---------------------------------------------------------------------------


class TestBuyingDetection:
    """Open-market purchases and awards yield an additive buying bonus."""

    def test_purchase_transaction_gives_bonus(self) -> None:
        filing = {
            "transactionCode": "P",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 200_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": "",
        }
        assert _compute_buying_bonus([filing]) > 0

    def test_award_transaction_gives_bonus(self) -> None:
        filing = {
            "transactionCode": "A",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 500_000.0},
            "filingTitle": "Chief Financial Officer",
            "footnotes": "",
        }
        assert _compute_buying_bonus([filing]) > 0

    def test_no_transactions_gives_zero_bonus(self) -> None:
        assert _compute_buying_bonus([]) == 0

    def test_sale_only_gives_zero_bonus(self) -> None:
        """Selling transactions must not reduce or affect the buying bonus."""
        filing = {
            "transactionCode": "S",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 2_000_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": "",
        }
        assert _compute_buying_bonus([filing]) == 0

    def test_sponsor_buy_counts(self) -> None:
        """A financial sponsor buying should still yield a bonus."""
        filing = {
            "transactionCode": "P",
            "reportingOwnerName": "Blackstone Group Holdings",
            "transactionAmounts": {"transactionTotalValue": 10_000_000.0},
            "filingTitle": "Director",
            "footnotes": "",
        }
        assert _compute_buying_bonus([filing]) > 0

    def test_multiple_buys_increase_bonus(self) -> None:
        """Multiple purchase transactions should yield a higher bonus than one."""
        single = {
            "transactionCode": "P",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 100_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": "",
        }
        bonus_one = _compute_buying_bonus([single])
        bonus_many = _compute_buying_bonus([single, single, single])
        assert bonus_many >= bonus_one

    def test_bonus_is_non_negative(self) -> None:
        """Buying bonus can never be negative."""
        assert _compute_buying_bonus([]) >= 0

    def test_sale_mixed_with_purchase_still_gives_bonus(self) -> None:
        """A mixed set of filings with at least one purchase yields a bonus."""
        filings = [
            {
                "transactionCode": "S",
                "reportingOwnerName": "Jane Doe",
                "transactionAmounts": {"transactionTotalValue": 1_000_000.0},
                "filingTitle": "Chief Executive Officer",
                "footnotes": "",
            },
            {
                "transactionCode": "P",
                "reportingOwnerName": "Jane Doe",
                "transactionAmounts": {"transactionTotalValue": 300_000.0},
                "filingTitle": "Chief Executive Officer",
                "footnotes": "",
            },
        ]
        assert _compute_buying_bonus(filings) > 0


# ---------------------------------------------------------------------------
# _detect_clustered_csuite_selling
# ---------------------------------------------------------------------------


class TestClusteredCsuiteSelling:
    """Multiple Tier1 discretionary sales produce a display-only note."""

    def _make_tier1_sale(self, name: str = "Jane Doe", footnote: str = "") -> dict:  # type: ignore[type-arg]
        return {
            "transactionCode": "S",
            "reportingOwnerName": name,
            "transactionAmounts": {"transactionTotalValue": 400_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": footnote,
        }

    def _make_tier3_sale(self) -> dict:  # type: ignore[type-arg]
        return {
            "transactionCode": "S",
            "reportingOwnerName": "Random VP",
            "transactionAmounts": {"transactionTotalValue": 50_000.0},
            "filingTitle": "Vice President",
            "footnotes": "",
        }

    def test_multiple_tier1_sales_no_10b51_gives_note(self) -> None:
        filings = [
            self._make_tier1_sale("CEO Person"),
            self._make_tier1_sale("CFO Person"),
        ]
        note = _detect_clustered_csuite_selling(filings)
        assert note is not None

    def test_note_is_non_empty_string(self) -> None:
        filings = [
            self._make_tier1_sale("CEO Person"),
            self._make_tier1_sale("CFO Person"),
        ]
        note = _detect_clustered_csuite_selling(filings)
        assert isinstance(note, str) and len(note) > 0

    def test_10b51_suppresses_note(self) -> None:
        """When all selling Tier1 filings have 10b5-1 plans, no note is raised."""
        filings = [
            self._make_tier1_sale("CEO Person", footnote="Pursuant to a 10b5-1 plan"),
            self._make_tier1_sale("CFO Person", footnote="Pre-planned sale per Rule 10b5-1"),
        ]
        note = _detect_clustered_csuite_selling(filings)
        assert note is None

    def test_single_csuite_sale_no_note(self) -> None:
        """Only 1 Tier1 sale is not 'clustered' — no note."""
        note = _detect_clustered_csuite_selling([self._make_tier1_sale()])
        assert note is None

    def test_no_filings_no_note(self) -> None:
        note = _detect_clustered_csuite_selling([])
        assert note is None

    def test_sponsor_sale_excluded_from_clustered_detection(self) -> None:
        """Sponsor selling doesn't count toward clustered C-suite detection."""
        filings = [
            {
                "transactionCode": "S",
                "reportingOwnerName": "Bain Capital Investors LLC",
                "transactionAmounts": {"transactionTotalValue": 5_000_000.0},
                "filingTitle": "Director",
                "footnotes": "",
            },
            {
                "transactionCode": "S",
                "reportingOwnerName": "KKR & Co Inc",
                "transactionAmounts": {"transactionTotalValue": 4_000_000.0},
                "filingTitle": "Director",
                "footnotes": "",
            },
        ]
        note = _detect_clustered_csuite_selling(filings)
        assert note is None

    def test_tier3_selling_no_note(self) -> None:
        """Non-C-suite selling (Tier3) does not trigger the note."""
        note = _detect_clustered_csuite_selling([self._make_tier3_sale(), self._make_tier3_sale()])
        assert note is None

    def test_note_has_no_score_impact_buying_bonus_unaffected(self) -> None:
        """When a clustered selling note is produced, the buying bonus is still 0
        (note is display-only, carries no scoring effect)."""
        filings = [
            self._make_tier1_sale("CEO Person"),
            self._make_tier1_sale("CFO Person"),
        ]
        note = _detect_clustered_csuite_selling(filings)
        bonus = _compute_buying_bonus(filings)
        assert note is not None
        assert bonus == 0  # selling-only set → zero buying bonus

    def test_mixed_tier1_with_and_without_10b51(self) -> None:
        """If at least one Tier1 sale lacks 10b5-1, a note is produced."""
        filings = [
            self._make_tier1_sale("CEO Person", footnote="Pursuant to 10b5-1 plan"),
            self._make_tier1_sale("CFO Person", footnote=""),  # no plan
        ]
        note = _detect_clustered_csuite_selling(filings)
        assert note is not None


# ---------------------------------------------------------------------------
# _build_insider_analysis
# ---------------------------------------------------------------------------


class TestBuildInsiderAnalysis:
    """Integration of buying bonus + clustered selling note in the analysis result."""

    def test_no_filings_gives_zero_buying_bonus(self) -> None:
        result = _build_insider_analysis("AAPL", filings=[])
        assert result.buying_bonus == 0

    def test_no_filings_gives_no_clustered_selling_note(self) -> None:
        result = _build_insider_analysis("AAPL", filings=[])
        assert result.clustered_selling_note is None

    def test_ticker_uppercased(self) -> None:
        result = _build_insider_analysis("aapl", filings=[])
        assert result.ticker == "AAPL"

    def test_sponsor_sale_no_note(self) -> None:
        """Sponsor sales are ignored — no clustered note."""
        filing = {
            "transactionCode": "S",
            "reportingOwnerName": "Bain Capital Investors LLC",
            "transactionAmounts": {"transactionTotalValue": 5_000_000.0},
            "filingTitle": "Director",
            "footnotes": "",
        }
        result = _build_insider_analysis("COHR", filings=[filing])
        assert result.clustered_selling_note is None

    def test_non_sale_transaction_gives_bonus(self) -> None:
        """An award transaction ('A') yields a positive buying bonus."""
        filing = {
            "transactionCode": "A",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 2_000_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": "",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.buying_bonus > 0

    def test_10b51_sale_ignored_for_note(self) -> None:
        """10b5-1 sales don't count toward clustered selling note."""
        filings = [
            {
                "transactionCode": "S",
                "reportingOwnerName": "CEO One",
                "transactionAmounts": {"transactionTotalValue": 400_000.0},
                "filingTitle": "Chief Executive Officer",
                "footnotes": "Pursuant to a Rule 10b5-1 plan adopted in advance",
            },
            {
                "transactionCode": "S",
                "reportingOwnerName": "CFO Two",
                "transactionAmounts": {"transactionTotalValue": 300_000.0},
                "filingTitle": "Chief Financial Officer",
                "footnotes": "Pre-planned Rule 10b5-1 sale",
            },
        ]
        result = _build_insider_analysis("XYZ", filings=filings)
        assert result.clustered_selling_note is None

    def test_purchase_gives_positive_buying_bonus(self) -> None:
        filing = {
            "transactionCode": "P",
            "reportingOwnerName": "Jane Doe",
            "transactionAmounts": {"transactionTotalValue": 500_000.0},
            "filingTitle": "Chief Executive Officer",
            "footnotes": "",
        }
        result = _build_insider_analysis("XYZ", filings=[filing])
        assert result.buying_bonus > 0

    def test_clustered_selling_triggers_note(self) -> None:
        filings = [
            {
                "transactionCode": "S",
                "reportingOwnerName": "CEO Person",
                "transactionAmounts": {"transactionTotalValue": 400_000.0},
                "filingTitle": "Chief Executive Officer",
                "footnotes": "",
            },
            {
                "transactionCode": "S",
                "reportingOwnerName": "CFO Person",
                "transactionAmounts": {"transactionTotalValue": 300_000.0},
                "filingTitle": "Chief Financial Officer",
                "footnotes": "",
            },
        ]
        result = _build_insider_analysis("XYZ", filings=filings)
        assert result.clustered_selling_note is not None

    def test_clustered_selling_does_not_reduce_buying_bonus(self) -> None:
        """A clustered selling note must have zero effect on the buying bonus."""
        filings = [
            {
                "transactionCode": "S",
                "reportingOwnerName": "CEO Person",
                "transactionAmounts": {"transactionTotalValue": 400_000.0},
                "filingTitle": "Chief Executive Officer",
                "footnotes": "",
            },
            {
                "transactionCode": "S",
                "reportingOwnerName": "CFO Person",
                "transactionAmounts": {"transactionTotalValue": 300_000.0},
                "filingTitle": "Chief Financial Officer",
                "footnotes": "",
            },
        ]
        result = _build_insider_analysis("XYZ", filings=filings)
        assert result.buying_bonus == 0  # selling set → no bonus


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
