from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from stockpicker.alerts import alerts_from_opportunities, watchlist_items_from_opportunities
from stockpicker.backtest import build_backtest_observations, summarize_observations
from stockpicker.dashboard import render_dashboard
from stockpicker.db import Database
from stockpicker.manager_universe import load_manager_universe_csv
from stockpicker.models import (
    DecisionJournalEntry,
    DecisionType,
    Manager,
    PortfolioPosition,
    StrategyType,
    ThesisStatus,
)
from stockpicker.opportunities import rank_opportunities
from stockpicker.pipeline import (
    build_cost_estimates_for_signals,
    generate_manager_signals,
    ingest_13f_filings,
    ingest_beneficial_ownership_filings,
    run_filing_season,
)
from stockpicker.research import render_research_packet
from stockpicker.sec import SecClient
from stockpicker.security_master import load_security_mappings_csv

console = Console()


@click.group()
@click.option("--db", "db_path", default="data/stockpicker.sqlite", help="SQLite database path.")
@click.pass_context
def app(ctx: click.Context, db_path: str) -> None:
    ctx.obj = {"db": Database(db_path)}


@app.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    console.print("[green]Initialized StockPicker database.[/green]")


@app.command("add-manager")
@click.option("--name", required=True)
@click.option("--cik", required=True)
@click.option("--strategy", default=StrategyType.UNKNOWN.value)
@click.option("--quality", default=5.0, type=float)
@click.option("--concentration", default=5.0, type=float)
@click.option("--turnover", default=5.0, type=float)
@click.option("--notes", default="")
@click.pass_context
def add_manager(
    ctx: click.Context,
    name: str,
    cik: str,
    strategy: str,
    quality: float,
    concentration: float,
    turnover: float,
    notes: str,
) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    manager_id = db.upsert_manager(
        Manager(
            name=name,
            cik=cik,
            strategy=StrategyType(strategy),
            quality_score=quality,
            concentration_score=concentration,
            turnover_score=turnover,
            notes=notes,
        )
    )
    console.print(f"[green]Saved manager {name} as id {manager_id}.[/green]")


@app.command("managers")
@click.pass_context
def managers(ctx: click.Context) -> None:
    db: Database = ctx.obj["db"]
    table = Table(title="Tracked Managers")
    for column in ["ID", "Name", "CIK", "Strategy", "Quality"]:
        table.add_column(column)
    for manager in db.managers():
        table.add_row(
            str(manager.id),
            manager.name,
            manager.cik,
            manager.strategy,
            f"{manager.quality_score:.1f}",
        )
    console.print(table)


@app.command("import-managers")
@click.argument("csv_path", type=click.Path(exists=True))
@click.pass_context
def import_managers(ctx: click.Context, csv_path: str) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    imported = 0
    for manager in load_manager_universe_csv(csv_path):
        db.upsert_manager(manager)
        imported += 1
    console.print(f"[green]Imported {imported} managers.[/green]")


@app.command("ingest-13f")
@click.option("--cik", required=True)
@click.option("--user-agent", envvar="SEC_USER_AGENT", required=True)
@click.option("--limit", default=4)
@click.option("--ticker-map", type=click.Path(exists=True), default=None)
@click.pass_context
def ingest_13f(
    ctx: click.Context, cik: str, user_agent: str, limit: int, ticker_map: str | None
) -> None:
    db: Database = ctx.obj["db"]
    manager = db.manager_by_cik(cik)
    if not manager:
        raise click.ClickException(f"No manager found for CIK {cik}. Add it first.")
    result = ingest_13f_filings(
        db=db,
        manager=manager,
        sec_client=SecClient(user_agent),
        limit=limit,
        ticker_map_path=ticker_map,
    )
    console.print(
        f"[green]Ingested {result.filing_count} filings and "
        f"{result.holding_count} holdings for {result.manager.name}.[/green]"
    )


@app.command("ingest-beneficial")
@click.option("--cik", required=True)
@click.option("--user-agent", envvar="SEC_USER_AGENT", required=True)
@click.option("--limit", default=20)
@click.pass_context
def ingest_beneficial(ctx: click.Context, cik: str, user_agent: str, limit: int) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    manager = db.manager_by_cik(cik)
    if not manager:
        raise click.ClickException(f"No manager found for CIK {cik}. Add it first.")
    result = ingest_beneficial_ownership_filings(
        db=db,
        manager=manager,
        sec_client=SecClient(user_agent),
        limit=limit,
    )
    console.print(
        f"[green]Ingested {result.filing_count} 13D/13G filings and "
        f"{result.signal_count} signals for {result.manager.name}.[/green]"
    )


