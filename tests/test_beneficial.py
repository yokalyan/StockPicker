from datetime import date

from stockpicker.beneficial import beneficial_filing_to_signal, parse_beneficial_ownership_filing
from stockpicker.models import FilingType, SignalType


def test_parse_beneficial_ownership_extracts_key_fields():
    raw = """
    Item 1. Security and Issuer Acme Corp
    The Reporting Person beneficially owns 1,250,000 shares, representing 7.4%
    of the outstanding common stock. Purchases were made at prices ranging
    from $14.20 to $15.80 per share.
    Item 4. Purpose of Transaction The Reporting Person intends to discuss
    strategic alternatives with the board. Item 5. Interest in Securities
    """

    filing = parse_beneficial_ownership_filing(
        raw,
        manager_id=3,
        accession_number="0000000000-26-000002",
        filing_type=FilingType.SCHEDULE_13D,
        filing_date=date(2026, 10, 1),
        document_url="https://example.com/filing",
        ticker="ACME",
    )

    assert filing.issuer_name == "Acme Corp"
    assert filing.ownership_pct == 7.4
    assert filing.shares_owned == 1_250_000
    assert filing.price_low == 14.20
    assert filing.price_high == 15.80
    assert filing.purpose is not None


def test_beneficial_filing_to_signal_classifies_13d_as_activist():
    filing = parse_beneficial_ownership_filing(
        "Name of Issuer: Acme Corp beneficially owns 100,000 shares 5.2%",
        manager_id=3,
        accession_number="x",
        filing_type=FilingType.SCHEDULE_13D,
        filing_date=date(2026, 10, 1),
        document_url="https://example.com/filing",
        ticker="ACME",
    )

    signal = beneficial_filing_to_signal(filing)

    assert signal.signal_type == SignalType.ACTIVIST
    assert signal.metadata["ownership_pct"] == 5.2
