from __future__ import annotations

from datetime import UTC, datetime

from stockpicker.models import CostBasisEstimate, Opportunity, Signal


def render_research_packet(
    opportunity: Opportunity,
    signals: list[Signal],
    cost_estimates: list[CostBasisEstimate],
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
