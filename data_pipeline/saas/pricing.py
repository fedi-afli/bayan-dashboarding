"""
How many credits a dashboard costs, from the resources it consumes.

The engine reports resource drivers (engine.service.Engine.estimate_build);
this module turns them into credits. Price = sum of the lines below, rounded
up to whole credits, never less than MINIMUM.

Rates were calibrated on this server (see README "Credits"):
  - building costs ≈ 1.8 µs of CPU per cell and reading ≈ 0.2 µs
      -> PROCESSING: 1 credit per million cells stored
  - Postgres keeps ≈ 13 bytes per cell, re-read on every dashboard view
      -> STORAGE: 1 credit per 25 MB kept
  - the AI matcher needs ≈ 0.8 s of GPU per column it analyses
      -> AI: 0.25 credit per column sent to the AI
  - fixed work per dashboard (chart selection, metadata, first render)
      -> BASE: 0.5 credit
Every build also records what it *actually* used (app.dashboard_usage), so
these rates can be re-checked against real traffic.

The price is quoted before building and that quote is what's charged — the
user always sees the price before clicking, and it never depends on how busy
the server happened to be.
"""

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Rates:
    base: float = 0.5
    cells_per_credit: int = 1_000_000
    mb_per_credit: float = 25.0
    per_ai_column: float = 0.25
    minimum: int = 1


RATES = Rates()


def quote(drivers: dict, rates: Rates = RATES) -> dict:
    """
    drivers: {"rows", "columns", "cells", "storage_bytes", "ai_columns"} from the engine.
    Returns {"credits", "exact", "lines": [{"key", "label", "detail", "amount"}], "drivers"}.
    """
    rows, columns, cells = drivers["rows"], drivers["columns"], drivers["cells"]
    mb = drivers["storage_bytes"] / 1_000_000
    ai_columns = drivers.get("ai_columns", 0)

    lines = [
        {"key": "base", "label": "Dashboard setup", "detail": "charts, layout, first computation",
         "amount": rates.base},
        {"key": "processing", "label": "Data processed",
         "detail": f"{rows:,} rows × {columns} column{'s' if columns != 1 else ''} = {cells:,} cells",
         "amount": cells / rates.cells_per_credit},
        {"key": "storage", "label": "Storage", "detail": f"≈ {_fmt_mb(mb)} kept for your dashboard",
         "amount": mb / rates.mb_per_credit},
    ]
    if ai_columns:
        lines.append({"key": "ai", "label": "AI column matching",
                      "detail": f"{ai_columns} column{'s' if ai_columns != 1 else ''} analysed",
                      "amount": ai_columns * rates.per_ai_column})

    exact = sum(line["amount"] for line in lines)
    credits = max(rates.minimum, math.ceil(round(exact, 6)))
    for line in lines:
        line["amount"] = round(line["amount"], 2)
    return {"credits": credits, "exact": round(exact, 2), "lines": lines, "drivers": dict(drivers)}


def examples(rates: Rates = RATES) -> list[dict]:
    """Typical files and what they cost, for the pricing explanation in the app."""
    samples = [
        ("Small shop export", 2_000, 8, 0),
        ("A year of sales", 50_000, 10, 0),
        ("Large history", 200_000, 12, 0),
        ("Very large file", 500_000, 15, 0),
    ]
    out = []
    for label, rows, cols, ai in samples:
        drivers = {"rows": rows, "columns": cols, "cells": rows * cols,
                   "storage_bytes": int(rows * (28 + cols * 12) * 1.1), "ai_columns": ai}
        out.append({"label": label, "rows": rows, "columns": cols, "credits": quote(drivers, rates)["credits"]})
    return out


def describe(rates: Rates = RATES) -> dict:
    return {**asdict(rates), "examples": examples(rates)}


def _fmt_mb(mb: float) -> str:
    return f"{mb * 1000:.0f} KB" if mb < 1 else f"{mb:.1f} MB"
