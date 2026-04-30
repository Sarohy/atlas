"""Framework 8 — Insider Activity Flag service.

Decision flow
-------------
1. Fetch SEC EDGAR submissions + Form 4 XML for the ticker (free public API,
   no API key required — only a User-Agent header).  Only transaction code
   "S" (sale) filings are processed.

2. Three sequential filters for each sale:
   a. Financial-sponsor check — if the filer name matches a known PE / sponsor
      firm (e.g. Bain Capital) the sale is not counted as discretionary (the
      "COHR / Bain Capital exception").  No F5 cap is applied.
   b. Rule 10b5-1 check — footnotes containing pre-planned sale language cause
      the sale to be ignored entirely.
   c. If neither exception applies → discretionary sale confirmed; flag raised.

3. Filer title is classified into InsiderTier (TIER1 / TIER2 / TIER3).

4. Hard-pass check: >= 5 sales with zero purchases -> ticker removed from
   investable universe (CF Industries pattern).

5. F5 cap resolution:
   * Large sale (>= $1 M) OR Tier 1 filer -> cap F5 at 68
   * Standard discretionary sale -> cap F5 at 72

Pure helpers (_is_financial_sponsor, _has_10b51_language, _classify_filer_tier,
_is_hard_pass, _resolve_f5_cap, _build_insider_analysis) contain zero I/O so
they can be unit-tested synchronously.

The async method (compute) owns all network I/O via the SEC EDGAR feed.
"""

from __future__ import annotations

import logging
import re as _re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Any, Final

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Known PE / financial-sponsor name fragments (lower-case, substring match).
_SPONSOR_KEYWORDS: frozenset[str] = frozenset(
    {
        "bain capital",
        "blackstone",
        "kkr",
        "carlyle",
        "apollo",
        "silver lake",
        "warburg pincus",
        "general atlantic",
        "vista equity",
        "thoma bravo",
    }
)

# Phrases in footnotes that signal a Rule 10b5-1 pre-planned sale.
_PLAN_KEYWORDS: frozenset[str] = frozenset(
    {
        "10b5-1",
        "10b51",
        "pre-planned",
        "preplanned",
        "prearranged",
        "pre-arranged",
    }
)

# Filer title fragments that map to each tier (checked in order; first match wins).
_TIER1_KEYWORDS: frozenset[str] = frozenset(
    {"chief executive", "ceo", "chief financial", "cfo", "chief operating", "coo", "president"}
)
_TIER2_KEYWORDS: frozenset[str] = frozenset(
    {"chief technology", "cto", "chief product", "cpo", "chief marketing", "cmo"}
)

# Hard-pass: >= this many sales with 0 purchases -> remove from universe.
_HARD_PASS_SALE_THRESHOLD: Final[int] = 5

# F5 cap values.
_F5_CAP_LARGE: Final[int] = 68    # large sale (>= $1M) OR Tier 1 filer
_F5_CAP_STANDARD: Final[int] = 72  # standard discretionary sale

# Sale USD threshold for the large-sale cap.
_LARGE_SALE_THRESHOLD: Final[float] = 1_000_000.0

# In-memory cache TTL (24 hours).
_CACHE_TTL_SECONDS: Final[int] = 86_400

# Module-level cache: ticker -> (InsiderAnalysisResponse, unix_timestamp)
_cache: dict[str, tuple[InsiderAnalysisResponse, float]] = {}

# Module-level CIK cache: upper-case ticker -> zero-padded 10-digit CIK string
_cik_cache: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class InsiderTier(StrEnum):
    """Officer seniority tier used to calibrate the F5 cap."""

    TIER1 = "TIER1"  # CEO, CFO, COO, President
    TIER2 = "TIER2"  # CTO, CPO, CMO
    TIER3 = "TIER3"  # Directors, other officers


# Forward reference resolved after InsiderAnalysisResponse is imported in the
# schema module.  The local dataclass is defined here to keep the service
# self-contained and avoid a circular import.


