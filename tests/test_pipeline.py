from datetime import date

from stockpicker.db import Database
from stockpicker.models import Filing, Holding, Manager, StrategyType
from stockpicker.pipeline import ingest_beneficial_ownership_filings, run_filing_season


class FakeSecClient:
    def recent_filings(self, cik, forms=None, limit=20):
        return [
            {
                "accession_number": "beneficial",
                "filing_type": "SC 13D",
                "filing_date": date(2026, 10, 9),
                "report_period": None,
                "document_url": "https://example.com/beneficial",
            }
        ][:limit]

    def download_text(self, url):
        return """
        Item 1. Security and Issuer Acme Corp Trading Symbol: ACME
        The Reporting Person beneficially owns 1,250,000 shares, representing 7.4%
        of the outstanding common stock. Purchases were made from $14.20 to $15.80.
        Item 4. Purpose of Transaction Strategic alternatives. Item 5.
        """


def test_run_filing_season_generates_signals_without_ingest(tmp_path):
    db = Database(tmp_path / "stockpicker.sqlite")
    db.init()
    manager_id = db.upsert_manager(
        Manager(name="Patient Capital", cik="12345", strategy=StrategyType.SMALL_MID_VALUE)
    )
    manager = db.manager_by_cik("12345")
    assert manager is not None
    first_filing = db.upsert_filing(
        Filing(
            manager_id=manager_id,
            accession_number="first",
            filing_type="13F-HR",
            filing_date=date(2026, 5, 15),
            report_period=date(2026, 3, 31),
            document_url="https://example.com/first",
        )
    )
    second_filing = db.upsert_filing(
        Filing(
            manager_id=manager_id,
            accession_number="second",
            filing_type="13F-HR",
            filing_date=date(2026, 8, 14),
            report_period=date(2026, 6, 30),
            document_url="https://example.com/second",
        )
    )
    db.replace_holdings(
        first_filing,
        [
            Holding(
                filing_id=first_filing,
                manager_id=manager_id,
                accession_number="first",
                report_period=date(2026, 3, 31),
                issuer_name="ACME CORP",
                cusip="000000001",
                ticker="ACME",
                shares=100,
                market_value=1000,
            )
        ],
    )
    db.replace_holdings(
        second_filing,
        [
            Holding(
                filing_id=second_filing,
                manager_id=manager_id,
                accession_number="second",
                report_period=date(2026, 6, 30),
                issuer_name="ACME CORP",
                cusip="000000001",
                ticker="ACME",
                shares=200,
                market_value=2000,
            )
        ],
    )

    result = run_filing_season(db=db, managers=[manager], ingest=False)

    assert result.signal_count == 1
    assert result.manager_errors == {}


def test_ingest_beneficial_ownership_filings_creates_filing_and_signal(tmp_path):
    db = Database(tmp_path / "stockpicker.sqlite")
    db.init()
    db.upsert_manager(Manager(name="Patient Capital", cik="12345"))
    manager = db.manager_by_cik("12345")
    assert manager is not None

    result = ingest_beneficial_ownership_filings(
        db=db,
        manager=manager,
        sec_client=FakeSecClient(),
    )

    assert result.filing_count == 1
    assert result.signal_count == 1
    assert db.beneficial_ownership_filings("ACME")[0].ownership_pct == 7.4
    assert db.signals()[0].ticker == "ACME"
