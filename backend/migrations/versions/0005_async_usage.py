"""Checkpoint asynchronous counter batches without per-search history."""
import sqlalchemy as sa
from alembic import op

revision = "0005_async_usage"
down_revision = "0004_counter_only_admission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_flush_checkpoints",
        sa.Column("writer_id", sa.Uuid(), primary_key=True),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("sequence >= 0", name="nonnegative_flush_sequence"),
    )


def downgrade() -> None:
    op.drop_table("usage_flush_checkpoints")
