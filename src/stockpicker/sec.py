from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from stockpicker.models import Holding

SEC_BASE = "https://www.sec.gov"
SUBMISSIONS_URL = SEC_BASE + "/Archives/edgar/data/{cik}/{accession_no_dashes}/{primary_doc}"


class SecClient:
    def __init__(self, user_agent: str, timeout: float = 30.0):
        if "@" not in user_agent:
            raise ValueError("SEC requests require a descriptive user agent with contact email.")
        self.client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            timeout=timeout,
            follow_redirects=True,
        )

    def submissions(self, cik: str) -> dict:
        padded = cik.zfill(10)
        response = self.client.get(f"{SEC_BASE}/submissions/CIK{padded}.json")
        response.raise_for_status()
        return response.json()

    def recent_filings(
        self, cik: str, forms: set[str] | None = None, limit: int = 40
    ) -> list[dict]:
        data = self.submissions(cik)
        recent = data["filings"]["recent"]
        filings = []
        for index, accession in enumerate(recent["accessionNumber"]):
            form = recent["form"][index]
            if forms and form not in forms:
                continue
            filings.append(
                {
                    "accession_number": accession,
                    "filing_type": form,
                    "filing_date": date.fromisoformat(recent["filingDate"][index]),
                    "report_period": _optional_date(recent["reportDate"][index]),
                    "primary_doc": recent["primaryDocument"][index],
                    "document_url": SUBMISSIONS_URL.format(
                        cik=str(int(cik)),
                        accession_no_dashes=accession.replace("-", ""),
                        primary_doc=recent["primaryDocument"][index],
                    ),
                }
            )
            if len(filings) >= limit:
                break
        return filings

    def download_text(self, url: str) -> str:
        response = self.client.get(url)
        response.raise_for_status()
        return response.text


def _optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def parse_13f_information_table(
    raw_text: str,
    *,
    filing_id: int,
    manager_id: int,
    accession_number: str,
    report_period: date,
    ticker_map: dict[str, str] | None = None,
) -> list[Holding]:
    """Parse the information table from a 13F filing.

    SEC filings can embed the table as XML or HTML. We prefer XML, then fall back
    to table-shaped HTML. 13F values are reported in thousands of dollars, so the
    stored market value is normalized to dollars.
    """

    ticker_map = ticker_map or {}
    xml_blob = _extract_information_table_xml(raw_text)
    if xml_blob:
        return _parse_13f_xml(
            xml_blob,
            filing_id=filing_id,
            manager_id=manager_id,
            accession_number=accession_number,
            report_period=report_period,
            ticker_map=ticker_map,
        )
    return _parse_13f_html(
        raw_text,
        filing_id=filing_id,
        manager_id=manager_id,
        accession_number=accession_number,
        report_period=report_period,
        ticker_map=ticker_map,
    )


def _extract_information_table_xml(raw_text: str) -> str | None:
    documents = re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", raw_text, flags=re.I | re.S)
    for doc in documents:
        type_match = re.search(r"<TYPE>\s*([^\n<]+)", doc, flags=re.I)
        doc_type = type_match.group(1).strip().lower() if type_match else ""
        if "infotable" not in doc_type and "information table" not in doc_type:
            continue
        text_match = re.search(r"<TEXT>(.*?)</TEXT>", doc, flags=re.I | re.S)
        if text_match:
            return text_match.group(1).strip()
    if "<informationTable" in raw_text or "<ns1:informationTable" in raw_text:
        start = raw_text.find("<?xml")
        return raw_text[start:] if start >= 0 else raw_text
    return None


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1].lower()


def _child_text(element: ElementTree.Element, name: str) -> str:
    for child in element.iter():
        if _strip_namespace(child.tag) == name.lower() and child.text:
            return child.text.strip()
    return ""


def _parse_13f_xml(
    xml_blob: str,
    *,
    filing_id: int,
    manager_id: int,
    accession_number: str,
    report_period: date,
    ticker_map: dict[str, str],
) -> list[Holding]:
    root = ElementTree.fromstring(xml_blob.encode())
    holdings: list[Holding] = []
    for info_table in root.iter():
        if _strip_namespace(info_table.tag) != "infotable":
            continue
        issuer_name = _child_text(info_table, "nameofissuer")
        cusip = _child_text(info_table, "cusip")
        value = float(_child_text(info_table, "value") or 0) * 1000
        shares = float(_child_text(info_table, "sshprnamt") or 0)
        put_call = _child_text(info_table, "putcall") or None
        holdings.append(
            Holding(
                filing_id=filing_id,
                manager_id=manager_id,
                accession_number=accession_number,
                report_period=report_period,
                issuer_name=issuer_name,
                cusip=cusip,
                ticker=ticker_map.get(cusip),
                shares=shares,
                market_value=value,
                put_call=put_call,
            )
        )
    return holdings


def _parse_13f_html(
    raw_text: str,
    *,
    filing_id: int,
    manager_id: int,
    accession_number: str,
    report_period: date,
    ticker_map: dict[str, str],
) -> list[Holding]:
    soup = BeautifulSoup(raw_text, "html.parser")
    holdings: list[Holding] = []
    for row in soup.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if len(cells) < 5 or not re.fullmatch(r"[0-9A-Z]{9}", cells[2] if len(cells) > 2 else ""):
            continue
        issuer_name = cells[0]
        cusip = cells[2]
        value = _floatish(cells[3]) * 1000
        shares = _floatish(cells[4])
        holdings.append(
            Holding(
                filing_id=filing_id,
                manager_id=manager_id,
                accession_number=accession_number,
                report_period=report_period,
                issuer_name=issuer_name,
                cusip=cusip,
                ticker=ticker_map.get(cusip),
                shares=shares,
                market_value=value,
            )
        )
    return holdings


def _floatish(value: str) -> float:
    cleaned = value.replace(",", "").replace("$", "").strip()
    return float(cleaned) if cleaned else 0.0


def accession_to_archive_url(cik: str, accession_number: str, primary_doc: str) -> str:
    return SUBMISSIONS_URL.format(
        cik=str(int(cik)),
        accession_no_dashes=accession_number.replace("-", ""),
        primary_doc=primary_doc,
    )


def load_ticker_map(path: str | Path | None) -> dict[str, str]:
    if not path:
        return {}
    result: dict[str, str] = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cusip, ticker = [part.strip() for part in line.split(",", 1)]
        result[cusip.upper()] = ticker.upper()
    return result
