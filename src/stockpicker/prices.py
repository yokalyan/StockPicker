from __future__ import annotations

from datetime import date, timedelta

import yfinance as yf

from stockpicker.models import CostBasisEstimate, PriceBar, WatchlistState


def fetch_price_bars(ticker: str, start: date, end: date) -> list[PriceBar]:
    frame = yf.download(
        ticker,
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    bars: list[PriceBar] = []
    if frame.empty:
        return bars
    for index, row in frame.iterrows():
        bars.append(
            PriceBar(
                ticker=ticker.upper(),
                trade_date=index.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
        )
    return bars


def estimate_cost_basis(
    *,
    ticker: str,
    manager_id: int,
    report_period: date,
    quarter_bars: list[PriceBar],
    current_price: float | None = None,
) -> CostBasisEstimate | None:
    if not quarter_bars:
        return None

    total_volume = sum(max(bar.volume, 0) for bar in quarter_bars)
    if total_volume:
        midpoint = sum(bar.close * bar.volume for bar in quarter_bars) / total_volume
        confidence = "medium"
    else:
        midpoint = sum(bar.close for bar in quarter_bars) / len(quarter_bars)
        confidence = "low"

    lows = sorted(bar.low for bar in quarter_bars)
    highs = sorted(bar.high for bar in quarter_bars)
    low_cost = _percentile(lows, 0.25)
    high_cost = _percentile(highs, 0.75)
    current_vs_midpoint_pct = (
        (current_price - midpoint) / midpoint if current_price is not None and midpoint else None
    )

    status = WatchlistState.NEEDS_UNDERWRITING
    if current_price is not None:
        if current_price < low_cost:
            status = WatchlistState.BELOW_SPONSOR_COST
        elif current_price <= high_cost:
            status = WatchlistState.INSIDE_BUY_ZONE
        else:
            status = WatchlistState.TOO_EXPENSIVE

    return CostBasisEstimate(
        ticker=ticker.upper(),
        manager_id=manager_id,
        report_period=report_period,
        low_cost=round(low_cost, 2),
        high_cost=round(high_cost, 2),
        midpoint=round(midpoint, 2),
        current_price=round(current_price, 2) if current_price is not None else None,
        current_vs_midpoint_pct=(
            round(current_vs_midpoint_pct, 4) if current_vs_midpoint_pct is not None else None
        ),
        confidence=confidence,
        status=status,
    )


def quarter_window(report_period: date) -> tuple[date, date]:
    month = ((report_period.month - 1) // 3) * 3 + 1
    start = date(report_period.year, month, 1)
    return start, report_period


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile on an empty list.")
    index = min(len(values) - 1, max(0, round((len(values) - 1) * pct)))
    return values[index]
