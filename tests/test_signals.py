from datetime import date

from stockpicker.models import Holding, SignalType
from stockpicker.signals import generate_position_signals


def holding(ticker: str, shares: float, value: float, weight: float | None = None) -> Holding:
    return Holding(
        filing_id=1,
        manager_id=1,
        accession_number="x",
        report_period=date(2026, 6, 30),
        issuer_name=f"{ticker} Corp",
        cusip=ticker,
        ticker=ticker,
        shares=shares,
        market_value=value,
        portfolio_weight=weight,
    )


def test_generate_position_signals_detects_new_large_add_trim_and_exit():
    current = [
        holding("AAA", 100, 1000, 0.08),
        holding("BBB", 300, 3000, 0.20),
        holding("CCC", 80, 800, 0.04),
    ]
    prior = [
        holding("BBB", 100, 1000, 0.10),
        holding("CCC", 100, 1000, 0.06),
        holding("DDD", 40, 400, 0.03),
    ]

    signals = generate_position_signals(
        manager_id=1,
        report_period=date(2026, 6, 30),
        current_holdings=current,
        prior_holdings=prior,
    )

    by_type = {signal.signal_type for signal in signals}
    assert SignalType.NEW_POSITION in by_type
    assert SignalType.TOP_POSITION in by_type
    assert SignalType.LARGE_ADD in by_type
    assert SignalType.TRIM in by_type
    assert SignalType.EXIT in by_type
