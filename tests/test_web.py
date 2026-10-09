from datetime import date

from stockpicker.db import Database
from stockpicker.models import (
    DecisionJournalEntry,
    DecisionType,
    PortfolioPosition,
    ThesisStatus,
    WatchlistItem,
    WatchlistState,
)
from stockpicker.web import render_app


def test_render_web_app_sections(tmp_path):
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
    db.upsert_portfolio_position(
        PortfolioPosition(
            ticker="ACME",
            thesis_status=ThesisStatus.ACTIVE,
            target_weight=0.05,
        )
    )
    db.add_decision(
        DecisionJournalEntry(
            ticker="ACME",
            decision_type=DecisionType.BUY,
            decision_date=date(2026, 10, 9),
            rationale="Inside buy zone",
        )
    )

    watchlist = render_app(db, section="watchlist")
    portfolio = render_app(db, section="portfolio")
    decisions = render_app(db, section="decisions")

    assert "StockPicker" in watchlist
    assert "ACME" in watchlist
    assert "Portfolio" in portfolio
    assert "Inside buy zone" in decisions
