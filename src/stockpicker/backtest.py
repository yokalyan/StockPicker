from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from stockpicker.models import PriceBar, Signal, SignalType


@dataclass(frozen=True)
class BacktestResult:
    signal_type: SignalType
    sample_size: int
    hit_rate: float
    average_return: float
    median_return: float


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