@dataclass
class InsiderAnalysisResponse:
    """Lightweight result returned by _build_insider_analysis and compute().

    The Pydantic schema (atlas.schemas.framework8) wraps this for the API
    response model; the service uses this dataclass internally.
    """

    ticker: str
    flag_active: bool
    hard_pass: bool
    filer_tier: InsiderTier | None
    largest_sale_usd: float | None
    f5_cap: int | None
    source: str  # "hardcoded" | "sec_edgar" | "default"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _is_financial_sponsor(filer_name: str) -> bool:
    """Return True when *filer_name* matches a known PE / financial sponsor.

    Case-insensitive substring search against _SPONSOR_KEYWORDS.
    Pure function — no I/O.
    """
    lower = filer_name.lower()
    return any(kw in lower for kw in _SPONSOR_KEYWORDS)


def _has_10b51_language(footnotes: str) -> bool:
    """Return True when *footnotes* contain pre-planned-trade language.

    Detects Rule 10b5-1 plan references and synonymous phrases.
    Pure function — no I/O.
    """
    lower = footnotes.lower()
    return any(kw in lower for kw in _PLAN_KEYWORDS)


# Compiled Tier-2 pattern — word-boundary match to avoid "director" → "cto".
_TIER2_RE: _re.Pattern[str] = _re.compile(
    r"\b(chief technology officer|cto|chief product officer|cpo|chief marketing officer|cmo)\b",
    _re.IGNORECASE,
)


def _classify_filer_tier(title: str) -> InsiderTier:
    """Map a filer's title string to an InsiderTier.

    Tier 1: CEO / CFO / COO / President (but NOT Vice President or Director)
    Tier 2: CTO / CPO / CMO
    Tier 3: Directors, other officers, or unrecognised titles (safe default)

    Pure function — no I/O.
    """
    lower = title.lower()

    # Tier 2 checked first — use regex word-boundary to avoid "director" → "cto".
    if _TIER2_RE.search(title):
        return InsiderTier.TIER2

    # Tier 1 — match only when the title is not a variant like "Vice President"
    # or "Director" (which contain "president" / none but should map to Tier 3).
    is_vp = "vice president" in lower
    is_director = "director" in lower
    if not is_vp and not is_director and any(kw in lower for kw in _TIER1_KEYWORDS):
        return InsiderTier.TIER1

    return InsiderTier.TIER3


def _is_hard_pass(sale_count: int, purchase_count: int) -> bool:
    """Return True when the insider pattern is disqualifying.

    Hard pass = >= _HARD_PASS_SALE_THRESHOLD sales AND zero purchases.
    Signals a stock to remove from the investable universe entirely.

    Pure function — no I/O.
    """
    return sale_count >= _HARD_PASS_SALE_THRESHOLD and purchase_count == 0


def _resolve_f5_cap(sale_usd: float, tier: InsiderTier) -> int:
    """Return the F5 score cap for a confirmed discretionary sale.

    Cap of 68 applies when:
      - sale value >= $1 M, OR
      - filer is Tier 1 (CEO / CFO / COO / President)

    Otherwise the standard cap of 72 applies.

    Pure function — no I/O.
    """
    if sale_usd >= _LARGE_SALE_THRESHOLD or tier == InsiderTier.TIER1:
        return _F5_CAP_LARGE
    return _F5_CAP_STANDARD


def _build_insider_analysis(
    ticker: str,
    filings: list[dict[str, Any]],
) -> InsiderAnalysisResponse:
    """Build an InsiderAnalysisResponse from pre-fetched filing dicts.

    Runs the three-filter pipeline (sponsor check, 10b5-1 check, discretionary
    classification) over *filings*.

    Pure function — no I/O (filings already fetched by the caller).
    """
    upper = ticker.strip().upper()

    # ── Parse filings with three-filter pipeline ─────────────────────────
    sale_count = 0
    purchase_count = 0
    flag_active = False
    best_tier: InsiderTier = InsiderTier.TIER3
    largest_sale: float = 0.0

    for filing in filings:
        code: str = filing.get("transactionCode", "")
        if code != "S":
            if code in ("P", "A"):
                purchase_count += 1
            continue

        sale_count += 1

        filer_name: str = filing.get("reportingOwnerName", "")
        footnotes: str = filing.get("footnotes", "") or ""
        amounts: dict[str, Any] = filing.get("transactionAmounts", {}) or {}
        try:
            sale_usd = abs(float(amounts.get("transactionTotalValue", 0) or 0))
        except (TypeError, ValueError):
            sale_usd = 0.0

        # Filter a: financial-sponsor exception — not discretionary.
        if _is_financial_sponsor(filer_name):
            continue

        # Filter b: Rule 10b5-1 pre-planned sale — ignore.
        if _has_10b51_language(footnotes):
            continue

        # Filter c: confirmed discretionary sale.
        flag_active = True
        title: str = filing.get("filingTitle", "")
        tier = _classify_filer_tier(title)

        # Track the most senior tier seen.
        if tier == InsiderTier.TIER1 or (
            tier == InsiderTier.TIER2 and best_tier == InsiderTier.TIER3
        ):
            best_tier = tier

        if sale_usd > largest_sale:
            largest_sale = sale_usd

    # ── 3. Hard-pass check ────────────────────────────────────────────────
    hard_pass = _is_hard_pass(sale_count, purchase_count)

    # ── 4. Resolve F5 cap ─────────────────────────────────────────────────
    f5_cap: int | None = None
    if flag_active:
        f5_cap = _resolve_f5_cap(largest_sale, best_tier)

    return InsiderAnalysisResponse(
        ticker=upper,
        flag_active=flag_active,
        hard_pass=hard_pass,
        filer_tier=best_tier if flag_active else None,
        largest_sale_usd=largest_sale if flag_active else None,
        f5_cap=f5_cap,
        source="sec_edgar",
    )


