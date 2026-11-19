"""Retain guest identities and aggregate their former session-owned quotas."""
import sqlalchemy as sa
from alembic import op

revision = "0003_durable_guests"
down_revision = "0002_atomic_admission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("guest_sessions", "guest_credentials")
    op.drop_column("guest_credentials", "expires_at")
    op.execute("""
        INSERT INTO usage_counters (scope, subject, feature, "window", count)
        SELECT 'guest', c.profile_id::text, u.feature, u."window", SUM(u.count)
        FROM usage_counters AS u
        JOIN guest_credentials AS c ON u.subject = c.id::text
        WHERE u.scope = 'session'
        GROUP BY c.profile_id, u.feature, u."window"
        ON CONFLICT (scope, subject, feature, "window")
        DO UPDATE SET count = usage_counters.count + EXCLUDED.count
    """)
    # Keep unmapped legacy counters as history rather than discarding usage.
    op.execute("""
        DELETE FROM usage_counters AS u USING guest_credentials AS c
        WHERE u.scope = 'session' AND u.subject = c.id::text
    """)


def downgrade() -> None:
    # The old application has per-session ownership. Assign the aggregate to
    # one credential so rollback/re-upgrade preserves sums without duplication.
    op.execute("""
        INSERT INTO usage_counters (scope, subject, feature, "window", count)
        SELECT 'session', c.id::text, u.feature, u."window", u.count
        FROM usage_counters AS u
        JOIN (
            SELECT DISTINCT ON (profile_id) profile_id, id
            FROM guest_credentials ORDER BY profile_id, id
        ) AS c ON u.subject = c.profile_id::text
        WHERE u.scope = 'guest'
        ON CONFLICT (scope, subject, feature, "window")
        DO UPDATE SET count = usage_counters.count + EXCLUDED.count
    """)
    op.execute("""
        DELETE FROM usage_counters AS u USING guest_credentials AS c
        WHERE u.scope = 'guest' AND u.subject = c.profile_id::text
    """)
    op.add_column("guest_credentials", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP + INTERVAL '24 hours'")))
    op.alter_column("guest_credentials", "expires_at", server_default=None)
    op.rename_table("guest_credentials", "guest_sessions")
