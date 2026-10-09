from __future__ import annotations

from collections import defaultdict
from datetime import date

from stockpicker.models import Holding, Signal, SignalType


def generate_position_signals(
    *,
    manager_id: int,
    report_period: date,
    current_holdings: list[Holding],
    prior_holdings: list[Holding],
    large_change_threshold: float = 0.5,
    top_position_threshold: float = 0.05,
) -> list[Signal]:
    """Create quarter-over-quarter signals for one manager."""

    current_by_key = {_holding_key(item): item for item in current_holdings if item.ticker}
    prior_by_key = {_holding_key(item): item for item in prior_holdings if item.ticker}
    all_keys = sorted(set(current_by_key) | set(prior_by_key))
    signals: list[Signal] = []

    for key in all_keys:
        current = current_by_key.get(key)
        prior = prior_by_key.get(key)
        if current and not prior:
            signals.append(_signal(SignalType.NEW_POSITION, current, None, report_period))
            if (current.portfolio_weight or 0) >= top_position_threshold:
                signals.append(_signal(SignalType.TOP_POSITION, current, None, report_period))
            continue
        if prior and not current:
            signals.append(_exit_signal(prior, report_period))
            continue
        if not current or not prior:
            continue

        share_change = current.shares - prior.shares
        if share_change == 0:
            continue
        pct_change = share_change / prior.shares if prior.shares else None
        if pct_change is not None and pct_change >= large_change_threshold:
            signals.append(_signal(SignalType.LARGE_ADD, current, prior, report_period))
        elif share_change > 0:
            signals.append(_signal(SignalType.ADD, current, prior, report_period))
        elif pct_change is not None and pct_change <= -large_change_threshold:
            signals.append(_signal(SignalType.LARGE_TRIM, current, prior, report_period))
        else:
            signals.append(_signal(SignalType.TRIM, current, prior, report_period))

    return signals


def detect_multi_quarter_accumulation(
    signals_by_period: dict[date, list[Signal]], min_periods: int = 2
) -> list[Signal]:
    """Flag tickers that were added across multiple sequential processed periods."""

    adds_by_ticker: dict[str, list[Signal]] = defaultdict(list)
    for period in sorted(signals_by_period):
        for signal in signals_by_period[period]:
            if signal.signal_type in {
                SignalType.ADD,
                SignalType.LARGE_ADD,
                SignalType.NEW_POSITION,
            }:
                adds_by_ticker[signal.ticker].append(signal)

    result: list[Signal] = []
    for _ticker, additions in adds_by_ticker.items():
        if len(additions) < min_periods:
            continue
        latest = additions[-1]
        result.append(
            latest.model_copy(
                update={
                    "signal_type": SignalType.MULTI_QUARTER_ACCUMULATION,
                    "metadata": {
                        **latest.metadata,
                        "accumulation_periods": len(additions),
                        "source_signal_ids": [item.id for item in additions if item.id],
                    },
                }
            )
        )
    return result


def detect_multi_quarter_distribution(
    signals_by_period: dict[date, list[Signal]], min_periods: int = 2
) -> list[Signal]:
    """Flag tickers that were trimmed or exited across multiple processed periods."""

    trims_by_ticker: dict[str, list[Signal]] = defaultdict(list)
    for period in sorted(signals_by_period):
        for signal in signals_by_period[period]:
            if signal.signal_type in {
                SignalType.TRIM,
                SignalType.LARGE_TRIM,
                SignalType.EXIT,
            }:
                trims_by_ticker[signal.ticker].append(signal)

    result: list[Signal] = []
    for _ticker, trims in trims_by_ticker.items():
        if len(trims) < min_periods:
            continue
        latest = trims[-1]
        result.append(
            latest.model_copy(
                update={
                    "signal_type": SignalType.MULTI_QUARTER_DISTRIBUTION,
                    "metadata": {
                        **latest.metadata,
                        "distribution_periods": len(trims),
                        "source_signal_ids": [item.id for item in trims if item.id],
                    },
                }
            )
        )
    return result


def _holding_key(holding: Holding) -> str:
    return (holding.ticker or holding.cusip or holding.issuer_name).upper()


def _signal(
    signal_type: SignalType, current: Holding, prior: Holding | None, report_period: date
) -> Signal:
    prior_shares = prior.shares if prior else 0.0
    share_change = current.shares - prior_shares
    pct_change = share_change / prior_shares if prior_shares else None
    return Signal(
        manager_id=current.manager_id,
        ticker=(current.ticker or current.cusip or current.issuer_name).upper(),
        issuer_name=current.issuer_name,
        signal_type=signal_type,
        report_period=report_period,
        current_shares=current.shares,
        prior_shares=prior_shares,
        share_change=share_change,
        pct_change=pct_change,
        current_weight=current.portfolio_weight,
        prior_weight=prior.portfolio_weight if prior else None,
    )


def _exit_signal(prior: Holding, report_period: date) -> Signal:
    return Signal(
        manager_id=prior.manager_id,
        ticker=(prior.ticker or prior.cusip or prior.issuer_name).upper(),
        issuer_name=prior.issuer_name,
        signal_type=SignalType.EXIT,
        report_period=report_period,
        current_shares=0.0,
        prior_shares=prior.shares,
        share_change=-prior.shares,
        pct_change=-1.0 if prior.shares else None,
        current_weight=0.0,
        prior_weight=prior.portfolio_weight,
    )
