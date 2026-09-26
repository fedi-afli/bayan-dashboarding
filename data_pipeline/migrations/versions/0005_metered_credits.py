"""credits priced from resource usage

- app.dashboard_charges: now tracks how many credits a dashboard has been paid
  in total (a rebuild that needs more resources only pays the difference).
- app.dashboard_usage: one row per successful build — the quote that was
  charged next to the resources actually measured, to recalibrate pricing.

Revision ID: 0005
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.dashboard_charges ADD COLUMN credits_paid INTEGER NOT NULL DEFAULT 0")
    op.execute("""UPDATE app.dashboard_charges c SET credits_paid = -l.delta
                  FROM app.credit_ledger l WHERE l.id = c.ledger_id""")
    op.execute("ALTER TABLE app.dashboard_charges DROP COLUMN ledger_id")
    op.execute("ALTER TABLE app.dashboard_charges ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE app.dashboard_charges ADD CONSTRAINT dashboard_charges_paid_positive CHECK (credits_paid > 0)")

    op.execute("""
    CREATE TABLE app.dashboard_usage (
        id              BIGSERIAL PRIMARY KEY,
        dataset_id      TEXT NOT NULL,
        account_id      UUID NOT NULL REFERENCES app.accounts(id) ON DELETE CASCADE,
        quoted_credits  INTEGER NOT NULL,
        charged_credits INTEGER NOT NULL,          -- 0 for a rebuild already covered
        quote           JSONB NOT NULL,            -- drivers + price lines shown to the user
        measured        JSONB NOT NULL,            -- seconds, cpu seconds, actual bytes stored…
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX dashboard_usage_dataset_idx ON app.dashboard_usage (dataset_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.dashboard_usage")
    op.execute("ALTER TABLE app.dashboard_charges DROP CONSTRAINT IF EXISTS dashboard_charges_paid_positive")
    op.execute("ALTER TABLE app.dashboard_charges DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE app.dashboard_charges ADD COLUMN ledger_id BIGINT REFERENCES app.credit_ledger(id)")
    op.execute("""UPDATE app.dashboard_charges c SET ledger_id = (
                      SELECT max(id) FROM app.credit_ledger l WHERE l.kind = 'dashboard' AND l.ref = c.dataset_id)""")
    op.execute("ALTER TABLE app.dashboard_charges DROP COLUMN credits_paid")
