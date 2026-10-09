# StockPicker Requirements

## Objective

Build a private filings intelligence platform that turns SEC 13F/13D/13G disclosures
into a ranked research queue for active equity underwriting.

The system is explicitly not a trade recommender. It is an evidence funnel.

## User Profile

- Active investor.
- Willing to underwrite businesses independently.
- Interested in small and mid-cap opportunities.
- Wants a repeatable research process.
- Can ignore most signals and wait for price.

## Functional Requirements

### Manager Universe

- Store curated managers with CIKs, strategy labels, quality scores, concentration scores,
  turnover scores, and notes.
- Allow managers to be excluded or de-emphasized through scoring.

### Filing Ingestion

- Pull recent SEC 13F filings for tracked managers.
- Parse 13F information tables into normalized holdings.
- Support 13D/13G beneficial ownership extraction for ownership percentage, share count,
  disclosed price range, and purpose text.

### Signal Engine

- Detect new positions, adds, large adds, trims, large trims, exits, top-position changes,
  activist filings, and beneficial-owner filings.
- Store signals with enough source metadata to audit why they were created.

### Cost Basis

- Estimate sponsor cost basis from quarterly price and volume data.
- Classify each signal as below sponsor cost, inside buy zone, too expensive, or needs
  underwriting.

### Ranking

- Rank opportunities by manager quality, signal type, position weight, price status, and
  number of tracked managers involved.
- Rank “worth researching,” not “worth buying.”

### Research Workflow

- Generate Markdown research packets with:
  - Why the idea surfaced.
  - Filing signals.
  - Cost-basis context.
  - Underwriting questions.
  - Decision log.

### Validation

- Provide lightweight forward-return summaries by signal type.
- Preserve the ability to expand into manager-level and price-zone backtests.

## Non-Goals For MVP

- Broker integration.
- Automated trading.
- Full valuation automation.
- Real-time news ingestion.
- Multi-user collaboration.
- Perfect parsing of every historical SEC filing variant.

## Build Phases

1. SEC/SQLite core.
2. Signals, pricing, and opportunity ranking.
3. CLI workflow and research packets.
4. 13D/13G beneficial ownership signals.
5. Backtest primitives and requirements documentation.

## Definition Of Done

- Lint passes.
- Tests pass.
- CLI can initialize the database and expose the workflow.
- Each phase is committed separately.
- README explains setup and usage.
