from __future__ import annotations

import csv
from pathlib import Path

from stockpicker.models import SecurityMapping


def load_security_mappings_csv(path: str | Path, source: str = "csv") -> list[SecurityMapping]:
    """Load CUSIP-to-ticker mappings from a CSV.

    Required columns: cusip, ticker.
    Optional columns: issuer_name, source.
    """

    mappings: list[SecurityMapping] = []
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"cusip", "ticker"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        for row in reader:
            cusip = (row.get("cusip") or "").strip().upper()
            ticker = (row.get("ticker") or "").strip().upper()
            if not cusip or not ticker:
                continue
            mappings.append(
                SecurityMapping(
                    cusip=cusip,
                    ticker=ticker,
                    issuer_name=(row.get("issuer_name") or "").strip() or None,
                    source=(row.get("source") or "").strip() or source,
                )
            )
    return mappings
