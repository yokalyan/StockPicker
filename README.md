# StockPicker

StockPicker is a private filings intelligence engine for active investors. It ingests SEC
filings, detects meaningful position changes, estimates whether the current price is near a
manager's likely entry range, and turns the best signals into a disciplined research queue.

The product goal is not automated buy/sell calls. The goal is a repeatable funnel for finding
small and mid-cap ideas worth underwriting.

## What It Does

- Tracks a curated manager universe.
- Parses 13F holdings.
- Extracts basic 13D/13G beneficial ownership signals.
- Detects new positions, adds, trims, exits, and top-position changes.
- Estimates cost-basis ranges from quarterly price and volume data.
- Ranks opportunities by manager quality, signal strength, and price discipline.
- Generates Markdown research packets with underwriting questions and a decision log.
- Includes lightweight forward-return backtest primitives.
- Imports a CUSIP-to-ticker security master and exports a static HTML dashboard.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/stockpicker init
```

Add a manager:

```bash
.venv/bin/stockpicker add-manager \
  --name "Example Capital" \
  --cik "0000000000" \
  --strategy small_mid_value \
  --quality 8.5
```

Or import a curated universe:

```bash
.venv/bin/stockpicker import-managers resources/manager_universe_template.csv
```

Ingest filings:

```bash
SEC_USER_AGENT="Your Name your.email@example.com" \
  .venv/bin/stockpicker ingest-13f --cik "0000000000" --limit 4
```

Generate signals and view opportunities:

```bash
.venv/bin/stockpicker generate-signals
.venv/bin/stockpicker opportunities --refresh-prices
```

Run the active manager universe end to end:

```bash
SEC_USER_AGENT="Your Name your.email@example.com" \
  .venv/bin/stockpicker run-season --limit 4
```

Generate a research packet:

```bash
.venv/bin/stockpicker research-packet --ticker XYZ --out research
```

Import a CUSIP-to-ticker map and export a dashboard:

```bash
.venv/bin/stockpicker import-security-map mappings.csv
.venv/bin/stockpicker unmapped-holdings
.venv/bin/stockpicker dashboard --out dashboard.html
```

Run validation backtests from stored signals and price history:

```bash
.venv/bin/stockpicker backtest --group-by signal_type --holding-days 180
.venv/bin/stockpicker backtest --group-by manager --holding-days 365
.venv/bin/stockpicker backtest --group-by price_status
```

## Current Build Phases

- Phase 1: project scaffold, SQLite schema, SEC client, 13F parser.
- Phase 2: position-change signals, cost-basis estimation, opportunity scoring.
- Phase 3: CLI workflow and research-packet generation.
- Phase 4: 13D/13G beneficial ownership parser and activist signal conversion.
- Phase 5: backtest primitives and requirements documentation.
- Phase 6: security master mapping and static dashboard export.
- Phase 7: manager universe import and filing-season run orchestration.
- Phase 8: grouped historical backtesting by signal, manager, ticker, and price zone.

## Design Principles

- Filings are leads, not recommendations.
- Manager selection matters more than raw holdings.
- Price paid changes the entire risk/reward.
- Most signals should be ignored.
- Every actionable idea needs independent underwriting.
