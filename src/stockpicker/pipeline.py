from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from stockpicker.beneficial import beneficial_filing_to_signal, parse_beneficial_ownership_filing
from stockpicker.db import Database
from stockpicker.models import Filing, FilingType, Manager, Signal
from stockpicker.prices import estimate_cost_basis, fetch_price_bars, quarter_window
from stockpicker.sec import SecClient, load_ticker_map, parse_13f_information_table
from stockpicker.signals import (
    detect_multi_quarter_accumulation,
    detect_multi_quarter_distribution,
    generate_position_signals,
)

TRACKED_13F_FORMS = {FilingType.FORM_13F.value, FilingType.FORM_13F_AMENDMENT.value}
TRACKED_BENEFICIAL_FORMS = {
    FilingType.SCHEDULE_13D.value,
    FilingType.SCHEDULE_13D_AMENDMENT.value,
    FilingType.SCHEDULE_13G.value,
    FilingType.SCHEDULE_13G_AMENDMENT.value,
}


@dataclass(frozen=True)
class IngestResult:
    manager: Manager
    filing_count: int
    holding_count: int


@dataclass(frozen=True)
class BeneficialIngestResult:
    manager: Manager
    filing_count: int
    signal_count: int


@dataclass(frozen=True)
class FilingSeasonResult:
    ingested: list[IngestResult] = field(default_factory=list)
    signal_count: int = 0
    mapping_updates: int = 0
    manager_errors: dict[str, str] = field(default_factory=dict)


def ingest_13f_filings(
    *,
    db: Database,
    manager: Manager,
    sec_client: SecClient,
    limit: int = 4,
    ticker_map_path: str | None = None,
) -> IngestResult:
    if manager.id is None:
        raise ValueError("Manager must be saved before ingesting filings.")

    ticker_map = load_ticker_map(ticker_map_path)
    filings = sec_client.recent_filings(manager.cik, forms=TRACKED_13F_FORMS, limit=limit)
    holding_count = 0
    for item in filings:
        raw_text = sec_client.download_text(item["document_url"])
        filing = Filing(
            manager_id=manager.id,
            accession_number=item["accession_number"],
            filing_type=item["filing_type"],
            filing_date=item["filing_date"],
            report_period=item["report_period"],
            document_url=item["document_url"],
            raw_text=raw_text,
            parsed_at=datetime.now(UTC),
        )
        filing_id = db.upsert_filing(filing)
        if filing.report_period is None:
            continue
        holdings = parse_13f_information_table(
            raw_text,
            filing_id=filing_id,
            manager_id=manager.id,
            accession_number=filing.accession_number,
            report_period=filing.report_period,
            ticker_map=ticker_map,
        )
        db.replace_holdings(filing_id, holdings)
        holding_count += len(holdings)

    return IngestResult(manager=manager, filing_count=len(filings), holding_count=holding_count)


def ingest_beneficial_ownership_filings(
    *,
    db: Database,
    manager: Manager,
    sec_client: SecClient,
    limit: int = 20,
) -> BeneficialIngestResult:
    if manager.id is None:
        raise ValueError("Manager must be saved before ingesting filings.")

    filings = sec_client.recent_filings(
        manager.cik,
        forms=TRACKED_BENEFICIAL_FORMS,
        limit=limit,
    )
    signals = []
    for item in filings:
        raw_text = sec_client.download_text(item["document_url"])
        filing = parse_beneficial_ownership_filing(
            raw_text,
            manager_id=manager.id,
            accession_number=item["accession_number"],
            filing_type=item["filing_type"],
            filing_date=item["filing_date"],
            document_url=item["document_url"],
        )
        db.upsert_beneficial_ownership_filing(filing)
        signals.append(beneficial_filing_to_signal(filing))
    signal_count = db.add_signals(signals)
    return BeneficialIngestResult(
        manager=manager,
        filing_count=len(filings),
        signal_count=signal_count,
    )


def run_filing_season(
    *,
    db: Database,
    managers: list[Manager],
    sec_client: SecClient | None = None,
    limit: int = 4,
    ticker_map_path: str | None = None,
    ingest: bool = True,
) -> FilingSeasonResult:
    results: list[IngestResult] = []
    errors: dict[str, str] = {}
    signal_count = 0

    for manager in managers:
        try:
            if ingest:
                if sec_client is None:
                    raise ValueError("SEC client is required when ingestion is enabled.")
                results.append(
                    ingest_13f_filings(
                        db=db,
                        manager=manager,
                        sec_client=sec_client,
                        limit=limit,
                        ticker_map_path=ticker_map_path,
                    )
                )
            signal_count += len(generate_manager_signals(db, manager))
        except Exception as exc:  # noqa: BLE001
            errors[manager.name] = str(exc)

    mapping_updates = db.apply_security_mappings()
    return FilingSeasonResult(
        ingested=results,
        signal_count=signal_count,
        mapping_updates=mapping_updates,
        manager_errors=errors,
    )


def generate_manager_signals(db: Database, manager: Manager) -> list[Signal]:
    if manager.id is None:
        raise ValueError("Manager must be saved before generating signals.")

    periods = db.periods_for_manager(manager.id)
    if len(periods) < 2:
        return []

    generated: list[Signal] = []
    signals_by_period: dict[date, list[Signal]] = {}
    for prior_period, current_period in zip(periods, periods[1:], strict=False):
        prior = db.holdings_for_manager_period(manager.id, prior_period)
        current = db.holdings_for_manager_period(manager.id, current_period)
        signals = generate_position_signals(
            manager_id=manager.id,
            report_period=current_period,
            current_holdings=current,
            prior_holdings=prior,
        )
        db.replace_signals(manager.id, current_period, signals)
        signals_by_period[current_period] = signals
        generated.extend(signals)
    multi_period = [
        *detect_multi_quarter_accumulation(signals_by_period),
        *detect_multi_quarter_distribution(signals_by_period),
    ]
    db.add_signals(multi_period)
    generated.extend(multi_period)
    return generated


def build_cost_estimates_for_signals(
    *,
    db: Database,
    signals: list[Signal],
    refresh_prices: bool = False,
) -> list:
    estimates = []
    for signal in signals:
        start, end = quarter_window(signal.report_period)
        bars = db.prices(signal.ticker, start, end)
        if refresh_prices and not bars:
            bars = fetch_price_bars(signal.ticker, start, date.today())
            db.upsert_prices(bars)
            bars = [bar for bar in bars if start <= bar.trade_date <= end]
        latest_bars = db.prices(signal.ticker, start, date.today())
        current_price = latest_bars[-1].close if latest_bars else None
        estimate = estimate_cost_basis(
            ticker=signal.ticker,
            manager_id=signal.manager_id,
            report_period=signal.report_period,
            quarter_bars=bars,
            current_price=current_price,
        )
        if estimate:
            estimates.append(estimate)
    return estimates