@app.command("beneficial-filings")
@click.option("--ticker", default=None)
@click.pass_context
def beneficial_filings(ctx: click.Context, ticker: str | None) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    table = Table(title="Beneficial Ownership Filings")
    for column in ["Date", "Ticker", "Issuer", "Type", "Ownership", "Price Range"]:
        table.add_column(column)
    for filing in db.beneficial_ownership_filings(ticker=ticker):
        ownership = f"{filing.ownership_pct:.1f}%" if filing.ownership_pct is not None else ""
        price_range = ""
        if filing.price_low is not None and filing.price_high is not None:
            price_range = f"${filing.price_low:.2f}-${filing.price_high:.2f}"
        table.add_row(
            filing.filing_date.isoformat(),
            filing.ticker or "",
            filing.issuer_name,
            str(filing.filing_type),
            ownership,
            price_range,
        )
    console.print(table)


@app.command("run-season")
@click.option("--user-agent", envvar="SEC_USER_AGENT")
@click.option("--limit", default=4)
@click.option("--ticker-map", type=click.Path(exists=True), default=None)
@click.option("--skip-ingest", is_flag=True, help="Generate signals from already-ingested filings.")
@click.pass_context
def run_season(
    ctx: click.Context,
    user_agent: str | None,
    limit: int,
    ticker_map: str | None,
    skip_ingest: bool,
) -> None:
    db: Database = ctx.obj["db"]
    active_managers = db.managers()
    if not active_managers:
        raise click.ClickException("No active managers found. Import or add managers first.")
    if not skip_ingest and not user_agent:
        raise click.ClickException("SEC_USER_AGENT is required unless --skip-ingest is used.")
    sec_client = None if skip_ingest else SecClient(user_agent)
    result = run_filing_season(
        db=db,
        managers=active_managers,
        sec_client=sec_client,
        limit=limit,
        ticker_map_path=ticker_map,
        ingest=not skip_ingest,
    )
    filing_count = sum(item.filing_count for item in result.ingested)
    holding_count = sum(item.holding_count for item in result.ingested)
    console.print(
        "[green]Filing season run complete.[/green] "
        f"Managers: {len(active_managers)} | Filings: {filing_count} | "
        f"Holdings: {holding_count} | Signals: {result.signal_count} | "
        f"Mapped holdings: {result.mapping_updates}"
    )
    if result.manager_errors:
        error_table = Table(title="Manager Errors")
        error_table.add_column("Manager")
        error_table.add_column("Error")
        for manager_name, error in result.manager_errors.items():
            error_table.add_row(manager_name, error)
        console.print(error_table)


@app.command("generate-signals")
@click.option("--cik", default=None)
@click.pass_context
def generate_signals(ctx: click.Context, cik: str | None) -> None:
    db: Database = ctx.obj["db"]
    managers = [db.manager_by_cik(cik)] if cik else db.managers()
    total = 0
    for manager in managers:
        if manager is None:
            continue
        total += len(generate_manager_signals(db, manager))
    console.print(f"[green]Generated {total} signals.[/green]")


@app.command("opportunities")
@click.option("--refresh-prices", is_flag=True)
@click.option("--limit", default=25)
@click.pass_context
def opportunities(ctx: click.Context, refresh_prices: bool, limit: int) -> None:
    db: Database = ctx.obj["db"]
    ranked = _ranked_opportunities(db, refresh_prices=refresh_prices)
    table = Table(title="Ranked Filing Opportunities")
    for column in ["Rank", "Ticker", "Score", "Signal", "Price", "Managers"]:
        table.add_column(column)
    for index, item in enumerate(ranked[:limit], start=1):
        table.add_row(
            str(index),
            item.ticker,
            f"{item.score:.1f}",
            item.best_signal.value,
            item.price_status.value,
            ", ".join(item.managers),
        )
    console.print(table)


@app.command("alerts")
@click.option("--refresh-prices", is_flag=True)
@click.option("--save-watchlist", is_flag=True)
@click.option("--limit", default=50)
@click.pass_context
def alerts(
    ctx: click.Context, refresh_prices: bool, save_watchlist: bool, limit: int
) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    ranked = _ranked_opportunities(db, refresh_prices=refresh_prices)[:limit]
    alerts = alerts_from_opportunities(ranked, db.watchlist_by_ticker())
    table = Table(title="Operating Alerts")
    for column in ["Severity", "Type", "Ticker", "Message"]:
        table.add_column(column)
    for alert in alerts:
        table.add_row(
            str(alert.severity),
            alert.alert_type.value,
            alert.ticker,
            alert.message,
        )
    console.print(table)
    if save_watchlist:
        for item in watchlist_items_from_opportunities(ranked):
            db.upsert_watchlist_item(item)
        console.print(f"[green]Saved {len(ranked)} opportunities to watchlist.[/green]")


