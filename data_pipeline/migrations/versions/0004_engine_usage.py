"""engine: resource usage per dataset (what an upload and a build actually consumed)

Revision ID: 0004
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE bayan_datasets ADD COLUMN upload_usage JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE bayan_datasets ADD COLUMN build_usage JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE bayan_datasets DROP COLUMN build_usage")
    op.execute("ALTER TABLE bayan_datasets DROP COLUMN upload_usage")
