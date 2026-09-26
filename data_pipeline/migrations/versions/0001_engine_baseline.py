"""engine baseline: dataset metadata table + lenient timestamp helper

Matches what the app created on startup before migrations existed, so it is
safe to run on an existing database (IF NOT EXISTS / OR REPLACE).

Revision ID: 0001
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS bayan_datasets (
        id            TEXT PRIMARY KEY,
        filename      TEXT NOT NULL,
        file_path     TEXT NOT NULL,
        status        TEXT NOT NULL DEFAULT 'pending',
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        loaded_at     TIMESTAMPTZ,
        source_rows   INTEGER,
        profile       JSONB NOT NULL,
        suggestion    JSONB NOT NULL,
        mapping       JSONB,
        table_name    TEXT,
        column_types  JSONB,
        row_count     INTEGER,
        charts        JSONB,
        hidden_charts JSONB NOT NULL DEFAULT '[]'::jsonb
    )""")
    # Lenient text -> timestamp for date columns that arrived as text:
    # unparseable values become NULL instead of failing the whole query.
    op.execute("""
    CREATE OR REPLACE FUNCTION bayan_try_timestamp(v TEXT) RETURNS TIMESTAMP AS $$
    BEGIN
        RETURN v::timestamp;
    EXCEPTION WHEN others THEN
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql STABLE""")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS bayan_try_timestamp(TEXT)")
    op.execute("DROP TABLE IF EXISTS bayan_datasets")