@app.command("watchlist")
@click.pass_context
def watchlist(ctx: click.Context) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    table = Table(title="Watchlist")
    for column in ["Ticker", "State", "Price Status", "Score", "Updated"]:
        table.add_column(column)
    for item in db.watchlist():
        table.add_row(
            item.ticker,
            item.state.value,
            item.last_price_status.value if item.last_price_status else "",
            f"{item.opportunity_score:.1f}" if item.opportunity_score is not None else "",
            item.updated_at.isoformat(timespec="seconds") if item.updated_at else "",
        )
    console.print(table)


@app.command("position")
@click.option("--ticker", required=True)
@click.option("--issuer-name", default=None)
@click.option("--status", type=click.Choice([item.value for item in ThesisStatus]), required=True)
@click.option("--target-weight", type=float, default=None)
@click.option("--entry-price", type=float, default=None)
@click.option("--add-below", type=float, default=None)
@click.option("--trim-above", type=float, default=None)
@click.option("--exit-condition", default="")
@click.option("--thesis", default="")
@click.pass_context
def position(
    ctx: click.Context,
    ticker: str,
    issuer_name: str | None,
    status: str,
    target_weight: float | None,
    entry_price: float | None,
    add_below: float | None,
    trim_above: float | None,
    exit_condition: str,
    thesis: str,
) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    db.upsert_portfolio_position(
        PortfolioPosition(
            ticker=ticker,
            issuer_name=issuer_name,
            thesis_status=ThesisStatus(status),
            target_weight=target_weight,
            entry_price=entry_price,
            add_below=add_below,
            trim_above=trim_above,
            exit_condition=exit_condition,
            thesis=thesis,
        )
    )
    console.print(f"[green]Saved position plan for {ticker.upper()}.[/green]")


@app.command("portfolio")
@click.pass_context
def portfolio(ctx: click.Context) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    table = Table(title="Portfolio Plans")
    for column in ["Ticker", "Status", "Target", "Entry", "Add Below", "Trim Above", "Exit"]:
        table.add_column(column)
    for item in db.portfolio_positions():
        table.add_row(
            item.ticker,
            item.thesis_status.value,
            f"{item.target_weight:.1%}" if item.target_weight is not None else "",
            f"${item.entry_price:.2f}" if item.entry_price is not None else "",
            f"${item.add_below:.2f}" if item.add_below is not None else "",
            f"${item.trim_above:.2f}" if item.trim_above is not None else "",
            item.exit_condition,
        )
    console.print(table)


@app.command("decision")
@click.option("--ticker", required=True)
@click.option(
    "--type",
    "decision_type",
    type=click.Choice([item.value for item in DecisionType]),
    required=True,
)
@click.option("--rationale", required=True)
@click.option("--price", type=float, default=None)
@click.option("--signal-id", type=int, default=None)
@click.option("--date", "decision_date", type=click.DateTime(formats=["%Y-%m-%d"]), default=None)
@click.pass_context
def decision(
    ctx: click.Context,
    ticker: str,
    decision_type: str,
    rationale: str,
    price: float | None,
    signal_id: int | None,
    decision_date,
) -> None:
    from datetime import date as date_type

    db: Database = ctx.obj["db"]
    db.init()
    entry_id = db.add_decision(
        DecisionJournalEntry(
            ticker=ticker,
            decision_type=DecisionType(decision_type),
            decision_date=decision_date.date() if decision_date else date_type.today(),
            rationale=rationale,
            price=price,
            signal_id=signal_id,
        )
    )
    console.print(f"[green]Recorded decision {entry_id} for {ticker.upper()}.[/green]")


@app.command("decisions")
@click.option("--ticker", default=None)
@click.pass_context
def decisions(ctx: click.Context, ticker: str | None) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    table = Table(title="Decision Journal")
    for column in ["Date", "Ticker", "Type", "Price", "Rationale"]:
        table.add_column(column)
    for item in db.decisions(ticker=ticker):
        table.add_row(
            item.decision_date.isoformat(),
            item.ticker,
            item.decision_type.value,
            f"${item.price:.2f}" if item.price is not None else "",
            item.rationale,
        )
    console.print(table)


