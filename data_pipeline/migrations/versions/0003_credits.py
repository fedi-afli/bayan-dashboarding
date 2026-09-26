"""credits: ledger, dashboard charges, payments

- app.credit_ledger: every balance change, append-only. accounts.credit_balance
  is a cached sum kept in the same transaction as each ledger insert.
- app.dashboard_charges: which datasets have been paid for (rebuilds are free,
  and a double click can't charge twice).
- app.payments: one row per top-up attempt; provider-agnostic.
- app.payment_notifications: raw log of every provider callback, for support.

Revision ID: 0003
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE app.credit_ledger (
        id            BIGSERIAL PRIMARY KEY,
        account_id    UUID NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
        delta         INTEGER NOT NULL CHECK (delta <> 0),
        balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
        kind          TEXT NOT NULL CHECK (kind IN ('welcome', 'topup', 'dashboard', 'refund', 'adjustment')),
        ref           TEXT NOT NULL,
        description   TEXT NOT NULL,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX credit_ledger_account_idx ON app.credit_ledger (account_id, created_at DESC)")
    # a payment / welcome bonus / refund can only ever be credited once
    op.execute("""CREATE UNIQUE INDEX credit_ledger_once ON app.credit_ledger (kind, ref)
                  WHERE kind IN ('welcome', 'topup', 'refund')""")

    op.execute("""
    CREATE TABLE app.dashboard_charges (
        dataset_id TEXT PRIMARY KEY,                -- engine dataset id (no FK across the seam)
        account_id UUID NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
        ledger_id  BIGINT NOT NULL REFERENCES app.credit_ledger(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")

    op.execute("""
    CREATE TABLE app.payments (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        account_id      UUID NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
        provider        TEXT NOT NULL,
        provider_ref    TEXT,
        pack_code       TEXT NOT NULL,
        credits         INTEGER NOT NULL CHECK (credits > 0),
        amount_millimes BIGINT NOT NULL CHECK (amount_millimes > 0),
        currency        TEXT NOT NULL DEFAULT 'TND',
        status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed')),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        paid_at         TIMESTAMPTZ,
        UNIQUE (provider, provider_ref)
    )""")
    op.execute("CREATE INDEX payments_account_idx ON app.payments (account_id, created_at DESC)")

    op.execute("""
    CREATE TABLE app.payment_notifications (
        id           BIGSERIAL PRIMARY KEY,
        provider     TEXT NOT NULL,
        provider_ref TEXT,
        payment_id   UUID,
        outcome      TEXT NOT NULL,
        detail       JSONB,
        received_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.payment_notifications")
    op.execute("DROP TABLE IF EXISTS app.payments")
    op.execute("DROP TABLE IF EXISTS app.dashboard_charges")
    op.execute("DROP TABLE IF EXISTS app.credit_ledger")
