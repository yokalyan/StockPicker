from datetime import date

from stockpicker.dashboard import render_dashboard
from stockpicker.models import Opportunity, SignalType, WatchlistState


def test_render_dashboard_includes_opportunity_rows():
    html = render_dashboard(
        [
            Opportunity(
                ticker="ACME",
                issuer_name="Acme Corp",
                report_period=date(2026, 6, 30),
                score=55.2,
                signal_count=2,
                managers=["Patient Capital"],
                best_signal=SignalType.NEW_POSITION,
                price_status=WatchlistState.INSIDE_BUY_ZONE,
                rationale=["new position from Patient Capital"],
            )
        ]
    )

    assert "StockPicker Dashboard" in html
    assert "ACME" in html
    assert "inside buy zone" in html
