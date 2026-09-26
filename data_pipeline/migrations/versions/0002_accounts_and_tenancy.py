"""accounts & users (SaaS layer, schema `app`); tenant_id on engine data

- app.accounts / app.users: who logs in, and which account (tenant) they belong to
- bayan_datasets.tenant_id: every dataset belongs to one account
- learned_synonyms: confirmed column names, per tenant (was a shared JSON file)

Data created before accounts existed goes to a "Default workspace" account;
the first user to log in adopts it (see saas/accounts.py).

Revision ID: 0002
"""
import json
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

DEFAULT_ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"
LEGACY_SYNONYMS = Path(__file__).resolve().parents[2] / "engine" / "matchers" / "learned_synonyms.json"


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    op.execute("""
    CREATE TABLE app.accounts (
        id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name           TEXT NOT NULL,
        credit_balance INTEGER NOT NULL DEFAULT 0 CHECK (credit_balance >= 0),
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("""
    CREATE TABLE app.users (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        idp_subject  TEXT NOT NULL UNIQUE,          -- `sub` claim from the identity provider
        email        TEXT,
        display_name TEXT,
        account_id   UUID NOT NULL REFERENCES app.accounts(id) ON DELETE RESTRICT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX users_account_idx ON app.users (account_id)")
    op.execute(f"INSERT INTO app.accounts (id, name) VALUES ('{DEFAULT_ACCOUNT_ID}', 'Default workspace')")

    # engine side: opaque tenant key, no foreign key across the seam
    op.execute("ALTER TABLE bayan_datasets ADD COLUMN tenant_id TEXT")
    op.execute(f"UPDATE bayan_datasets SET tenant_id = '{DEFAULT_ACCOUNT_ID}'")
    op.execute("ALTER TABLE bayan_datasets ALTER COLUMN tenant_id SET NOT NULL")
    op.execute("CREATE INDEX bayan_datasets_tenant_idx ON bayan_datasets (tenant_id, status)")
    op.execute("""
    CREATE TABLE learned_synonyms (
        tenant_id  TEXT NOT NULL,
        synonym    TEXT NOT NULL,                   -- normalized column name
        field      TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, synonym)
    )""")

    # carry over what the old shared JSON file had learned
    if LEGACY_SYNONYMS.exists():
        from engine.matchers.synonym_store import get_static_synonyms, is_learnable

        static = get_static_synonyms()
        conn = op.get_bind()
        for field, names in json.loads(LEGACY_SYNONYMS.read_text(encoding="utf-8")).items():
            for name in names:
                key = is_learnable(name, static)
                if key:
                    conn.execute(
                        text("INSERT INTO learned_synonyms (tenant_id, synonym, field) VALUES (:t, :s, :f) "
                             "ON CONFLICT DO NOTHING"),
                        {"t": DEFAULT_ACCOUNT_ID, "s": key, "f": field},
                    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS learned_synonyms")
    op.execute("DROP INDEX IF EXISTS bayan_datasets_tenant_idx")
    op.execute("ALTER TABLE bayan_datasets DROP COLUMN IF EXISTS tenant_id")
    op.execute("DROP TABLE IF EXISTS app.users")
    op.execute("DROP TABLE IF EXISTS app.accounts")
