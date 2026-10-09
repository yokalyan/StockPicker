from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from stockpicker.models import BeneficialOwnershipFiling, FilingType, Signal, SignalType

PRICE_PATTERN = re.compile(r"\$\s*(\d+(?:\.\d+)?)")
PCT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
SHARES_PATTERN = re.compile(r"([\d,]+)\s+(?:shares|share)", re.I)
ISSUER_STOP = r"(?= Trading Symbol| Ticker Symbol| Symbol| The Reporting| Item \d|$)"


def parse_beneficial_ownership_filing(
    raw_text: str,
    *,
    manager_id: int,
    accession_number: str,
    filing_type: FilingType | str,
    filing_date: date,
    document_url: str,
    ticker: str | None = None,
) -> BeneficialOwnershipFiling:
    text = _clean_text(raw_text)
    issuer_name = _extract_issuer_name(text)
    ticker = ticker or _extract_ticker(text)
    ownership_pct = _extract_ownership_pct(text)
    shares_owned = _extract_shares_owned(text)
    price_low, price_high = _extract_price_range(text)
    purpose = _extract_purpose(text)
    return BeneficialOwnershipFiling(
        manager_id=manager_id,
        accession_number=accession_number,
        filing_type=filing_type,
        filing_date=filing_date,
        issuer_name=issuer_name,
        ticker=ticker,
        ownership_pct=ownership_pct,
        shares_owned=shares_owned,
        price_low=price_low,
        price_high=price_high,
        purpose=purpose,
        document_url=document_url,
    )


def beneficial_filing_to_signal(
    filing: BeneficialOwnershipFiling, report_period: date | None = None
) -> Signal:
    is_activist = str(filing.filing_type).upper().endswith("13D") or "13D" in str(
        filing.filing_type
    )
    return Signal(
        manager_id=filing.manager_id,
        ticker=(filing.ticker or filing.issuer_name).upper(),
        issuer_name=filing.issuer_name,
        signal_type=SignalType.ACTIVIST if is_activist else SignalType.BENEFICIAL_OWNER,
        report_period=report_period or filing.filing_date,
        current_shares=filing.shares_owned or 0.0,
        prior_shares=0.0,
        share_change=filing.shares_owned or 0.0,
        pct_change=None,
        current_weight=None,
        prior_weight=None,
        metadata={
            "ownership_pct": filing.ownership_pct,
            "price_low": filing.price_low,
            "price_high": filing.price_high,
            "purpose": filing.purpose,
            "accession_number": filing.accession_number,
        },
    )


def _clean_text(raw_text: str) -> str:
    soup = BeautifulSoup(raw_text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True) or raw_text)


def _extract_issuer_name(text: str) -> str:
    candidates = [
        rf"Name of Issuer\)?\s*:?\s*([A-Z][A-Za-z0-9 .,&'-]+?){ISSUER_STOP}",
        rf"Item 1\.\s*Security and Issuer\s+([A-Z][A-Za-z0-9 .,&'-]+?){ISSUER_STOP}",
    ]
    for pattern in candidates:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip(" .")
    return "Unknown Issuer"


def _extract_ticker(text: str) -> str | None:
    candidates = [
        r"(?:Trading Symbol|Ticker Symbol|Symbol)\s*:?\s*([A-Z][A-Z0-9.\-]{0,9})",
        r"\(Ticker\s*:?\s*([A-Z][A-Z0-9.\-]{0,9})\)",
    ]
    for pattern in candidates:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).upper()
    return None


def _extract_ownership_pct(text: str) -> float | None:
    focused = re.search(
        r"(?:percent of class|percentage of class|beneficially owns).*?(\d+(?:\.\d+)?)\s*%",
        text,
        flags=re.I,
    )
    if focused:
        return float(focused.group(1))
    match = PCT_PATTERN.search(text)
    return float(match.group(1)) if match else None


def _extract_shares_owned(text: str) -> float | None:
    focused = re.search(
        r"(?:beneficially owns|aggregate amount).*?([\d,]+)\s+(?:shares|share)",
        text,
        flags=re.I,
    )
    if focused:
        return float(focused.group(1).replace(",", ""))
    match = SHARES_PATTERN.search(text)
    return float(match.group(1).replace(",", "")) if match else None


def _extract_price_range(text: str) -> tuple[float | None, float | None]:
    prices = [float(match.group(1)) for match in PRICE_PATTERN.finditer(text)]
    if not prices:
        return None, None
    return min(prices), max(prices)


def _extract_purpose(text: str) -> str | None:
    match = re.search(r"Item 4\.\s*Purpose of Transaction\s+(.*?)(?:Item 5\.|Item 6\.)", text, re.I)
    if not match:
        return None
    purpose = match.group(1).strip()
    return purpose[:1000]