def _parse_form4_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parse a Form 4 XML document into a list of normalised transaction dicts.

    Each dict has the same keys expected by ``_build_insider_analysis``:
    ``transactionCode``, ``reportingOwnerName``,
    ``transactionAmounts.transactionTotalValue``, ``filingTitle``,
    ``footnotes``.

    Returns an empty list when *xml_text* is empty or malformed.
    Pure function — no I/O.
    """
    if not xml_text or not xml_text.strip():
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # Owner info is shared across all transactions in one Form 4.
    owner_name: str = root.findtext(".//rptOwnerName") or ""
    officer_title: str = root.findtext(".//officerTitle") or ""

    # Build footnote id → text map.
    footnotes: dict[str, str] = {}
    for fn in root.findall(".//footnotes/footnote"):
        fn_id = fn.get("id", "")
        footnotes[fn_id] = (fn.text or "").strip()

    results: list[dict[str, Any]] = []
    for txn in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
        code: str = txn.findtext("transactionCoding/transactionCode") or ""

        shares_text = txn.findtext("transactionAmounts/transactionShares/value") or "0"
        price_text = (
            txn.findtext("transactionAmounts/transactionPricePerShare/value") or "0"
        )
        try:
            total_value = abs(float(shares_text)) * abs(float(price_text))
        except (ValueError, TypeError):
            total_value = 0.0

        # Resolve all footnote references attached to this transaction.
        txn_footnote_ids = [ref.get("id", "") for ref in txn.findall("footnoteId")]
        txn_footnotes = " ".join(
            footnotes[fid] for fid in txn_footnote_ids if fid in footnotes
        )

        results.append(
            {
                "transactionCode": code,
                "reportingOwnerName": owner_name,
                "transactionAmounts": {"transactionTotalValue": total_value},
                "filingTitle": officer_title,
                "footnotes": txn_footnotes,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class Framework8Service:
    """Framework 8 — Insider Activity Flag.

    Checks SEC EDGAR Form 4 filings for recent discretionary insider selling.
    Hardcoded tickers bypass the API entirely.

    Parameters
    ----------
    sec_api_key:
        Retained for backward-compatibility with Framework 7 instantiation.
        The EDGAR RSS feed is public and requires no key.
    """

    def __init__(self, sec_api_key: str = "") -> None:
        self._sec_api_key = sec_api_key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compute(self, ticker: str) -> InsiderAnalysisResponse:
        """Return the insider activity analysis for *ticker*.

        Uses a 24-hour in-process cache to avoid redundant feed fetches.
        Safe defaults (flag_active=False) are returned on network errors.
        """
        upper = ticker.strip().upper()

        # Cache hit.
        if upper in _cache:
            cached, ts = _cache[upper]
            if time.monotonic() - ts < _CACHE_TTL_SECONDS:
                return cached

        filings = await self._fetch_filings(upper)
        result = _build_insider_analysis(upper, filings=filings)
        _cache[upper] = (result, time.monotonic())
        return result

    async def get_insider_flag(self, ticker: str) -> bool:
        """Backward-compatible boolean flag for Framework 7.

        Returns True when Framework 8 has an active insider flag for *ticker*.
        """
        result = await self.compute(ticker)
        return result.flag_active

    # ------------------------------------------------------------------
    # Private I/O
    # ------------------------------------------------------------------

    async def _resolve_cik(self, ticker: str, client: httpx.AsyncClient) -> str | None:
        """Return the zero-padded 10-digit CIK for *ticker*, or None if unknown.

        Uses a module-level cache so the company_tickers.json download only
        happens once per process lifetime.
        """
        if ticker in _cik_cache:
            return _cik_cache[ticker]

        resp = await client.get("https://www.sec.gov/files/company_tickers.json")
        if resp.status_code != 200:
            return None

        data: dict[str, Any] = resp.json()
        for entry in data.values():
            if not isinstance(entry, dict):
                continue
            if str(entry.get("ticker", "")).upper() == ticker:
                cik = str(entry["cik_str"]).zfill(10)
                _cik_cache[ticker] = cik
                return cik
        return None

    async def _fetch_filings(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch recent Form 4 transaction data for *ticker* from SEC EDGAR.

        Three-step process:
          1. Resolve ticker → CIK via company_tickers.json (cached).
          2. Get recent Form 4 accession numbers via the submissions API.
          3. Fetch and parse each Form 4 XML (≤ 10 filings, last 90 days).

        Returns an empty list on any network or parsing error so that the
        safe-default (no insider flag) applies.
        """
        cutoff = date.today() - timedelta(days=90)

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": "atlas-investing contact@atlas.dev"},
            ) as client:
                # Step 1: resolve CIK.
                cik = await self._resolve_cik(ticker, client)
                if not cik:
                    logger.warning(
                        "Framework 8: CIK not found for ticker",
                        extra={"ticker": ticker},
                    )
                    return []

                # Step 2: get the submissions list for this issuer.
                subs_resp = await client.get(
                    f"https://data.sec.gov/submissions/CIK{cik}.json",
                )
                if subs_resp.status_code != 200:
                    logger.warning(
                        "Framework 8: submissions fetch failed",
                        extra={"ticker": ticker, "status": subs_resp.status_code},
                    )
                    return []

                subs: dict[str, Any] = subs_resp.json()
                recent: dict[str, Any] = (
                    subs.get("filings", {}).get("recent", {}) or {}
                )
                forms: list[str] = recent.get("form", []) or []
                accessions: list[str] = recent.get("accessionNumber", []) or []
                filing_dates: list[str] = recent.get("filingDate", []) or []
                primary_docs: list[str] = recent.get("primaryDocument", []) or []

                # Step 3: collect Form 4 accessions within the last 90 days.
                # The submissions list is reverse-chronological, so we can break
                # early once we pass the cutoff date.
                form4_items: list[tuple[str, str]] = []  # (accession_nodash, doc)
                for form, acc, fdate, pdoc in zip(
                    forms, accessions, filing_dates, primary_docs, strict=False
                ):
                    if form not in ("4", "4/A"):
                        continue
                    try:
                        if date.fromisoformat(fdate) < cutoff:
                            break
                    except ValueError:
                        continue
                    # The submissions API returns primaryDocument with a
                    # stylesheet prefix (e.g. "xslF345X06/primarydocument.xml").
                    # The raw XML lives at the filename only — strip any path.
                    raw_doc = pdoc.split("/")[-1] if pdoc else "primarydocument.xml"
                    form4_items.append((acc.replace("-", ""), raw_doc))
                    if len(form4_items) >= 10:
                        break

                # Step 4: fetch and parse each Form 4 XML.
                cik_int = int(cik)
                all_filings: list[dict[str, Any]] = []
                for acc_nodash, pdoc in form4_items:
                    xml_url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{cik_int}/{acc_nodash}/{pdoc}"
                    )
                    try:
                        xml_resp = await client.get(xml_url)
                        if xml_resp.status_code == 200:
                            all_filings.extend(_parse_form4_xml(xml_resp.text))
                    except Exception as exc:
                        logger.debug(
                            "Framework 8: XML fetch failed",
                            extra={"accession": acc_nodash, "error": repr(exc)},
                        )
                        continue

                return all_filings

        except Exception as exc:
            logger.warning(
                "Framework 8 EDGAR fetch failed; defaulting to no flag",
                extra={"ticker": ticker, "error": repr(exc)},
            )
            return []
