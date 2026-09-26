"""
Postgres storage for the data engine.

Every uploaded dataset gets its own table (`ds_<id>`), plus one row in
`bayan_datasets` holding everything else about it (profile, mapping,
charts, layout). Rows are scoped by `tenant_id` — an opaque key the engine
never interprets (the SaaS layer passes the account id). Every query below
filters on it, so one tenant can never read another's data.

The schema itself (bayan_datasets, learned_synonyms, helper functions) is
owned by Alembic migrations; this module only creates/drops the per-dataset
tables.

Values are stored as they came out of the file — column SQL types follow
the DataFrame's dtypes, not the schema — so a load can't fail because a
column holds something other than what its field name suggests. Charts
cope with that at query time (see queries.py).
"""

import json

import pandas as pd
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor, execute_values

from .db import get_connection

NUMERIC_TYPES = {"BIGINT", "DOUBLE PRECISION"}
TEMPORAL_TYPES = {"TIMESTAMP", "TIMESTAMPTZ"}


def table_name_for(dataset_id: str) -> str:
    return "ds_" + dataset_id.replace("-", "")


def sql_type_for(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE PRECISION"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMPTZ" if getattr(series.dt, "tz", None) is not None else "TIMESTAMP"
    return "TEXT"


def column_types_for(df: pd.DataFrame) -> dict:
    return {col: sql_type_for(df[col]) for col in df.columns}


def _to_db_value(value, sql_type: str):
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if sql_type == "TEXT" and not isinstance(value, str):
        return str(value)
    return value


def _dumps(obj) -> str:
    # profiles/examples can carry numpy / Timestamp values
    return json.dumps(obj, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# datasets
# ---------------------------------------------------------------------------

def create_pending(tenant_id: str, dataset_id: str, filename: str, file_path: str, source_rows: int,
                   profile: dict, suggestion: dict, upload_usage: dict | None = None) -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bayan_datasets
                       (id, tenant_id, filename, file_path, source_rows, profile, suggestion, upload_usage)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (dataset_id, tenant_id, filename, file_path, source_rows,
                 Json(profile, dumps=_dumps), Json(suggestion, dumps=_dumps), Json(upload_usage or {})),
            )
    finally:
        conn.close()


def save_dataset(tenant_id: str, dataset_id: str, df: pd.DataFrame, column_types: dict, mapping: dict,
                 charts: list, hidden_charts: list) -> int:
    """
    (Re)create the dataset's table from `df` and mark it ready — all in
    one transaction. Confirming again replaces the data instead of
    appending, so re-running never double-counts.
    """
    table = table_name_for(dataset_id)
    columns = list(df.columns)
    types = [column_types[c] for c in columns]

    create = sql.SQL("CREATE TABLE {} ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(c), sql.SQL(t)) for c, t in zip(columns, types)
        ),
    )
    insert = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    rows = [
        tuple(_to_db_value(v, t) for v, t in zip(row, types))
        for row in df.itertuples(index=False, name=None)
    ]

    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM bayan_datasets WHERE id = %s AND tenant_id = %s FOR UPDATE",
                (dataset_id, tenant_id),
            )
            if cur.fetchone() is None:
                raise LookupError(dataset_id)
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))
            cur.execute(create)
            if rows:
                execute_values(cur, insert.as_string(cur), rows, page_size=1000)
            cur.execute(
                """UPDATE bayan_datasets
                   SET status = 'ready', loaded_at = now(), mapping = %s, table_name = %s,
                       column_types = %s, row_count = %s, charts = %s, hidden_charts = %s
                   WHERE id = %s AND tenant_id = %s""",
                (Json(mapping), table, Json(column_types), len(rows),
                 Json(charts, dumps=_dumps), Json(hidden_charts), dataset_id, tenant_id),
            )
    finally:
        conn.close()
    return len(rows)


def set_build_usage(tenant_id: str, dataset_id: str, usage: dict) -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE bayan_datasets SET build_usage = %s WHERE id = %s AND tenant_id = %s",
                        (Json(usage), dataset_id, tenant_id))
    finally:
        conn.close()


def table_size_bytes(dataset_id: str) -> int:
    """Actual on-disk size of a dataset's table (data + TOAST + indexes)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(pg_total_relation_size(to_regclass(%s)), 0)", (table_name_for(dataset_id),))
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def get_dataset(tenant_id: str, dataset_id: str):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM bayan_datasets WHERE id = %s AND tenant_id = %s",
                (dataset_id, tenant_id),
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_datasets(tenant_id: str) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, filename, status, created_at, loaded_at, source_rows, row_count,
                          jsonb_array_length(COALESCE(charts, '[]'::jsonb)) AS chart_count
                   FROM bayan_datasets WHERE tenant_id = %s
                   ORDER BY COALESCE(loaded_at, created_at) DESC""",
                (tenant_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def set_hidden_charts(tenant_id: str, dataset_id: str, hidden: list[str]) -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE bayan_datasets SET hidden_charts = %s WHERE id = %s AND tenant_id = %s",
                (Json(hidden), dataset_id, tenant_id),
            )
    finally:
        conn.close()


def delete_dataset(tenant_id: str, dataset_id: str) -> bool:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM bayan_datasets WHERE id = %s AND tenant_id = %s RETURNING id",
                (dataset_id, tenant_id),
            )
            if cur.fetchone() is None:
                return False
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table_name_for(dataset_id))))
            return True
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# learned synonyms (per tenant)
# ---------------------------------------------------------------------------

def load_learned_synonyms(tenant_id: str) -> dict:
    """{field: {normalized synonym}} confirmed by this tenant."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT field, synonym FROM learned_synonyms WHERE tenant_id = %s", (tenant_id,))
            learned: dict = {}
            for field, synonym in cur.fetchall():
                learned.setdefault(field, set()).add(synonym)
            return learned
    finally:
        conn.close()


def learn_synonym(tenant_id: str, normalized: str, field: str) -> None:
    """First confirmation wins: a synonym already learned for another field is left alone."""
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO learned_synonyms (tenant_id, synonym, field) VALUES (%s, %s, %s)
                   ON CONFLICT (tenant_id, synonym) DO NOTHING""",
                (tenant_id, normalized, field),
            )
    finally:
        conn.close()
