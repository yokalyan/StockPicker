from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from stockpicker.dashboard import render_dashboard
from stockpicker.db import Database
from stockpicker.manager_universe import load_manager_universe_csv
from stockpicker.models import Manager, StrategyType
from stockpicker.opportunities import rank_opportunities
from stockpicker.pipeline import (
    build_cost_estimates_for_signals,
    generate_manager_signals,
    ingest_13f_filings,
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
    signals = db.signals()
    estimates = build_cost_estimates_for_signals(
        db=db, signals=signals, refresh_prices=refresh_prices
    )
    ranked = rank_opportunities(signals=signals, managers=db.managers(), cost_estimates=estimates)
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
    signals = db.signals()
    estimates = build_cost_estimates_for_signals(
        db=db, signals=signals, refresh_prices=refresh_prices
    )
    ranked = rank_opportunities(
        signals=signals, managers=db.managers(), cost_estimates=estimates
    )[:limit]
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(ranked))
    console.print(f"[green]Wrote {path}[/green]")


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


if __name__ == "__main__":
    app()