@app.command("import-security-map")
@click.argument("csv_path", type=click.Path(exists=True))
@click.pass_context
def import_security_map(ctx: click.Context, csv_path: str) -> None:
    db: Database = ctx.obj["db"]
    db.init()
    mappings = load_security_mappings_csv(csv_path)
    imported = db.upsert_security_mappings(mappings)
    applied = db.apply_security_mappings()
    console.print(
        f"[green]Imported {imported} security mappings and applied {applied} holdings.[/green]"
    )


@app.command("apply-security-map")
@click.pass_context
def apply_security_map(ctx: click.Context) -> None:
    db: Database = ctx.obj["db"]
    applied = db.apply_security_mappings()
    console.print(f"[green]Applied mappings to {applied} holdings.[/green]")


@app.command("unmapped-holdings")
@click.option("--limit", default=50)
@click.pass_context
def unmapped_holdings(ctx: click.Context, limit: int) -> None:
    db: Database = ctx.obj["db"]
    table = Table(title="Unmapped Holdings")
    for column in ["Issuer", "CUSIP", "Market Value", "Period"]:
        table.add_column(column)
    for holding in db.unmapped_holdings(limit=limit):
        table.add_row(
            holding.issuer_name,
            holding.cusip or "",
            f"${holding.market_value:,.0f}",
            holding.report_period.isoformat(),
        )
    console.print(table)


@app.command("dashboard")
@click.option("--out", type=click.Path(), default="dashboard.html")
@click.option("--refresh-prices", is_flag=True)
@click.option("--limit", default=50)
@click.pass_context
def dashboard(ctx: click.Context, out: str, refresh_prices: bool, limit: int) -> None:
    db: Database = ctx.obj["db"]
    ranked = _ranked_opportunities(db, refresh_prices=refresh_prices)[:limit]
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(ranked))
    console.print(f"[green]Wrote {path}[/green]")


@app.command("backtest")
@click.option(
    "--group-by",
    type=click.Choice(["signal_type", "manager", "price_status", "ticker"]),
    default="signal_type",
)
@click.option("--holding-days", default=180)
@click.option("--refresh-prices", is_flag=True)
@click.pass_context
def backtest(
    ctx: click.Context, group_by: str, holding_days: int, refresh_prices: bool
) -> None:
    db: Database = ctx.obj["db"]
    signals = db.signals()
    estimates = build_cost_estimates_for_signals(
        db=db, signals=signals, refresh_prices=refresh_prices
    )
    prices_by_ticker = db.all_prices_for_tickers(signal.ticker for signal in signals)
    observations = build_backtest_observations(
        signals=signals,
        managers=db.managers(),
        prices_by_ticker=prices_by_ticker,
        cost_estimates=estimates,
        holding_days=holding_days,
    )
    summaries = summarize_observations(observations, group_by=group_by)
    table = Table(title=f"Backtest by {group_by.replace('_', ' ')}")
    for column in ["Group", "N", "Hit Rate", "Avg", "Median", "Best", "Worst"]:
        table.add_column(column)
    for item in summaries:
        table.add_row(
            item.group,
            str(item.sample_size),
            f"{item.hit_rate:.1%}",
            f"{item.average_return:.1%}",
            f"{item.median_return:.1%}",
            f"{item.best_return:.1%}",
            f"{item.worst_return:.1%}",
        )
    console.print(table)


@app.command("research-packet")
@click.option("--ticker", required=True)
@click.option("--out", type=click.Path(), default="research")
@click.pass_context
def research_packet(ctx: click.Context, ticker: str, out: str) -> None:
    db: Database = ctx.obj["db"]
    signals = db.signals()
    estimates = build_cost_estimates_for_signals(db=db, signals=signals)
    ranked = rank_opportunities(signals=signals, managers=db.managers(), cost_estimates=estimates)
    opportunity = next((item for item in ranked if item.ticker == ticker.upper()), None)
    if not opportunity:
        raise click.ClickException(f"No opportunity found for {ticker.upper()}.")
    output_dir = Path(out)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{ticker.upper()}_research_packet.md"
    path.write_text(render_research_packet(opportunity, signals, estimates))
    console.print(f"[green]Wrote {path}[/green]")


def _ranked_opportunities(db: Database, refresh_prices: bool = False):
    signals = db.signals()
    estimates = build_cost_estimates_for_signals(
        db=db, signals=signals, refresh_prices=refresh_prices
    )
    return rank_opportunities(signals=signals, managers=db.managers(), cost_estimates=estimates)


if __name__ == "__main__":
    app()
