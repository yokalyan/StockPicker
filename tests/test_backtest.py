from datetime import date

from stockpicker.backtest import (
    build_backtest_observations,
    forward_return,
    summarize_forward_returns,
    summarize_observations,
)
from stockpicker.models import (
    CostBasisEstimate,
    Manager,
    PriceBar,
    Signal,
    SignalType,
    WatchlistState,
)


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


def test_backtest_observations_include_manager_and_price_status():
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
    manager = Manager(id=1, name="Patient Capital", cik="1")
    estimate = CostBasisEstimate(
        ticker="AAA",
        manager_id=1,
        report_period=date(2026, 1, 1),
        low_cost=9,
        high_cost=11,
        midpoint=10,
        status=WatchlistState.INSIDE_BUY_ZONE,
    )

    observations = build_backtest_observations(
        signals=[signal],
        managers=[manager],
        prices_by_ticker={
            "AAA": [bar("AAA", date(2026, 1, 2), 10), bar("AAA", date(2026, 7, 1), 12)]
        },
        cost_estimates=[estimate],
    )

    assert observations[0].manager_name == "Patient Capital"
    assert observations[0].price_status == WatchlistState.INSIDE_BUY_ZONE
    assert observations[0].forward_return == 0.2

    by_manager = summarize_observations(observations, group_by="manager")
    by_price = summarize_observations(observations, group_by="price_status")

    assert by_manager[0].group == "Patient Capital"
    assert by_price[0].group == "inside_buy_zone"


def test_backtest_observations_include_benchmark_and_excess_return():
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

    observations = build_backtest_observations(
        signals=[signal],
        managers=[Manager(id=1, name="Patient Capital", cik="1")],
        prices_by_ticker={
            "AAA": [bar("AAA", date(2026, 1, 2), 10), bar("AAA", date(2026, 7, 1), 13)]
        },
        benchmark_prices=[
            bar("SPY", date(2026, 1, 2), 100),
            bar("SPY", date(2026, 7, 1), 110),
        ],
    )

    assert observations[0].forward_return == 0.3
    assert observations[0].benchmark_return == 0.1
    assert round(observations[0].excess_return or 0, 6) == 0.2

    summaries = summarize_observations(observations, return_field="excess_return")

    assert round(summaries[0].average_return, 6) == 0.2
