from datetime import date

from stockpicker.db import Database
from stockpicker.models import (
    DecisionJournalEntry,
    DecisionType,
    Filing,
    Holding,
    Manager,
    PortfolioPosition,
    PriceBar,
    SecurityMapping,
    StrategyType,
    ThesisStatus,
    WatchlistItem,
    WatchlistState,
)


def test_database_initializes_and_upserts_manager(tmp_path):
    db = Database(tmp_path / "stockpicker.sqlite")
    db.init()

    manager_id = db.upsert_manager(
        Manager(
            name="Patient Capital",
            cik="12345",
            strategy=StrategyType.SMALL_MID_VALUE,
            quality_score=8.5,
        )
    )

    assert manager_id > 0
    managers = db.managers()
    assert managers[0].name == "Patient Capital"
    assert managers[0].cik == "0000012345"


def test_database_applies_security_mappings(tmp_path):
    db = Database(tmp_path / "stockpicker.sqlite")
    db.init()
    manager_id = db.upsert_manager(Manager(name="Patient Capital", cik="12345"))
    filing_id = db.upsert_filing(
        filing=Filing(
            manager_id=manager_id,
            accession_number="0000000000-26-000001",
            filing_type="13F-HR",
            filing_date=date(2026, 8, 14),
            report_period=date(2026, 6, 30),
            document_url="https://example.com",
        )
    )
    db.replace_holdings(
        filing_id,
        [
            Holding(
                filing_id=filing_id,
                manager_id=manager_id,
                accession_number="0000000000-26-000001",
                report_period=date(2026, 6, 30),
                issuer_name="ACME CORP",
                cusip="000000001",
                shares=100,
                market_value=1000,
            )
        ],
    )

    db.upsert_security_mappings([SecurityMapping(cusip="000000001", ticker="ACME")])
    assert db.apply_security_mappings() == 1
    holdings = db.holdings_for_manager_period(manager_id, date(2026, 6, 30))
    assert holdings[0].ticker == "ACME"


def test_database_loads_all_prices_for_tickers(tmp_path):
    db = Database(tmp_path / "stockpicker.sqlite")
    db.init()
    db.upsert_prices(
        [
            PriceBar(
                ticker="ACME",
                trade_date=date(2026, 1, 2),
                open=10,
                high=10,
                low=10,
                close=10,
                volume=100,
            )
        ]
    )

    prices = db.all_prices_for_tickers(["ACME", "MISSING"])

    assert len(prices["ACME"]) == 1
    assert prices["MISSING"] == []


def test_database_persists_watchlist_items(tmp_path):
    db = Database(tmp_path / "stockpicker.sqlite")
    db.init()
    db.upsert_watchlist_item(
        WatchlistItem(
            ticker="ACME",
            issuer_name="Acme Corp",
            state=WatchlistState.NEEDS_UNDERWRITING,
            last_price_status=WatchlistState.INSIDE_BUY_ZONE,
            opportunity_score=42,
        )
    )

    watchlist = db.watchlist()

    assert watchlist[0].ticker == "ACME"
    assert watchlist[0].last_price_status == WatchlistState.INSIDE_BUY_ZONE


def test_database_persists_portfolio_and_decisions(tmp_path):
    db = Database(tmp_path / "stockpicker.sqlite")
    db.init()
    db.upsert_portfolio_position(
        PortfolioPosition(
            ticker="ACME",
            issuer_name="Acme Corp",
            thesis_status=ThesisStatus.ACTIVE,
            target_weight=0.05,
            entry_price=12.5,
            add_below=10,
            trim_above=20,
            exit_condition="Thesis breaks",
            thesis="Mispriced small-cap compounder",
        )
    )
    decision_id = db.add_decision(
        DecisionJournalEntry(
            ticker="ACME",
            decision_type=DecisionType.BUY,
            decision_date=date(2026, 10, 9),
            rationale="Inside buy zone and thesis validated",
            price=12.5,
        )
    )

    positions = db.portfolio_positions()
    decisions = db.decisions("ACME")

    assert decision_id > 0
    assert positions[0].thesis_status == ThesisStatus.ACTIVE
    assert decisions[0].decision_type == DecisionType.BUY
