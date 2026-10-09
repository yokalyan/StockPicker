from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from stockpicker.models import (
    CostBasisEstimate,
    Manager,
    PriceBar,
    Signal,
    SignalType,
    WatchlistState,
)


@dataclass(frozen=True)
class BacktestResult:
    signal_type: SignalType
    sample_size: int
    hit_rate: float
    average_return: float
    median_return: float


@dataclass(frozen=True)
class BacktestObservation:
    ticker: str
    manager_name: str
    manager_id: int
    signal_type: SignalType
    price_status: WatchlistState
    signal_date: date
    holding_days: int
    forward_return: float
    benchmark_return: float | None = None
    excess_return: float | None = None


@dataclass(frozen=True)
class GroupedBacktestResult:
    group: str
    sample_size: int
    hit_rate: float
    average_return: float
    median_return: float
    best_return: float
    worst_return: float


def forward_return(
    *,
    prices: list[PriceBar],
    signal_date: date,
    holding_days: int,
) -> float | None:
    if not prices:
        return None
    ordered = sorted(prices, key=lambda item: item.trade_date)
    entry = next((bar for bar in ordered if bar.trade_date >= signal_date), None)
    exit_date = signal_date + timedelta(days=holding_days)
    exit_bar = next((bar for bar in ordered if bar.trade_date >= exit_date), ordered[-1])
    if not entry or not entry.close:
        return None
    return (exit_bar.close - entry.close) / entry.close


def summarize_forward_returns(
    *,
    signals: list[Signal],
    prices_by_ticker: dict[str, list[PriceBar]],
    holding_days: int = 180,
) -> list[BacktestResult]:
    returns_by_type: dict[SignalType, list[float]] = {}
    for signal in signals:
        result = forward_return(
            prices=prices_by_ticker.get(signal.ticker, []),
            signal_date=signal.report_period,
            holding_days=holding_days,
        )
        if result is None:
            continue
        returns_by_type.setdefault(signal.signal_type, []).append(result)

    summaries: list[BacktestResult] = []
    for signal_type, returns in returns_by_type.items():
        sorted_returns = sorted(returns)
        midpoint = len(sorted_returns) // 2
        if len(sorted_returns) % 2:
            median = sorted_returns[midpoint]
        else:
            median = (sorted_returns[midpoint - 1] + sorted_returns[midpoint]) / 2
        summaries.append(
            BacktestResult(
                signal_type=signal_type,
                sample_size=len(returns),
                hit_rate=sum(item > 0 for item in returns) / len(returns),
                average_return=sum(returns) / len(returns),
                median_return=median,
            )
        )
    return sorted(summaries, key=lambda item: item.average_return, reverse=True)


def build_backtest_observations(
    *,
    signals: list[Signal],
    managers: list[Manager],
    prices_by_ticker: dict[str, list[PriceBar]],
    cost_estimates: list[CostBasisEstimate] | None = None,
    benchmark_prices: list[PriceBar] | None = None,
    holding_days: int = 180,
) -> list[BacktestObservation]:
    managers_by_id = {manager.id: manager for manager in managers if manager.id is not None}
    cost_by_key = {
        (estimate.manager_id, estimate.ticker, estimate.report_period): estimate
        for estimate in cost_estimates or []
    }
    observations: list[BacktestObservation] = []
    for signal in signals:
        result = forward_return(
            prices=prices_by_ticker.get(signal.ticker, []),
            signal_date=signal.report_period,
            holding_days=holding_days,
        )
        if result is None:
            continue
        benchmark_return = (
            forward_return(
                prices=benchmark_prices,
                signal_date=signal.report_period,
                holding_days=holding_days,
            )
            if benchmark_prices
            else None
        )
        manager = managers_by_id.get(signal.manager_id)
        estimate = cost_by_key.get((signal.manager_id, signal.ticker, signal.report_period))
        observations.append(
            BacktestObservation(
                ticker=signal.ticker,
                manager_name=manager.name if manager else f"Manager {signal.manager_id}",
                manager_id=signal.manager_id,
                signal_type=signal.signal_type,
                price_status=estimate.status if estimate else WatchlistState.NEEDS_UNDERWRITING,
                signal_date=signal.report_period,
                holding_days=holding_days,
                forward_return=result,
                benchmark_return=benchmark_return,
                excess_return=(
                    result - benchmark_return if benchmark_return is not None else None
                ),
            )
        )
    return observations


def summarize_observations(
    observations: list[BacktestObservation],
    group_by: str = "signal_type",
    return_field: str = "forward_return",
) -> list[GroupedBacktestResult]:
    grouped: dict[str, list[float]] = {}
    for observation in observations:
        value = getattr(observation, return_field)
        if value is None:
            continue
        group = _group_value(observation, group_by)
        grouped.setdefault(group, []).append(value)

    summaries = [
        GroupedBacktestResult(
            group=group,
            sample_size=len(returns),
            hit_rate=sum(item > 0 for item in returns) / len(returns),
            average_return=sum(returns) / len(returns),
            median_return=_median(returns),
            best_return=max(returns),
            worst_return=min(returns),
        )
        for group, returns in grouped.items()
        if returns
    ]
    return sorted(summaries, key=lambda item: item.average_return, reverse=True)


def _group_value(observation: BacktestObservation, group_by: str) -> str:
    if group_by == "manager":
        return observation.manager_name
    if group_by == "price_status":
        return observation.price_status.value
    if group_by == "ticker":
        return observation.ticker
    if group_by == "signal_type":
        return observation.signal_type.value
    raise ValueError(f"Unsupported backtest group: {group_by}")


def _median(values: list[float]) -> float:
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[midpoint]
    return (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2
