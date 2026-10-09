from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StrategyType(StrEnum):
    ACTIVIST = "activist"
    CONCENTRATED_FUNDAMENTAL = "concentrated_fundamental"
    QUALITY_COMPOUNDER = "quality_compounder"
    SMALL_MID_VALUE = "small_mid_value"
    EVENT_DRIVEN = "event_driven"
    MULTI_STRATEGY = "multi_strategy"
    QUANT = "quant"
    MACRO = "macro"
    CREDIT = "credit"
    PASSIVE = "passive"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


class FilingType(StrEnum):
    FORM_13F = "13F-HR"
    FORM_13F_AMENDMENT = "13F-HR/A"
    SCHEDULE_13D = "SC 13D"
    SCHEDULE_13D_AMENDMENT = "SC 13D/A"
    SCHEDULE_13G = "SC 13G"
    SCHEDULE_13G_AMENDMENT = "SC 13G/A"


class SignalType(StrEnum):
    NEW_POSITION = "new_position"
    ADD = "add"
    LARGE_ADD = "large_add"
    TRIM = "trim"
    LARGE_TRIM = "large_trim"
    EXIT = "exit"
    TOP_POSITION = "top_position"
    MULTI_QUARTER_ACCUMULATION = "multi_quarter_accumulation"
    BENEFICIAL_OWNER = "beneficial_owner"
    ACTIVIST = "activist"


class WatchlistState(StrEnum):
    TOO_EXPENSIVE = "interesting_too_expensive"
    INSIDE_BUY_ZONE = "inside_buy_zone"
    BELOW_SPONSOR_COST = "below_sponsor_cost"
    NEEDS_UNDERWRITING = "needs_underwriting"
    UNDER_RESEARCH = "under_research"
    REJECTED = "rejected"
    OWNED = "owned"
    MONITOR_ONLY = "monitor_only"


class Manager(BaseModel):
    id: int | None = None
    name: str
    cik: str
    strategy: StrategyType = StrategyType.UNKNOWN
    quality_score: float = Field(default=5.0, ge=0, le=10)
    concentration_score: float = Field(default=5.0, ge=0, le=10)
    turnover_score: float = Field(default=5.0, ge=0, le=10)
    typical_holding_period_months: int | None = None
    is_active: bool = True
    notes: str = ""

    @property
    def normalized_cik(self) -> str:
        return self.cik.zfill(10)


class Filing(BaseModel):
    id: int | None = None
    manager_id: int
    accession_number: str
    filing_type: FilingType | str
    filing_date: date
    report_period: date | None = None
    document_url: str
    raw_text: str | None = None
    parsed_at: datetime | None = None


class Holding(BaseModel):
    id: int | None = None
    filing_id: int
    manager_id: int
    accession_number: str
    report_period: date
    issuer_name: str
    cusip: str | None = None
    ticker: str | None = None
    shares: float
    market_value: float
    put_call: str | None = None
    portfolio_weight: float | None = None


class Signal(BaseModel):
    id: int | None = None
    manager_id: int
    ticker: str
    issuer_name: str
    signal_type: SignalType
    report_period: date
    current_shares: float
    prior_shares: float
    share_change: float
    pct_change: float | None
    current_weight: float | None
    prior_weight: float | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PriceBar(BaseModel):
    ticker: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class CostBasisEstimate(BaseModel):
    ticker: str
    manager_id: int
    report_period: date
    low_cost: float
    high_cost: float
    midpoint: float
    current_price: float | None = None
    current_vs_midpoint_pct: float | None = None
    confidence: str = "low"
    status: WatchlistState = WatchlistState.NEEDS_UNDERWRITING
    method: str = "quarter_vwap_range"


class Opportunity(BaseModel):
    ticker: str
    issuer_name: str
    report_period: date
    score: float
    signal_count: int
    managers: list[str]
    best_signal: SignalType
    price_status: WatchlistState
    rationale: list[str]


class BeneficialOwnershipFiling(BaseModel):
    id: int | None = None
    manager_id: int
    accession_number: str
    filing_type: FilingType | str
    filing_date: date
    issuer_name: str
    ticker: str | None = None
    ownership_pct: float | None = None
    shares_owned: float | None = None
    price_low: float | None = None
    price_high: float | None = None
    purpose: str | None = None
    document_url: str
