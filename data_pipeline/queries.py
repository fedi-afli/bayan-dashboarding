"""
Turns a resolved chart config (from rules.resolve_charts_from_mapping) into
an actual SQL query against the loaded table, and runs it.
"""

from typing import Optional
from db import get_connection

AGG_MAP = {
    "sum": "SUM",
    "avg": "AVG",
    "mean": "AVG",
    "count": "COUNT",
}

# Only these characters are allowed in a column/table name used to build
# the query — since these come from our own schema field names (not raw
# user input), this is a sanity check against accidental injection, not a
# substitute for validating the mapping itself.
import re
_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _safe(identifier: str) -> str:
    if not _SAFE_IDENTIFIER.match(identifier):
        raise ValueError(f"Unsafe identifier in chart config: {identifier!r}")
    return identifier


def build_chart_query(config: dict, table: str = "sales") -> str:
    table = _safe(table)
    dim = config.get("x") or config.get("group_by")
    measure = config.get("y") or config.get("measure")
    agg_key = config.get("agg", "count")
    agg_sql = AGG_MAP.get(agg_key, "COUNT")

    if dim is None:
        # KPI-style chart with no dimension to group by — single aggregate value
        if measure is None:
            raise ValueError("Chart config has neither a dimension nor a measure.")
        measure = _safe(measure)
        return f"SELECT {agg_sql}({measure}) AS value FROM {table}"

    dim = _safe(dim)

    if measure:
        measure = _safe(measure)
        select = f"{dim}, {agg_sql}({measure}) AS value"
    else:
        select = f"{dim}, COUNT(*) AS value"

    query = f"SELECT {select} FROM {table} GROUP BY {dim} ORDER BY {dim}"

    if config.get("sort") == "desc":
        query = f"SELECT {select} FROM {table} GROUP BY {dim} ORDER BY value DESC"

    limit = config.get("limit")
    if limit:
        query += f" LIMIT {int(limit)}"

    return query


def run_chart_query(config: dict, table: str = "sales") -> list[dict]:
    query = build_chart_query(config, table)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()