from datetime import date

from stockpicker.models import PriceBar, WatchlistState
from stockpicker.prices import estimate_cost_basis, quarter_window


def test_estimate_cost_basis_classifies_buy_zone():
    bars = [
        PriceBar(
            ticker="AAA",
            trade_date=date(2026, 4, 1),
            open=10,
            high=12,
            low=9,
            close=11,
            volume=100,
        ),
        PriceBar(
            ticker="AAA",
            trade_date=date(2026, 5, 1),
            open=12,
            high=14,
            low=11,
            close=13,
            volume=300,
        ),
        PriceBar(
            ticker="AAA",
            trade_date=date(2026, 6, 1),
            open=13,
            high=15,
            low=12,
            close=14,
            volume=600,
        ),
    ]

    estimate = estimate_cost_basis(
        ticker="AAA",
        manager_id=1,
        report_period=date(2026, 6, 30),
        quarter_bars=bars,
        current_price=13,
    )

    assert estimate is not None
    assert estimate.midpoint == 13.4
    assert estimate.status == WatchlistState.INSIDE_BUY_ZONE


def test_quarter_window():
    assert quarter_window(date(2026, 9, 30)) == (date(2026, 7, 1), date(2026, 9, 30))
