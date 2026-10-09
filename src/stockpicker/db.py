from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from stockpicker.models import (
    DecisionJournalEntry,
    DecisionType,
    Filing,
    Holding,
    Manager,
    PortfolioPosition,
    PriceBar,
    SecurityMapping,
    Signal,
    ThesisStatus,
    WatchlistItem,
    WatchlistState,
)

SCHEMA_VERSION = 1


def _adapt_date(value: date) -> str:
    return value.isoformat()


def _adapt_datetime(value: datetime) -> str:
    return value.isoformat()


sqlite3.register_adapter(date, _adapt_date)
sqlite3.register_adapter(datetime, _adapt_datetime)


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS managers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cik TEXT NOT NULL UNIQUE,
                    strategy TEXT NOT NULL,
                    quality_score REAL NOT NULL,
                    concentration_score REAL NOT NULL,
                    turnover_score REAL NOT NULL,
                    typical_holding_period_months INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    notes TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS filings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manager_id INTEGER NOT NULL REFERENCES managers(id),
                    accession_number TEXT NOT NULL UNIQUE,
                    filing_type TEXT NOT NULL,
                    filing_date TEXT NOT NULL,
                    report_period TEXT,
                    document_url TEXT NOT NULL,
                    raw_text TEXT,
                    parsed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filing_id INTEGER NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
                    manager_id INTEGER NOT NULL REFERENCES managers(id),
                    accession_number TEXT NOT NULL,
                    report_period TEXT NOT NULL,
                    issuer_name TEXT NOT NULL,
                    cusip TEXT,
                    ticker TEXT,
                    shares REAL NOT NULL,
                    market_value REAL NOT NULL,
                    put_call TEXT NOT NULL DEFAULT '',
                    portfolio_weight REAL,
                    UNIQUE(filing_id, issuer_name, cusip, put_call)
                );

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manager_id INTEGER NOT NULL REFERENCES managers(id),
                    ticker TEXT NOT NULL,
                    issuer_name TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    report_period TEXT NOT NULL,
                    current_shares REAL NOT NULL,
                    prior_shares REAL NOT NULL,
                    share_change REAL NOT NULL,
                    pct_change REAL,
                    current_weight REAL,
                    prior_weight REAL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(manager_id, ticker, signal_type, report_period)
                );

                CREATE TABLE IF NOT EXISTS prices (
                    ticker TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    PRIMARY KEY(ticker, trade_date)
                );

                CREATE TABLE IF NOT EXISTS beneficial_ownership_filings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manager_id INTEGER NOT NULL REFERENCES managers(id),
                    accession_number TEXT NOT NULL UNIQUE,
                    filing_type TEXT NOT NULL,
                    filing_date TEXT NOT NULL,
                    issuer_name TEXT NOT NULL,
                    ticker TEXT,
                    ownership_pct REAL,
                    shares_owned REAL,
                    price_low REAL,
                    price_high REAL,
                    purpose TEXT,
                    document_url TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS security_mappings (
                    cusip TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    issuer_name TEXT,
                    source TEXT NOT NULL DEFAULT 'manual',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker TEXT PRIMARY KEY,
                    issuer_name TEXT,
                    state TEXT NOT NULL,
                    last_price_status TEXT,
                    opportunity_score REAL,
                    notes TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS portfolio_positions (
                    ticker TEXT PRIMARY KEY,
                    issuer_name TEXT,
                    thesis_status TEXT NOT NULL,
                    target_weight REAL,
                    entry_price REAL,
                    add_below REAL,
                    trim_above REAL,
                    exit_condition TEXT NOT NULL DEFAULT '',
                    thesis TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS decision_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    decision_date TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    price REAL,
                    signal_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                INSERT OR IGNORE INTO schema_meta(version, applied_at)
                VALUES (1, datetime('now'));
                """
            )

    def upsert_manager(self, manager: Manager) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO managers (
                    name, cik, strategy, quality_score, concentration_score, turnover_score,
                    typical_holding_period_months, is_active, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cik) DO UPDATE SET
                    name=excluded.name,
                    strategy=excluded.strategy,
                    quality_score=excluded.quality_score,
                    concentration_score=excluded.concentration_score,
                    turnover_score=excluded.turnover_score,
                    typical_holding_period_months=excluded.typical_holding_period_months,
                    is_active=excluded.is_active,
                    notes=excluded.notes
                """,
                (
                    manager.name,
                    manager.normalized_cik,
                    manager.strategy,
                    manager.quality_score,
                    manager.concentration_score,
                    manager.turnover_score,
                    manager.typical_holding_period_months,
                    int(manager.is_active),
                    manager.notes,
                ),
            )
            row = conn.execute(
                "SELECT id FROM managers WHERE cik = ?", (manager.normalized_cik,)
            ).fetchone()
            return int(row["id"])

    def managers(self, active_only: bool = True) -> list[Manager]:
        query = "SELECT * FROM managers"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY quality_score DESC, name"
        with self.connect() as conn:
            return [self._manager_from_row(row) for row in conn.execute(query)]

    def manager_by_cik(self, cik: str) -> Manager | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM managers WHERE cik = ?", (cik.zfill(10),)).fetchone()
            return self._manager_from_row(row) if row else None

    def upsert_filing(self, filing: Filing) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO filings (
                    manager_id, accession_number, filing_type, filing_date, report_period,
                    document_url, raw_text, parsed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(accession_number) DO UPDATE SET
                    manager_id=excluded.manager_id,
                    filing_type=excluded.filing_type,
                    filing_date=excluded.filing_date,
                    report_period=excluded.report_period,
                    document_url=excluded.document_url,
                    raw_text=excluded.raw_text,
                    parsed_at=excluded.parsed_at
                """,
                (
                    filing.manager_id,
                    filing.accession_number,
                    str(filing.filing_type),
                    filing.filing_date,
                    filing.report_period,
                    filing.document_url,
                    filing.raw_text,
                    filing.parsed_at,
                ),
            )
            row = conn.execute(
                "SELECT id FROM filings WHERE accession_number = ?", (filing.accession_number,)
            ).fetchone()
            return int(row["id"])

    def replace_holdings(self, filing_id: int, holdings: Iterable[Holding]) -> None:
        holdings = list(holdings)
        total_value = sum(item.market_value for item in holdings)
        with self.connect() as conn:
            conn.execute("DELETE FROM holdings WHERE filing_id = ?", (filing_id,))
            conn.executemany(
                """
                INSERT INTO holdings (
                    filing_id, manager_id, accession_number, report_period, issuer_name,
                    cusip, ticker, shares, market_value, put_call, portfolio_weight
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.filing_id,
                        item.manager_id,
                        item.accession_number,
                        item.report_period,
                        item.issuer_name,
                        item.cusip,
                        item.ticker,
                        item.shares,
                        item.market_value,
                        item.put_call or "",
                        item.market_value / total_value if total_value else None,
                    )
                    for item in holdings
                ],
            )

    def holdings_for_manager_period(self, manager_id: int, report_period: date) -> list[Holding]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM holdings
                WHERE manager_id = ? AND report_period = ?
                ORDER BY market_value DESC
                """,
                (manager_id, report_period),
            ).fetchall()
            return [self._holding_from_row(row) for row in rows]

    def periods_for_manager(self, manager_id: int) -> list[date]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT report_period FROM holdings
                WHERE manager_id = ?
                ORDER BY report_period
                """,
                (manager_id,),
            ).fetchall()
            return [date.fromisoformat(row["report_period"]) for row in rows]

    def replace_signals(
        self, manager_id: int, report_period: date, signals: Iterable[Signal]
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM signals WHERE manager_id = ? AND report_period = ?",
                (manager_id, report_period),
            )
            conn.executemany(
                """
                INSERT INTO signals (
                    manager_id, ticker, issuer_name, signal_type, report_period, current_shares,
                    prior_shares, share_change, pct_change, current_weight,
                    prior_weight, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.manager_id,
                        item.ticker,
                        item.issuer_name,
                        item.signal_type,
                        item.report_period,
                        item.current_shares,
                        item.prior_shares,
                        item.share_change,
                        item.pct_change,
                        item.current_weight,
                        item.prior_weight,
                        json.dumps(item.metadata, sort_keys=True),
                    )
                    for item in signals
                ],
            )

    def signals(self, report_period: date | None = None) -> list[Signal]:
        query = "SELECT * FROM signals"
        params: tuple[Any, ...] = ()
        if report_period:
            query += " WHERE report_period = ?"
            params = (report_period,)
        query += " ORDER BY report_period DESC, signal_type, ticker"
        with self.connect() as conn:
            return [self._signal_from_row(row) for row in conn.execute(query, params)]

    def upsert_prices(self, bars: Iterable[PriceBar]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO prices(ticker, trade_date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, trade_date) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume
                """,
                [
                    (
                        bar.ticker.upper(),
                        bar.trade_date,
                        bar.open,
                        bar.high,
                        bar.low,
                        bar.close,
                        bar.volume,
                    )
                    for bar in bars
                ],
            )

    def prices(self, ticker: str, start: date, end: date) -> list[PriceBar]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM prices
                WHERE ticker = ? AND trade_date BETWEEN ? AND ?
                ORDER BY trade_date
                """,
                (ticker.upper(), start, end),
            ).fetchall()
            return [self._price_from_row(row) for row in rows]

    def all_prices_for_tickers(self, tickers: Iterable[str]) -> dict[str, list[PriceBar]]:
        tickers = sorted({ticker.upper() for ticker in tickers})
        if not tickers:
            return {}
        placeholders = ",".join("?" for _ in tickers)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM prices
                WHERE ticker IN ({placeholders})
                ORDER BY ticker, trade_date
                """,
                tickers,
            ).fetchall()
        result: dict[str, list[PriceBar]] = {ticker: [] for ticker in tickers}
        for row in rows:
            bar = self._price_from_row(row)
            result.setdefault(bar.ticker, []).append(bar)
        return result

    def upsert_security_mappings(self, mappings: Iterable[SecurityMapping]) -> int:
        mappings = list(mappings)
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO security_mappings(cusip, ticker, issuer_name, source, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(cusip) DO UPDATE SET
                    ticker=excluded.ticker,
                    issuer_name=COALESCE(excluded.issuer_name, security_mappings.issuer_name),
                    source=excluded.source,
                    updated_at=datetime('now')
                """,
                [
                    (
                        item.cusip.upper(),
                        item.ticker.upper(),
                        item.issuer_name,
                        item.source,
                    )
                    for item in mappings
                ],
            )
        return len(mappings)

    def security_mapping_by_cusip(self) -> dict[str, SecurityMapping]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM security_mappings").fetchall()
            return {
                row["cusip"]: SecurityMapping(
                    cusip=row["cusip"],
                    ticker=row["ticker"],
                    issuer_name=row["issuer_name"],
                    source=row["source"],
                )
                for row in rows
            }

    def apply_security_mappings(self) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE holdings
                SET ticker = (
                    SELECT security_mappings.ticker
                    FROM security_mappings
                    WHERE security_mappings.cusip = holdings.cusip
                )
                WHERE (ticker IS NULL OR ticker = '')
                  AND cusip IN (SELECT cusip FROM security_mappings)
                """
            )
            return cursor.rowcount

    def unmapped_holdings(self, limit: int = 100) -> list[Holding]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM holdings
                WHERE ticker IS NULL OR ticker = ''
                ORDER BY market_value DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._holding_from_row(row) for row in rows]

    def upsert_watchlist_item(self, item: WatchlistItem) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist(
                    ticker, issuer_name, state, last_price_status, opportunity_score,
                    notes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(ticker) DO UPDATE SET
                    issuer_name=COALESCE(excluded.issuer_name, watchlist.issuer_name),
                    state=excluded.state,
                    last_price_status=excluded.last_price_status,
                    opportunity_score=excluded.opportunity_score,
                    notes=excluded.notes,
                    updated_at=datetime('now')
                """,
                (
                    item.ticker.upper(),
                    item.issuer_name,
                    item.state,
                    item.last_price_status,
                    item.opportunity_score,
                    item.notes,
                ),
            )

    def watchlist(self) -> list[WatchlistItem]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlist ORDER BY opportunity_score DESC"
            ).fetchall()
            return [self._watchlist_from_row(row) for row in rows]

    def watchlist_by_ticker(self) -> dict[str, WatchlistItem]:
        return {item.ticker: item for item in self.watchlist()}

    def upsert_portfolio_position(self, position: PortfolioPosition) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_positions(
                    ticker, issuer_name, thesis_status, target_weight, entry_price,
                    add_below, trim_above, exit_condition, thesis, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(ticker) DO UPDATE SET
                    issuer_name=COALESCE(excluded.issuer_name, portfolio_positions.issuer_name),
                    thesis_status=excluded.thesis_status,
                    target_weight=excluded.target_weight,
                    entry_price=excluded.entry_price,
                    add_below=excluded.add_below,
                    trim_above=excluded.trim_above,
                    exit_condition=excluded.exit_condition,
                    thesis=excluded.thesis,
                    updated_at=datetime('now')
                """,
                (
                    position.ticker.upper(),
                    position.issuer_name,
                    position.thesis_status,
                    position.target_weight,
                    position.entry_price,
                    position.add_below,
                    position.trim_above,
                    position.exit_condition,
                    position.thesis,
                ),
            )

    def portfolio_positions(self) -> list[PortfolioPosition]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM portfolio_positions ORDER BY ticker"
            ).fetchall()
            return [self._portfolio_position_from_row(row) for row in rows]

    def add_decision(self, decision: DecisionJournalEntry) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO decision_journal(
                    ticker, decision_type, decision_date, rationale, price, signal_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    decision.ticker.upper(),
                    decision.decision_type,
                    decision.decision_date,
                    decision.rationale,
                    decision.price,
                    decision.signal_id,
                ),
            )
            return int(cursor.lastrowid)

    def decisions(self, ticker: str | None = None) -> list[DecisionJournalEntry]:
        query = "SELECT * FROM decision_journal"
        params: tuple[Any, ...] = ()
        if ticker:
            query += " WHERE ticker = ?"
            params = (ticker.upper(),)
        query += " ORDER BY decision_date DESC, id DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._decision_from_row(row) for row in rows]

    @staticmethod
    def _manager_from_row(row: sqlite3.Row) -> Manager:
        return Manager(
            id=row["id"],
            name=row["name"],
            cik=row["cik"],
            strategy=row["strategy"],
            quality_score=row["quality_score"],
            concentration_score=row["concentration_score"],
            turnover_score=row["turnover_score"],
            typical_holding_period_months=row["typical_holding_period_months"],
            is_active=bool(row["is_active"]),
            notes=row["notes"],
        )

    @staticmethod
    def _holding_from_row(row: sqlite3.Row) -> Holding:
        return Holding(
            id=row["id"],
            filing_id=row["filing_id"],
            manager_id=row["manager_id"],
            accession_number=row["accession_number"],
            report_period=date.fromisoformat(row["report_period"]),
            issuer_name=row["issuer_name"],
            cusip=row["cusip"],
            ticker=row["ticker"],
            shares=row["shares"],
            market_value=row["market_value"],
            put_call=row["put_call"] or None,
            portfolio_weight=row["portfolio_weight"],
        )

    @staticmethod
    def _signal_from_row(row: sqlite3.Row) -> Signal:
        return Signal(
            id=row["id"],
            manager_id=row["manager_id"],
            ticker=row["ticker"],
            issuer_name=row["issuer_name"],
            signal_type=row["signal_type"],
            report_period=date.fromisoformat(row["report_period"]),
            current_shares=row["current_shares"],
            prior_shares=row["prior_shares"],
            share_change=row["share_change"],
            pct_change=row["pct_change"],
            current_weight=row["current_weight"],
            prior_weight=row["prior_weight"],
            metadata=json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _price_from_row(row: sqlite3.Row) -> PriceBar:
        return PriceBar(
            ticker=row["ticker"],
            trade_date=date.fromisoformat(row["trade_date"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )

    @staticmethod
    def _watchlist_from_row(row: sqlite3.Row) -> WatchlistItem:
        return WatchlistItem(
            ticker=row["ticker"],
            issuer_name=row["issuer_name"],
            state=WatchlistState(row["state"]),
            last_price_status=(
                WatchlistState(row["last_price_status"]) if row["last_price_status"] else None
            ),
            opportunity_score=row["opportunity_score"],
            notes=row["notes"],
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    @staticmethod
    def _portfolio_position_from_row(row: sqlite3.Row) -> PortfolioPosition:
        return PortfolioPosition(
            ticker=row["ticker"],
            issuer_name=row["issuer_name"],
            thesis_status=ThesisStatus(row["thesis_status"]),
            target_weight=row["target_weight"],
            entry_price=row["entry_price"],
            add_below=row["add_below"],
            trim_above=row["trim_above"],
            exit_condition=row["exit_condition"],
            thesis=row["thesis"],
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    @staticmethod
    def _decision_from_row(row: sqlite3.Row) -> DecisionJournalEntry:
        return DecisionJournalEntry(
            id=row["id"],
            ticker=row["ticker"],
            decision_type=DecisionType(row["decision_type"]),
            decision_date=date.fromisoformat(row["decision_date"]),
            rationale=row["rationale"],
            price=row["price"],
            signal_id=row["signal_id"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )
