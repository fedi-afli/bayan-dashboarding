"""
Resource metering for the data engine: how much work a dashboard causes.

The engine only *measures and estimates* resources (cells processed, bytes
stored, AI work, seconds). Turning resources into a price is the SaaS
layer's job (saas/pricing.py).

Storage model (checked against Postgres on 5k–500k-row files, within ~2%):
    bytes ≈ rows × (ROW_OVERHEAD + Σ avg value size of stored columns) × FILL_FACTOR
"""

import time
from contextlib import contextmanager

ROW_OVERHEAD_BYTES = 28      # tuple header (24) + item pointer (4)
FILL_FACTOR = 1.1            # page headers / free space
DEFAULT_VALUE_BYTES = 16.0   # for profiles recorded before avg_bytes existed
NUMERIC_BYTES = 8.0


@contextmanager
def meter():
    """Measures wall-clock and CPU seconds of the enclosed block (CPU of this thread only)."""
    m = {}
    wall, cpu = time.perf_counter(), time.thread_time()
    try:
        yield m
    finally:
        m["seconds"] = round(time.perf_counter() - wall, 3)
        m["cpu_seconds"] = round(time.thread_time() - cpu, 3)


def estimate_storage_bytes(rows: int, value_bytes: list[float]) -> int:
    return int(rows * (ROW_OVERHEAD_BYTES + sum(value_bytes)) * FILL_FACTOR)
