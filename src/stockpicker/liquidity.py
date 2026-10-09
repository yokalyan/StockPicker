from __future__ import annotations

from datetime import date

from stockpicker.models import LiquiditySnapshot, PriceBar


def calculate_liquidity_snapshot(
    ticker: str,
    bars: list[PriceBar],
    as_of: date | None = None,
) -> LiquiditySnapshot:
    ordered = sorted(bars, key=lambda item: item.trade_date)
    if not ordered:
        return LiquiditySnapshot(ticker=ticker.upper(), as_of=as_of or date.today())

    as_of = as_of or ordered[-1].trade_date
    latest_close = ordered[-1].close
    volume_30, dollar_30 = _averages(ordered[-30:])
    volume_90, dollar_90 = _averages(ordered[-90:])
    return LiquiditySnapshot(
        ticker=ticker.upper(),
        as_of=as_of,
        avg_volume_30d=volume_30,
        avg_dollar_volume_30d=dollar_30,
        avg_volume_90d=volume_90,
        avg_dollar_volume_90d=dollar_90,
        latest_close=latest_close,
        liquidity_label=_label(dollar_30),
    )


def _averages(bars: list[PriceBar]) -> tuple[float | None, float | None]:
    if not bars:
        return None, None
    avg_volume = sum(item.volume for item in bars) / len(bars)
    avg_dollar_volume = sum(item.volume * item.close for item in bars) / len(bars)
    return round(avg_volume, 2), round(avg_dollar_volume, 2)


def _label(avg_dollar_volume: float | None) -> str:
    if avg_dollar_volume is None:
        return "unknown"
    if avg_dollar_volume >= 50_000_000:
        return "high"
    if avg_dollar_volume >= 5_000_000:
        return "medium"
    return "low"
