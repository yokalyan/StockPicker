# Initial Draft Audit

This document maps the original StockPicker product draft to the implementation.

## Covered

- Manager universe: manager CIKs, strategy classification, quality/concentration/turnover
  scores, holding-period estimate, active/excluded state, CSV import, notes.
- Filing ingestion: 13F, 13F/A, 13D, 13D/A, 13G, 13G/A ingestion paths.
- Holdings database: issuer, CUSIP, ticker, shares, market value, put/call, portfolio
  weight, quarter/report period.
- Change detection: new positions, adds, large adds, trims, large trims, exits, top
  positions, multi-quarter accumulation, multi-quarter distribution, activist and
  beneficial-owner signals.
- Cost basis: quarter price range, volume-weighted midpoint, current price comparison,
  buy-zone classification, confidence label.
- Opportunity scoring: manager quality, signal type, position weight, price status,
  multi-manager confirmation, and explicit crowding score/label.
- Crowding analysis: tracked holder count, adding count, trimming count, strategy
  diversity, aggregate tracked weight, and crowding label.
- Research workflow: Markdown packets, filing signals, cost basis, crowding section,
  diligence prompts, company snapshot placeholders, decision log.
- Watchlist and alerts: buy-zone, below-sponsor-cost, price-zone changes, new signals,
  persisted watchlist states.
- Backtesting: forward returns grouped by signal type, manager, ticker, and price-zone
  status across configurable holding periods.
- Benchmark-relative backtests: optional benchmark price history, including SPY, and
  grouped excess-return summaries.
- Free market data enrichment: yfinance price/fundamental snapshots, SEC company facts
  fundamentals, and 30d/90d average dollar-volume liquidity labels.
- Portfolio tracking: position plans, thesis status, entry/add/trim/exit conditions, and
  decision journal.
- UI: CLI, static dashboard export, and local browser dashboard.

## Partially Covered

- Market cap, sector, high-level fundamentals, and liquidity can now be populated from
  free sources. Valuation multiples, short interest, insider trading, and sector-relative
  analysis still need a dependable source or explicit import path.
- Sector-relative backtests are not yet implemented; current relative backtests compare
  against a user-selected benchmark such as SPY.
- 13G-to-13D conversion detection is not explicit yet. The raw filings and signal types
  are persisted, so a conversion detector can be added on top.
- Historical manager signal quality is available through grouped backtests, but manager
  quality scores are still manually curated rather than auto-updated.

## Deferred On Purpose

- Broker integration.
- Automated trading.
- Automated valuation model.
- Real-time news ingestion and thesis-breaking news.
- Multi-user hosted deployment.
- Full historical SEC backfill at scale.
