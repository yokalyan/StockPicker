from datetime import date

from stockpicker.fundamentals import merge_fundamentals, sec_snapshot_from_company_facts
from stockpicker.models import FundamentalSnapshot


def test_sec_snapshot_from_company_facts_extracts_latest_us_gaap_values():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"end": "2025-12-31", "val": 900},
                            {"end": "2026-12-31", "val": 1000},
                        ]
                    }
                },
                "NetIncomeLoss": {"units": {"USD": [{"end": "2026-12-31", "val": 125}]}},
                "LongTermDebt": {"units": {"USD": [{"end": "2026-12-31", "val": 300}]}},
            }
        }
    }

    snapshot = sec_snapshot_from_company_facts(ticker="acme", facts=facts)

    assert snapshot.ticker == "ACME"
    assert snapshot.revenue == 1000
    assert snapshot.net_income == 125
    assert snapshot.debt == 300
    assert snapshot.source == "sec_companyfacts"


def test_merge_fundamentals_preserves_primary_and_fills_missing_fields():
    primary = FundamentalSnapshot(
        ticker="ACME",
        as_of=date(2026, 10, 9),
        market_cap=1_000_000,
        revenue=None,
        source="yfinance",
    )
    secondary = FundamentalSnapshot(
        ticker="ACME",
        as_of=date(2026, 10, 8),
        market_cap=2_000_000,
        revenue=500_000,
        net_income=50_000,
        source="sec_companyfacts",
    )

    merged = merge_fundamentals(primary, secondary)

    assert merged.market_cap == 1_000_000
    assert merged.revenue == 500_000
    assert merged.net_income == 50_000
    assert merged.as_of == date(2026, 10, 9)
    assert merged.source == "yfinance+sec_companyfacts"
