from __future__ import annotations

import csv
from pathlib import Path

from stockpicker.models import Manager, StrategyType

STRATEGY_DEFAULTS: dict[StrategyType, dict[str, float | int | None]] = {
    StrategyType.ACTIVIST: {
        "quality_score": 7.5,
        "concentration_score": 8.0,
        "turnover_score": 4.0,
        "typical_holding_period_months": 24,
    },
    StrategyType.CONCENTRATED_FUNDAMENTAL: {
        "quality_score": 8.0,
        "concentration_score": 8.0,
        "turnover_score": 3.5,
        "typical_holding_period_months": 36,
    },
    StrategyType.QUALITY_COMPOUNDER: {
        "quality_score": 8.0,
        "concentration_score": 7.0,
        "turnover_score": 3.0,
        "typical_holding_period_months": 48,
    },
    StrategyType.SMALL_MID_VALUE: {
        "quality_score": 8.0,
        "concentration_score": 7.5,
        "turnover_score": 4.0,
        "typical_holding_period_months": 36,
    },
    StrategyType.EVENT_DRIVEN: {
        "quality_score": 5.5,
        "concentration_score": 5.0,
        "turnover_score": 7.0,
        "typical_holding_period_months": 12,
    },
    StrategyType.MULTI_STRATEGY: {
        "quality_score": 3.0,
        "concentration_score": 3.0,
        "turnover_score": 8.0,
        "typical_holding_period_months": 6,
    },
    StrategyType.QUANT: {
        "quality_score": 2.0,
        "concentration_score": 2.0,
        "turnover_score": 9.0,
        "typical_holding_period_months": 3,
    },
    StrategyType.MACRO: {
        "quality_score": 3.0,
        "concentration_score": 3.0,
        "turnover_score": 8.0,
        "typical_holding_period_months": 6,
    },
    StrategyType.CREDIT: {
        "quality_score": 3.5,
        "concentration_score": 4.0,
        "turnover_score": 6.0,
        "typical_holding_period_months": 12,
    },
    StrategyType.PASSIVE: {
        "quality_score": 1.0,
        "concentration_score": 1.0,
        "turnover_score": 2.0,
        "typical_holding_period_months": None,
    },
    StrategyType.EXCLUDED: {
        "quality_score": 0.0,
        "concentration_score": 0.0,
        "turnover_score": 10.0,
        "typical_holding_period_months": None,
    },
    StrategyType.UNKNOWN: {
        "quality_score": 5.0,
        "concentration_score": 5.0,
        "turnover_score": 5.0,
        "typical_holding_period_months": None,
    },
}


def load_manager_universe_csv(path: str | Path) -> list[Manager]:
    """Load a curated manager universe from CSV.

    Required columns: name, cik.
    Optional columns: strategy, quality_score, concentration_score, turnover_score,
    typical_holding_period_months, is_active, notes.
    """

    managers: list[Manager] = []
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"name", "cik"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        for row in reader:
            name = (row.get("name") or "").strip()
            cik = (row.get("cik") or "").strip()
            if not name or not cik:
                continue
            strategy = _strategy(row.get("strategy"))
            defaults = STRATEGY_DEFAULTS[strategy]
            managers.append(
                Manager(
                    name=name,
                    cik=cik,
                    strategy=strategy,
                    quality_score=_float(row.get("quality_score"), defaults["quality_score"]),
                    concentration_score=_float(
                        row.get("concentration_score"), defaults["concentration_score"]
                    ),
                    turnover_score=_float(row.get("turnover_score"), defaults["turnover_score"]),
                    typical_holding_period_months=_int(
                        row.get("typical_holding_period_months"),
                        defaults["typical_holding_period_months"],
                    ),
                    is_active=_bool(row.get("is_active"), True),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return managers


def _strategy(value: str | None) -> StrategyType:
    if not value:
        return StrategyType.UNKNOWN
    try:
        return StrategyType(value.strip())
    except ValueError:
        return StrategyType.UNKNOWN


def _float(value: str | None, default: float | int | None) -> float:
    if value is None or value == "":
        return float(default or 0.0)
    return float(value)


def _int(value: str | None, default: float | int | None) -> int | None:
    if value is None or value == "":
        return int(default) if default is not None else None
    return int(value)


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "active"}
