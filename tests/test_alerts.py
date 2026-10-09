from datetime import date

from stockpicker.alerts import alerts_from_opportunities, watchlist_items_from_opportunities
from stockpicker.models import (
    AlertType,
    Opportunity,
    SignalType,
    WatchlistItem,
    WatchlistState,
)


def opportunity(status: WatchlistState) -> Opportunity:
    return Opportunity(
        ticker="ACME",
        issuer_name="Acme Corp",
        report_period=date(2026, 6, 30),
        score=42,
        signal_count=1,
        managers=["Patient Capital"],
        best_signal=SignalType.NEW_POSITION,
        price_status=status,
        rationale=["new position from Patient Capital"],
    )


def test_alerts_flag_new_actionable_opportunity():
    alerts = alerts_from_opportunities(
        [opportunity(WatchlistState.INSIDE_BUY_ZONE)],
        existing_watchlist={},
    )

    alert_types = {alert.alert_type for alert in alerts}
    assert AlertType.NEW_SIGNAL in alert_types
    assert AlertType.ENTERED_BUY_ZONE in alert_types


def test_alerts_flag_price_zone_change_below_cost():
    alerts = alerts_from_opportunities(
        [opportunity(WatchlistState.BELOW_SPONSOR_COST)],
        existing_watchlist={
            "ACME": WatchlistItem(
                ticker="ACME",
                last_price_status=WatchlistState.TOO_EXPENSIVE,
            )
        },
    )

    alert_types = {alert.alert_type for alert in alerts}
    assert AlertType.PRICE_ZONE_CHANGED in alert_types
    assert AlertType.BELOW_SPONSOR_COST in alert_types


def test_watchlist_items_from_opportunities_set_operating_state():
    items = watchlist_items_from_opportunities([opportunity(WatchlistState.TOO_EXPENSIVE)])

    assert items[0].ticker == "ACME"
    assert items[0].state == WatchlistState.MONITOR_ONLY
    assert items[0].last_price_status == WatchlistState.TOO_EXPENSIVE
