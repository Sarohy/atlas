"""Free EDGAR pulls for FGS — backlog (RPO) and customer concentration.

Uses only the free SEC EDGAR public APIs (no key, requires a User-Agent):
  * ``data.sec.gov/api/xbrl/companyconcept`` — structured XBRL facts (backlog /
    remaining performance obligation, when the filer tags it),
  * ``data.sec.gov/submissions`` + ``www.sec.gov/Archives`` — the latest 10-K
    text, parsed for the customer-concentration disclosure.

Both are best-effort: many filers (especially smaller high-flyers) don't tag a
remaining-performance-obligation, and some disclose customer concentration only
as a ">10% customer" count rather than an exact percentage. Callers treat a None
result as DATA_GAP, never a penalty.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Final

import httpx

_SEC_HEADERS: Final[dict[str, str]] = {"User-Agent": "atlas-investing contact@atlas.dev"}
_TIMEOUT: Final[float] = 20.0
_COMPANY_TICKERS_URL: Final[str] = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL: Final[str] = "https://data.sec.gov/submissions/CIK{cik}.json"
_CONCEPT_URL: Final[str] = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
_ARCHIVE_URL: Final[str] = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

# XBRL tags that represent backlog / contracted future revenue, most-preferred first.
_RPO_TAGS: Final[tuple[str, ...]] = (
    "RevenueRemainingPerformanceObligation",
    "ContractWithCustomerLiability",  # deferred revenue — weak proxy, last resort
)

# Only scan the first chunk of a 10-K (the concentration note is early, and full
# filings can be many MB).
_MAX_FILING_CHARS: Final[int] = 800_000

# Module-level CIK cache (ticker upper -> zero-padded 10-digit CIK).
_cik_cache: dict[str, str] = {}


@dataclass(frozen=True)
class CustomerConcentration:
    """Customer-concentration disclosure parsed from the latest 10-K."""

    largest_customer_pct: float | None  # exact % when a single customer figure is stated
    customers_over_10pct: int | None  # count of customers each >10% of revenue
    summary: str | None  # short verbatim snippet for transparency


async def resolve_cik(client: httpx.AsyncClient, ticker: str) -> str | None:
    """Return the zero-padded 10-digit CIK for *ticker*, or None. Cached."""
    sym = ticker.upper()
    if sym in _cik_cache:
        return _cik_cache[sym]
    try:
        resp = await client.get(_COMPANY_TICKERS_URL, headers=_SEC_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
        return None
    for entry in data.values():
        if isinstance(entry, dict) and str(entry.get("ticker", "")).upper() == sym:
            cik = str(entry["cik_str"]).zfill(10)
            _cik_cache[sym] = cik
            return cik
    return None


async def fetch_backlog_usd(client: httpx.AsyncClient, cik: str) -> float | None:
    """Return the latest remaining-performance-obligation (backlog) USD, or None.

    Only the dedicated RPO tag is treated as real backlog; the deferred-revenue
    fallback is intentionally NOT used for scoring (kept out to avoid mislabeling
    deferred revenue as backlog). Returns None when the filer does not tag RPO.
    """
    try:
        resp = await client.get(
            _CONCEPT_URL.format(cik=cik, tag=_RPO_TAGS[0]),
            headers=_SEC_HEADERS,
            timeout=_TIMEOUT,
        )
    except (httpx.HTTPStatusError, httpx.RequestError):
        return None
    if resp.status_code != 200:
        return None
    try:
        units = resp.json().get("units", {})
    except ValueError:
        return None
    usd = units.get("USD") or []
    if not usd:
        return None
    latest = max(usd, key=lambda v: str(v.get("end", "")))
    val = latest.get("val")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


async def fetch_customer_concentration(
    client: httpx.AsyncClient, cik: str
) -> CustomerConcentration | None:
    """Parse the latest 10-K for the customer-concentration disclosure.

    Returns None when no 10-K or no concentration language is found.
    """
    doc_text = await _fetch_latest_10k_text(client, cik)
    if not doc_text:
        return None
    return _parse_customer_concentration(doc_text)


async def _fetch_latest_10k_text(client: httpx.AsyncClient, cik: str) -> str:
    """Fetch + de-tag the latest 10-K primary document (capped length)."""
    try:
        sub = (
            await client.get(
                _SUBMISSIONS_URL.format(cik=cik), headers=_SEC_HEADERS, timeout=_TIMEOUT
            )
        ).json()
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
        return ""
    recent = sub.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    idx = next((i for i, f in enumerate(forms) if f == "10-K"), None)
    if idx is None:
        return ""
    acc = recent["accessionNumber"][idx].replace("-", "")
    doc = recent["primaryDocument"][idx]
    url = _ARCHIVE_URL.format(cik=int(cik), acc=acc, doc=doc)
    try:
        raw = (await client.get(url, headers=_SEC_HEADERS, timeout=60.0)).text
    except (httpx.HTTPStatusError, httpx.RequestError):
        return ""
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw[: _MAX_FILING_CHARS * 4]))
    return re.sub(r"\s+", " ", text)[:_MAX_FILING_CHARS]


# A percentage attributed to a SPECIFIC single customer (not a market/geo/segment
# "% of revenue", which causes false positives). Requires explicit single-customer
# language adjacent to the figure.
_SINGLE_CUSTOMER_PCT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:one customer|a single customer|(?:our |the )?largest customer|one client|"
    r"customer\s+[A-Z]\b)[^.]{0,70}?(\d{1,2}(?:\.\d+)?)\s?%"
    r"|(\d{1,2}(?:\.\d+)?)\s?%[^.]{0,50}?(?:from|by)\s+"
    r"(?:one customer|a single customer|(?:our |the )?largest customer)",
    re.IGNORECASE,
)
# Threshold phrasing → the % is a disclosure floor (e.g. ">10%"), not a real share.
_THRESHOLD_WORDS: Final[tuple[str, ...]] = (
    "more than", "greater than", "at least", "in excess of", "exceeding",
    "exceed", "over", "up to",
)
# "two customers that accounted for more than 10% of our revenue"
_COUNT_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(one|two|three|four|five|\d+)\s+customers?\s+(?:that\s+)?accounted\s+for"
    r"[^.]{0,30}?10\s?%",
    re.IGNORECASE,
)
_WORD_NUM: Final[dict[str, int]] = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def _parse_customer_concentration(text: str) -> CustomerConcentration | None:
    """Extract largest-customer % and/or the count of >10% customers."""
    largest: float | None = None
    for m in _SINGLE_CUSTOMER_PCT_RE.finditer(text):
        # Skip disclosure thresholds ("one customer ... more than 10%").
        if any(th in m.group(0).lower() for th in _THRESHOLD_WORDS):
            continue
        raw = m.group(1) or m.group(2)
        try:
            pct = float(raw)
        except (TypeError, ValueError):
            continue
        if 0 < pct < 100 and (largest is None or pct > largest):
            largest = pct

    count: int | None = None
    summary: str | None = None
    cm = _COUNT_RE.search(text)
    if cm:
        token = cm.group(1).lower()
        count = _WORD_NUM.get(token, int(token) if token.isdigit() else None)
        summary = re.sub(r"\s+", " ", cm.group(0)).strip()[:160]

    if largest is None and count is None:
        return None
    return CustomerConcentration(
        largest_customer_pct=largest, customers_over_10pct=count, summary=summary
    )
