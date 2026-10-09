from __future__ import annotations

from datetime import UTC, datetime

from stockpicker.models import (
    CostBasisEstimate,
    FundamentalSnapshot,
    LiquiditySnapshot,
    Opportunity,
    Signal,
)


def render_research_packet(
    opportunity: Opportunity,
    signals: list[Signal],
    cost_estimates: list[CostBasisEstimate],
    fundamental: FundamentalSnapshot | None = None,
    liquidity: LiquiditySnapshot | None = None,
) -> str:
    matching_signals = [item for item in signals if item.ticker == opportunity.ticker]
    matching_costs = [item for item in cost_estimates if item.ticker == opportunity.ticker]

    lines = [
        f"# {opportunity.ticker} Research Packet",
        "",
        f"Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        "",
        "## Why It Surfaced",
        "",
        f"- Opportunity score: {opportunity.score}",
        f"- Best signal: {opportunity.best_signal.value}",
        f"- Price status: {opportunity.price_status.value}",
        f"- Crowding: {opportunity.crowding_label} ({opportunity.crowding_score:+.1f})",
        f"- Managers: {', '.join(opportunity.managers)}",
        "",
    ]
    lines.extend(f"- {reason}" for reason in opportunity.rationale)
    lines.extend(["", "## Filing Signals", ""])

    for signal in matching_signals:
        lines.append(
            "- "
            f"{signal.report_period.isoformat()} | {signal.signal_type.value} | "
            f"shares {signal.prior_shares:,.0f} -> {signal.current_shares:,.0f} | "
            f"weight {_pct(signal.current_weight)}"
        )

    lines.extend(["", "## Cost Basis", ""])
    if matching_costs:
        for estimate in matching_costs:
            current = (
                f"${estimate.current_price:,.2f}" if estimate.current_price is not None else "n/a"
            )
            lines.append(
                "- "
                f"Manager {estimate.manager_id}: ${estimate.low_cost:,.2f}-"
                f"${estimate.high_cost:,.2f}; midpoint ${estimate.midpoint:,.2f}; "
                f"current {current}; confidence {estimate.confidence}"
            )
    else:
        lines.append("- No cost-basis estimate available yet.")

    lines.extend(
        [
            "",
            "## Crowding And Ownership",
            "",
            f"- Crowding label: {opportunity.crowding_label}",
            f"- Crowding score: {opportunity.crowding_score:+.1f}",
            "- Peer holder overlap: review tracked manager list and recent adds/trims.",
            "",
            "## Company Snapshot To Fill",
            "",
            "- Business description:",
            f"- Market cap: {_money(fundamental.market_cap) if fundamental else ''}",
            f"- Enterprise value: {_money(fundamental.enterprise_value) if fundamental else ''}",
            f"- Sector / industry: {_sector(fundamental)}",
            f"- Revenue: {_money(fundamental.revenue) if fundamental else ''}",
            f"- Net income: {_money(fundamental.net_income) if fundamental else ''}",
            f"- Operating income: {_money(fundamental.operating_income) if fundamental else ''}",
            f"- Cash: {_money(fundamental.cash) if fundamental else ''}",
            f"- Debt: {_money(fundamental.debt) if fundamental else ''}",
            "- Recent earnings notes:",
            "- Insider ownership / trading:",
            "- Short interest:",
            "- 30d average dollar volume: "
            f"{_money(liquidity.avg_dollar_volume_30d) if liquidity else ''}",
            "- 90d average dollar volume: "
            f"{_money(liquidity.avg_dollar_volume_90d) if liquidity else ''}",
            f"- Liquidity label: {liquidity.liquidity_label if liquidity else ''}",
            "- Primary risks:",
            "",
            "## Underwriting Questions",
            "",
            "- What does the business do, and why is it mispriced?",
            "- What must be true for the manager's thesis to work?",
            "- Is the current price near or below the sponsor's likely economics?",
            "- What is the market missing, and what evidence would disconfirm it?",
            "- Are other tracked managers crowding into or exiting the same idea?",
            "- What would make us add, hold, reject, or sell?",
            "",
            "## Decision Log",
            "",
            "- Status: needs underwriting",
            "- Initial decision:",
            "- Follow-up date:",
        ]
    )
    return "\n".join(lines) + "\n"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _money(value: float | None) -> str:
    return "" if value is None else f"${value:,.0f}"


def _sector(fundamental: FundamentalSnapshot | None) -> str:
    if not fundamental:
        return ""
    values = [item for item in [fundamental.sector, fundamental.industry] if item]
    return " / ".join(values)
