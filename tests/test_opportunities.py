from datetime import date

from stockpicker.models import (
    CostBasisEstimate,
    Manager,
    Signal,
    SignalType,
    StrategyType,
    WatchlistState,
)
from stockpicker.opportunities import rank_opportunities


def test_rank_opportunities_rewards_quality_signal_and_entry_price():
    manager = Manager(
        id=1,
        name="Patient Capital",
        cik="1",
        strategy=StrategyType.SMALL_MID_VALUE,
        quality_score=9,
    )
    signal = Signal(
        manager_id=1,
        ticker="AAA",
        issuer_name="AAA Corp",
        signal_type=SignalType.NEW_POSITION,
        report_period=date(2026, 6, 30),
        current_shares=100,
        prior_shares=0,
        share_change=100,
        pct_change=None,
        current_weight=0.08,
        prior_weight=None,
    )
    estimate = CostBasisEstimate(
        ticker="AAA",
        manager_id=1,
        report_period=date(2026, 6, 30),
        low_cost=10,
        high_cost=12,
        midpoint=11,
        current_price=11.5,
        status=WatchlistState.INSIDE_BUY_ZONE,
    )

    opportunities = rank_opportunities(
        signals=[signal], managers=[manager], cost_estimates=[estimate]
    )

    assert opportunities[0].ticker == "AAA"
    assert opportunities[0].score > 30
    assert opportunities[0].price_status == WatchlistState.INSIDE_BUY_ZONE
