from datetime import date, timedelta

from stockpicker.liquidity import calculate_liquidity_snapshot
from stockpicker.models import PriceBar


def bar(day: date, close: float, volume: int) -> PriceBar:
    return PriceBar(
        ticker="ACME",
        trade_date=day,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
    )


def test_calculate_liquidity_snapshot_labels_average_dollar_volume():
    start = date(2026, 1, 1)
    bars = [bar(start + timedelta(days=index), 10, 600_000) for index in range(90)]

    snapshot = calculate_liquidity_snapshot("acme", bars)

    assert snapshot.ticker == "ACME"
    assert snapshot.as_of == date(2026, 3, 31)
    assert snapshot.avg_volume_30d == 600_000
    assert snapshot.avg_dollar_volume_30d == 6_000_000
    assert snapshot.liquidity_label == "medium"


def test_calculate_liquidity_snapshot_handles_empty_history():
    snapshot = calculate_liquidity_snapshot("acme", [], as_of=date(2026, 10, 9))

    assert snapshot.as_of == date(2026, 10, 9)
    assert snapshot.liquidity_label == "unknown"
