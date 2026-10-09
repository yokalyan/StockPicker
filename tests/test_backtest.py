from datetime import date

from stockpicker.backtest import forward_return, summarize_forward_returns
from stockpicker.models import PriceBar, Signal, SignalType


def bar(ticker: str, day: date, close: float) -> PriceBar:
    return PriceBar(
        ticker=ticker,
        trade_date=day,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
    )


def test_forward_return_uses_first_available_entry_and_exit():
    prices = [
        bar("AAA", date(2026, 1, 2), 10),
        bar("AAA", date(2026, 7, 1), 15),
    ]

    result = forward_return(prices=prices, signal_date=date(2026, 1, 1), holding_days=180)

    assert result == 0.5


def test_summarize_forward_returns_groups_by_signal_type():
    signal = Signal(
        manager_id=1,
        ticker="AAA",
        issuer_name="AAA Corp",
        signal_type=SignalType.NEW_POSITION,
        report_period=date(2026, 1, 1),
        current_shares=100,
        prior_shares=0,
        share_change=100,
        pct_change=None,
        current_weight=0.1,
        prior_weight=None,
    )

    summaries = summarize_forward_returns(
        signals=[signal],
        prices_by_ticker={
            "AAA": [bar("AAA", date(2026, 1, 2), 10), bar("AAA", date(2026, 7, 1), 8)]
        },
    )

    assert summaries[0].signal_type == SignalType.NEW_POSITION
    assert summaries[0].average_return == -0.2
    assert summaries[0].hit_rate == 0
