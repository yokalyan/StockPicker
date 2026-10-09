from __future__ import annotations

from dataclasses import dataclass

from stockpicker.models import Manager, Signal, SignalType

BUYING_SIGNALS = {
    SignalType.NEW_POSITION,
    SignalType.ADD,
    SignalType.LARGE_ADD,
    SignalType.TOP_POSITION,
    SignalType.MULTI_QUARTER_ACCUMULATION,
    SignalType.ACTIVIST,
    SignalType.BENEFICIAL_OWNER,
}
SELLING_SIGNALS = {
    SignalType.TRIM,
    SignalType.LARGE_TRIM,
    SignalType.EXIT,
    SignalType.MULTI_QUARTER_DISTRIBUTION,
}


@dataclass(frozen=True)
class CrowdingSnapshot:
    ticker: str
    holder_count: int
    adding_count: int
    trimming_count: int
    strategy_count: int
    aggregate_weight: float

    @property
    def score(self) -> float:
        confirmation = min(self.adding_count * 2.0, 8.0)
        diversity = min(self.strategy_count * 1.5, 6.0)
        crowding_penalty = max(0, self.holder_count - 5) * 2.0
        trim_penalty = self.trimming_count * 2.5
        return round(confirmation + diversity - crowding_penalty - trim_penalty, 2)

    @property
    def label(self) -> str:
        if self.holder_count >= 6:
            return "crowded"
        if self.adding_count >= 2 and self.trimming_count == 0:
            return "confirmed"
        if self.trimming_count > self.adding_count:
            return "distribution"
        if self.holder_count == 1:
            return "single-sponsor"
        return "mixed"


def crowding_snapshot(
    *,
    ticker: str,
    signals: list[Signal],
    managers_by_id: dict[int, Manager],
) -> CrowdingSnapshot:
    ticker_signals = [item for item in signals if item.ticker == ticker]
    holder_ids = {item.manager_id for item in ticker_signals}
    adding_ids = {
        item.manager_id for item in ticker_signals if item.signal_type in BUYING_SIGNALS
    }
    trimming_ids = {
        item.manager_id for item in ticker_signals if item.signal_type in SELLING_SIGNALS
    }
    strategies = {
        managers_by_id[item.manager_id].strategy
        for item in ticker_signals
        if item.manager_id in managers_by_id
    }
    aggregate_weight = sum(item.current_weight or 0 for item in ticker_signals)
    return CrowdingSnapshot(
        ticker=ticker,
        holder_count=len(holder_ids),
        adding_count=len(adding_ids),
        trimming_count=len(trimming_ids),
        strategy_count=len(strategies),
        aggregate_weight=aggregate_weight,
    )
