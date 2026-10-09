from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import yfinance as yf

from stockpicker.models import FundamentalSnapshot

SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def fetch_yfinance_snapshot(ticker: str) -> FundamentalSnapshot:
    try:
        info = yf.Ticker(ticker).get_info()
    except Exception:
        info = {}
    return FundamentalSnapshot(
        ticker=ticker.upper(),
        as_of=date.today(),
        market_cap=_float(info.get("marketCap")),
        enterprise_value=_float(info.get("enterpriseValue")),
        sector=info.get("sector"),
        industry=info.get("industry"),
        revenue=_float(info.get("totalRevenue")),
        net_income=_float(info.get("netIncomeToCommon")),
        operating_income=_float(info.get("operatingIncome")),
        cash=_float(info.get("totalCash")),
        debt=_float(info.get("totalDebt")),
        source="yfinance",
    )


def fetch_sec_company_facts(cik: str, user_agent: str) -> dict[str, Any]:
    if "@" not in user_agent:
        raise ValueError("SEC requests require a descriptive user agent with contact email.")
    response = httpx.get(
        SEC_COMPANY_FACTS_URL.format(cik=cik.zfill(10)),
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def sec_snapshot_from_company_facts(
    *,
    ticker: str,
    facts: dict[str, Any],
) -> FundamentalSnapshot:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    return FundamentalSnapshot(
        ticker=ticker.upper(),
        as_of=date.today(),
        revenue=_latest_fact(
            us_gaap,
            ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
        ),
        net_income=_latest_fact(us_gaap, ["NetIncomeLoss"]),
        operating_income=_latest_fact(us_gaap, ["OperatingIncomeLoss"]),
        cash=_latest_fact(us_gaap, ["CashAndCashEquivalentsAtCarryingValue"]),
        debt=_latest_fact(us_gaap, ["LongTermDebt", "LongTermDebtAndFinanceLeaseObligations"]),
        source="sec_companyfacts",
    )


def merge_fundamentals(
    primary: FundamentalSnapshot, secondary: FundamentalSnapshot
) -> FundamentalSnapshot:
    data = primary.model_dump()
    secondary_data = secondary.model_dump()
    for key, value in secondary_data.items():
        if key in {"ticker", "as_of", "source"}:
            continue
        if data.get(key) is None and value is not None:
            data[key] = value
    data["source"] = f"{primary.source}+{secondary.source}"
    return FundamentalSnapshot(**data)


def _latest_fact(us_gaap: dict[str, Any], names: list[str]) -> float | None:
    for name in names:
        units = us_gaap.get(name, {}).get("units", {})
        candidates = []
        for unit_values in units.values():
            candidates.extend(unit_values)
        candidates = [item for item in candidates if "val" in item and "end" in item]
        if candidates:
            latest = sorted(candidates, key=lambda item: item["end"])[-1]
            return _float(latest["val"])
    return None


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
