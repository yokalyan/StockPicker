from datetime import date
from pathlib import Path

from stockpicker.sec import parse_13f_information_table


def test_parse_13f_xml_fixture():
    fixture = Path("tests/fixtures/sample_13f.xml").read_text()
    raw = """
<DOCUMENT>
<TYPE>INFORMATION TABLE
<TEXT>
""" + fixture + """
</TEXT>
</DOCUMENT>
"""

    holdings = parse_13f_information_table(
        raw,
        filing_id=1,
        manager_id=7,
        accession_number="0000000000-26-000001",
        report_period=date(2026, 6, 30),
        ticker_map={"000000001": "ACME", "000000002": "BRVO"},
    )

    assert len(holdings) == 2
    assert holdings[0].issuer_name == "ACME CORP"
    assert holdings[0].ticker == "ACME"
    assert holdings[0].market_value == 12_500_000
    assert holdings[0].shares == 250_000
