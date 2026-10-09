from datetime import date

from stockpicker.crowding import crowding_snapshot
from stockpicker.models import Manager, Signal, SignalType, StrategyType


def signal(manager_id: int, signal_type: SignalType) -> Signal:
    return Signal(
        manager_id=manager_id,
        ticker="ACME",
        issuer_name="Acme Corp",
        signal_type=signal_type,
        report_period=date(2026, 6, 30),
        current_shares=100,
        prior_shares=0,
        share_change=100,
        pct_change=None,
        current_weight=0.05,
        prior_weight=None,
    )


def test_crowding_snapshot_labels_confirmed_multi_manager_buying():
    managers = {
        1: Manager(id=1, name="A", cik="1", strategy=StrategyType.SMALL_MID_VALUE),
        2: Manager(id=2, name="B", cik="2", strategy=StrategyType.ACTIVIST),
    }

    snapshot = crowding_snapshot(
        ticker="ACME",
        signals=[
            signal(1, SignalType.NEW_POSITION),
            signal(2, SignalType.LARGE_ADD),
        ],
        managers_by_id=managers,
    )

    assert snapshot.label == "confirmed"
    assert snapshot.adding_count == 2
    assert snapshot.score > 0
