"""Guest identity and usage only; search candidates are never retained."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_guest_usage"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("guest_profiles", sa.Column("id", sa.Uuid(), primary_key=True))
    op.create_table("guest_sessions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("guest_profiles.id"), nullable=False), sa.Column("token_digest", sa.LargeBinary(32), unique=True, nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("usage_counters", sa.Column("scope", sa.String(16), primary_key=True), sa.Column("subject", sa.String(128), primary_key=True), sa.Column("feature", sa.String(32), primary_key=True), sa.Column("window", sa.String(32), primary_key=True), sa.Column("count", sa.Integer(), nullable=False), sa.CheckConstraint("count >= 0", name="nonnegative_count"))
    op.create_table("usage_reservations", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("provider_keys", postgresql.JSONB(), nullable=False), sa.Column("state", sa.String(16), nullable=False), sa.CheckConstraint("state IN ('reserved','dispatched','success','failed','cancelled','released')", name="reservation_state"))


def downgrade() -> None:
    for table in ("usage_reservations", "usage_counters", "guest_sessions", "guest_profiles"):
        op.drop_table(table)
