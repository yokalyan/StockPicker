from __future__ import annotations

from collections import defaultdict
from datetime import date

from stockpicker.crowding import crowding_snapshot
from stockpicker.models import (
    CostBasisEstimate,
    Manager,
    Opportunity,
    Signal,
    SignalType,
    WatchlistState,
)

SIGNAL_WEIGHTS = {
    SignalType.ACTIVIST: 22,
    SignalType.NEW_POSITION: 16,
    SignalType.TOP_POSITION: 14,
    SignalType.LARGE_ADD: 12,
    SignalType.MULTI_QUARTER_ACCUMULATION: 12,
    SignalType.MULTI_QUARTER_DISTRIBUTION: -14,
    SignalType.BENEFICIAL_OWNER: 10,
    SignalType.ADD: 6,
    SignalType.TRIM: -6,
    SignalType.LARGE_TRIM: -12,
    SignalType.EXIT: -20,
}

PRICE_WEIGHTS = {
    WatchlistState.BELOW_SPONSOR_COST: 18,
    WatchlistState.INSIDE_BUY_ZONE: 12,
    WatchlistState.NEEDS_UNDERWRITING: 4,
    WatchlistState.MONITOR_ONLY: 0,
    WatchlistState.TOO_EXPENSIVE: -10,
    WatchlistState.REJECTED: -30,
    WatchlistState.UNDER_RESEARCH: 5,
    WatchlistState.OWNED: 0,
}


def rank_opportunities(
    *,
    signals: list[Signal],
    managers: list[Manager],
    cost_estimates: list[CostBasisEstimate] | None = None,
    report_period: date | None = None,
) -> list[Opportunity]:
    managers_by_id = {manager.id: manager for manager in managers if manager.id is not None}
    costs_by_key = {
        (estimate.manager_id, estimate.ticker): estimate for estimate in cost_estimates or []
    }
    grouped: dict[str, list[Signal]] = defaultdict(list)
    for signal in signals:
        if report_period and signal.report_period != report_period:
            continue
        grouped[signal.ticker].append(signal)

    opportunities: list[Opportunity] = []
    for ticker, ticker_signals in grouped.items():
        issuer_name = ticker_signals[0].issuer_name
        score = 0.0
        rationale: list[str] = []
        manager_names: list[str] = []
        best_signal = max(
            ticker_signals, key=lambda item: SIGNAL_WEIGHTS.get(item.signal_type, 0)
        ).signal_type
        price_status = WatchlistState.NEEDS_UNDERWRITING

        for signal in ticker_signals:
            manager = managers_by_id.get(signal.manager_id)
            manager_quality = manager.quality_score if manager else 5.0
            manager_names.append(manager.name if manager else f"Manager {signal.manager_id}")
            signal_score = SIGNAL_WEIGHTS.get(signal.signal_type, 0)
            score += signal_score * (manager_quality / 10)
            if signal.current_weight:
                score += min(signal.current_weight * 100, 10)
            rationale.append(
                f"{signal.signal_type.value} from {manager_names[-1]}"
                + (
                    f" at {signal.current_weight:.1%} weight"
                    if signal.current_weight is not None
                    else ""
                )
            )

            estimate = costs_by_key.get((signal.manager_id, signal.ticker))
            if estimate:
                score += PRICE_WEIGHTS[estimate.status]
                if PRICE_WEIGHTS[estimate.status] > PRICE_WEIGHTS[price_status]:
                    price_status = estimate.status
                rationale.append(
                    f"price is {estimate.status.value.replace('_', ' ')} "
                    f"versus ${estimate.low_cost}-${estimate.high_cost} estimated cost"
                )

        if len(set(manager_names)) > 1:
            score += min(len(set(manager_names)) * 4, 12)
            rationale.append(f"{len(set(manager_names))} tracked managers involved")

        crowding = crowding_snapshot(
            ticker=ticker,
            signals=ticker_signals,
            managers_by_id=managers_by_id,
        )
        score += crowding.score
        rationale.append(
            f"crowding: {crowding.label}; {crowding.adding_count} adding, "
            f"{crowding.trimming_count} trimming, {crowding.holder_count} tracked holders"
        )

        opportunities.append(
            Opportunity(
                ticker=ticker,
                issuer_name=issuer_name,
                report_period=max(signal.report_period for signal in ticker_signals),
                score=round(score, 2),
                signal_count=len(ticker_signals),
                managers=sorted(set(manager_names)),
                best_signal=best_signal,
                price_status=price_status,
                rationale=rationale,
                crowding_score=crowding.score,
                crowding_label=crowding.label,
            )
        )

    return sorted(opportunities, key=lambda item: item.score, reverse=True)
