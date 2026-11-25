"""Flush asynchronous usage batches in one database call."""
from alembic import op

revision = "0006_usage_flush_function"
down_revision = "0005_async_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION lumiere_flush_charges(p_writer_id uuid, p_sequence bigint, p_deltas jsonb)
        RETURNS SETOF usage_counters
        LANGUAGE plpgsql
        AS $$
        DECLARE
            last_sequence bigint;
        BEGIN
            INSERT INTO usage_flush_checkpoints (writer_id, sequence)
            VALUES (p_writer_id, 0)
            ON CONFLICT DO NOTHING;

            SELECT c.sequence INTO last_sequence
            FROM usage_flush_checkpoints AS c
            WHERE c.writer_id = p_writer_id
            FOR UPDATE;

            IF last_sequence = p_sequence THEN
                -- A retry after an ambiguous commit must not charge twice.
                RETURN QUERY
                SELECT c.* FROM usage_counters AS c
                JOIN jsonb_to_recordset(p_deltas)
                    AS d(scope text, subject text, feature text, "window" text, count integer)
                    USING (scope, subject, feature, "window")
                ORDER BY c.scope, c.subject, c.feature, c."window";
            ELSIF last_sequence = p_sequence - 1 THEN
                -- Consistent ordering avoids deadlocks between overlapping writers.
                RETURN QUERY
                INSERT INTO usage_counters AS c (scope, subject, feature, "window", count)
                SELECT d.scope, d.subject, d.feature, d."window", d.count
                FROM jsonb_to_recordset(p_deltas)
                    AS d(scope text, subject text, feature text, "window" text, count integer)
                ORDER BY d.scope, d.subject, d.feature, d."window"
                ON CONFLICT (scope, subject, feature, "window")
                DO UPDATE SET count = c.count + excluded.count
                RETURNING c.*;

                UPDATE usage_flush_checkpoints
                SET sequence = p_sequence
                WHERE writer_id = p_writer_id;
            ELSE
                -- No rows signals rejection without aborting the caller's transaction.
                RETURN;
            END IF;
        END;
        $$
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION lumiere_flush_charges(uuid, bigint, jsonb)")
