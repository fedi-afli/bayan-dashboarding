"""
Turns a chart spec (from rules.resolve_charts) into SQL against one
dataset's table, runs it, and shapes the result for the dashboard.

All identifiers are composed with psycopg2.sql (never string-formatted)
and every value goes through query parameters.

Columns are stored with whatever type the file had (see storage.py), so
each field is turned into an expression that fits how it's used:
  - measures need a numeric (or boolean) column
  - time axes accept timestamp columns, or text parsed leniently
A chart whose columns can't serve its purpose raises ChartUnavailable and
is simply not offered for that dataset.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from psycopg2 import sql

from .db import get_connection
from .storage import NUMERIC_TYPES, TEMPORAL_TYPES

BLANK_LABEL = "(blank)"
OTHER_LABEL = "Other"
SCATTER_SAMPLE = 500
MAX_GROUPS_FETCHED = 5000

TRUTHY = ("1", "true", "t", "yes", "y", "oui", "o", "نعم")


class ChartUnavailable(ValueError):
    """The dataset's columns can't support this chart."""


class DateFilter:
    def __init__(self, field: Optional[str], date_from: Optional[date], date_to: Optional[date]):
        self.field = field
        self.date_from = date_from
        self.date_to = date_to

    @property
    def active(self) -> bool:
        return bool(self.field and (self.date_from or self.date_to))


class QueryContext:
    def __init__(self, table: str, column_types: dict, date_filter: Optional[DateFilter] = None):
        self.table = sql.Identifier(table)
        self.column_types = column_types
        self.date_filter = date_filter or DateFilter(None, None, None)

    # ---------- column expressions ----------
    def _type(self, field: str) -> str:
        if field not in self.column_types:
            raise ChartUnavailable(f"missing column {field!r}")
        return self.column_types[field]

    def num(self, field: str) -> sql.Composable:
        t = self._type(field)
        if t in NUMERIC_TYPES:
            return sql.Identifier(field)
        if t == "BOOLEAN":
            return sql.SQL("({}::int)").format(sql.Identifier(field))
        raise ChartUnavailable(f"{field!r} isn't numeric ({t})")

    def ts(self, field: str) -> sql.Composable:
        t = self._type(field)
        if t in TEMPORAL_TYPES:
            return sql.Identifier(field)
        if t == "TEXT":
            return sql.SQL("bayan_try_timestamp({})").format(sql.Identifier(field))
        raise ChartUnavailable(f"{field!r} isn't a date ({t})")

    def label(self, field: str) -> sql.Composable:
        self._type(field)
        return sql.SQL("{}::text").format(sql.Identifier(field))

    def metric(self, m: dict) -> sql.Composable:
        agg = m.get("agg")
        if agg == "count":
            return sql.SQL("COUNT(*)")
        if agg == "count_distinct":
            self._type(m["field"])
            return sql.SQL("COUNT(DISTINCT {})").format(sql.Identifier(m["field"]))
        if agg == "sum":
            return sql.SQL("SUM({})").format(self.num(m["field"]))
        if agg == "avg":
            return sql.SQL("AVG({})").format(self.num(m["field"]))
        if agg == "rate":
            self._type(m["field"])
            return sql.SQL("AVG(CASE WHEN lower(trim({}::text)) IN ({}) THEN 1.0 ELSE 0.0 END)").format(
                sql.Identifier(m["field"]), sql.SQL(", ").join(map(sql.Literal, TRUTHY)))
        if agg == "ratio":
            return sql.SQL("({})::float / NULLIF({}, 0)").format(self.metric(m["num"]), self.metric(m["den"]))
        raise ChartUnavailable(f"unknown aggregation {agg!r}")

    def is_additive(self, m: dict) -> bool:
        return m.get("agg") in ("sum", "count")

    # ---------- WHERE ----------
    def where(self, *conditions: sql.Composable) -> tuple[sql.Composable, list]:
        conds = list(conditions)
        params = []
        df = self.date_filter
        if df.active:
            t = self.ts(df.field)
            if df.date_from:
                conds.append(sql.SQL("{} >= %s").format(t))
                params.append(df.date_from)
            if df.date_to:
                conds.append(sql.SQL("{} < %s").format(t))
                params.append(df.date_to + timedelta(days=1))
        if not conds:
            return sql.SQL(""), params
        return sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conds), params


def _num(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return v


def _fetch(query: sql.Composable, params: list) -> list[tuple]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()


def check_chart(spec: dict, ctx: QueryContext) -> None:
    """Raise ChartUnavailable if the dataset's column types can't support `spec`."""
    c = spec["config"]
    if spec["chart_type"] == "scatter":
        ctx.num(c["x"])
        ctx.num(c["y"])
        return
    ctx.metric(c["metric"])
    if c.get("time"):
        ctx.ts(c["time"])
    for p in c.get("period", []):
        ctx.num(p)
    if c.get("dimension"):
        ctx.label(c["dimension"])


# ---------------------------------------------------------------------------
# per chart type
# ---------------------------------------------------------------------------

def _kpi(spec, ctx):
    where, params = ctx.where()
    q = sql.SQL("SELECT {} FROM {}").format(ctx.metric(spec["config"]["metric"]), ctx.table) + where
    rows = _fetch(q, params)
    return {"value": _num(rows[0][0]) if rows else None}


def _granularity(first: datetime, last: datetime) -> str:
    span = (last - first).days
    if span <= 62:
        return "day"
    if span <= 366:
        return "week"
    return "month"


def _time_series(spec, ctx):
    c = spec["config"]
    t = ctx.ts(c["time"])
    where, params = ctx.where(sql.SQL("{} IS NOT NULL").format(t))

    bounds = _fetch(sql.SQL("SELECT MIN({0}), MAX({0}) FROM {1}").format(t, ctx.table) + where, params)
    first, last = bounds[0] if bounds else (None, None)
    if first is None:
        return {"rows": [], "granularity": None}

    grain = _granularity(first, last)
    q = sql.SQL("SELECT date_trunc({}, {}) AS bucket, {} AS value FROM {}").format(
        sql.Literal(grain), t, ctx.metric(c["metric"]), ctx.table
    ) + where + sql.SQL(" GROUP BY 1 ORDER BY 1")

    fmt = "%Y-%m" if grain == "month" else "%Y-%m-%d"
    rows = [{"label": b.strftime(fmt), "value": _num(v)} for b, v in _fetch(q, params)]
    return {"rows": rows, "granularity": grain}


def _period_series(spec, ctx):
    c = spec["config"]
    parts = [ctx.num(p) for p in c["period"]]
    where, params = ctx.where(*[sql.SQL("{} IS NOT NULL").format(p) for p in parts])
    cols = sql.SQL(", ").join(parts)
    idx = sql.SQL(", ").join(sql.SQL(str(i + 1)) for i in range(len(parts)))
    q = sql.SQL("SELECT {}, {} AS value FROM {}").format(cols, ctx.metric(c["metric"]), ctx.table) \
        + where + sql.SQL(" GROUP BY {} ORDER BY {}").format(idx, idx)

    rows = []
    for r in _fetch(q, params):
        *keys, value = r
        label = "-".join(f"{int(k):02d}" if i else str(int(k)) for i, k in enumerate(keys))
        rows.append({"label": label, "value": _num(value)})
    return {"rows": rows, "granularity": "month" if len(parts) > 1 else "year"}


def _breakdown(spec, ctx):
    c = spec["config"]
    top = int(c.get("top", 10))
    where, params = ctx.where()
    q = sql.SQL("SELECT {} AS label, {} AS value FROM {}").format(
        ctx.label(c["dimension"]), ctx.metric(c["metric"]), ctx.table
    ) + where + sql.SQL(" GROUP BY 1 LIMIT {}").format(sql.Literal(MAX_GROUPS_FETCHED))

    groups = [(label if label not in (None, "") else BLANK_LABEL, _num(v) or 0) for label, v in _fetch(q, params)]
    groups.sort(key=lambda g: g[1], reverse=True)

    shown, rest = groups[:top], groups[top:]
    rows = [{"label": str(l), "value": v} for l, v in shown]
    if rest and ctx.is_additive(c["metric"]):
        rows.append({"label": OTHER_LABEL, "value": sum(v for _, v in rest), "is_other": True})
    return {"rows": rows, "total_groups": len(groups), "hidden_groups": len(rest)}


def _scatter(spec, ctx):
    c = spec["config"]
    x, y = ctx.num(c["x"]), ctx.num(c["y"])
    where, params = ctx.where(sql.SQL("{} IS NOT NULL").format(x), sql.SQL("{} IS NOT NULL").format(y))
    # random sample, not "the first 500 rows of the file"
    q = sql.SQL("SELECT {}, {} FROM {}").format(x, y, ctx.table) + where \
        + sql.SQL(" ORDER BY random() LIMIT {}").format(sql.Literal(SCATTER_SAMPLE))
    return {"points": [[_num(a), _num(b)] for a, b in _fetch(q, params)]}


def run_chart_query(spec: dict, ctx: QueryContext) -> dict:
    kind = spec["chart_type"]
    c = spec["config"]
    if kind == "kpi":
        return _kpi(spec, ctx)
    if kind == "line":
        return _time_series(spec, ctx) if c.get("time") else _period_series(spec, ctx)
    if kind in ("bar", "donut"):
        return _breakdown(spec, ctx)
    if kind == "scatter":
        return _scatter(spec, ctx)
    raise ChartUnavailable(f"unknown chart type {kind!r}")


def date_bounds(ctx: QueryContext, field: str) -> tuple[Optional[str], Optional[str]]:
    t = ctx.ts(field)
    rows = _fetch(sql.SQL("SELECT MIN({0})::date, MAX({0})::date FROM {1}").format(t, ctx.table), [])
    lo, hi = rows[0] if rows else (None, None)
    return (lo.isoformat() if lo else None, hi.isoformat() if hi else None)
