from datetime import date

from stockpicker.models import (
    FundamentalSnapshot,
    LiquiditySnapshot,
    Opportunity,
    Signal,
    SignalType,
    WatchlistState,
)
from stockpicker.research import render_research_packet


def test_render_research_packet_contains_decision_scaffold():
    opportunity = Opportunity(
        ticker="AAA",
        issuer_name="AAA Corp",
        report_period=date(2026, 6, 30),
        score=42,
        signal_count=1,
        managers=["Patient Capital"],
        best_signal=SignalType.NEW_POSITION,
        price_status=WatchlistState.INSIDE_BUY_ZONE,
        rationale=["new_position from Patient Capital"],
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

    packet = render_research_packet(
        opportunity,
        [signal],
        [],
        fundamental=FundamentalSnapshot(
            ticker="AAA",
            as_of=date(2026, 10, 9),
            market_cap=1_000_000_000,
            sector="Industrials",
            industry="Specialty Machinery",
            revenue=500_000_000,
        ),
        liquidity=LiquiditySnapshot(
            ticker="AAA",
            as_of=date(2026, 10, 9),
            avg_dollar_volume_30d=7_500_000,
            avg_dollar_volume_90d=6_500_000,
            liquidity_label="medium",
        ),
    )

    assert "# AAA Research Packet" in packet
    assert "## Crowding And Ownership" in packet
    assert "## Company Snapshot To Fill" in packet
    assert "## Underwriting Questions" in packet
    assert "## Decision Log" in packet
    assert "Market cap: $1,000,000,000" in packet
    assert "Industrials / Specialty Machinery" in packet
    assert "30d average dollar volume: $7,500,000" in packet
