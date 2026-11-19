"""Keep quota counters authoritative and discard per-attempt outcome history."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_counter_only_admission"
down_revision = "0003_durable_guests"
branch_labels = None
depends_on = None


def _create_admission_function(with_reservations: bool) -> None:
    signature = "attempt_id uuid, limits jsonb" if with_reservations else "limits jsonb"
    record = """
        INSERT INTO usage_reservations (id, provider_keys, state)
        SELECT attempt_id,
            COALESCE(jsonb_agg(key - 'cap' ORDER BY key->>'scope', key->>'subject', key->>'feature', key->>'window')
                FILTER (WHERE key->>'feature' = 'people_provider'), '[]'::jsonb),
            'charged'
        FROM jsonb_array_elements(limits) AS keys(key);
    """ if with_reservations else ""
    op.execute(f"""
        CREATE FUNCTION lumiere_admit_and_charge({signature})
        RETURNS boolean LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO usage_counters (scope, subject, feature, "window", count)
            SELECT scope, subject, feature, "window", 0
            FROM jsonb_to_recordset(limits)
                AS l(scope text, subject text, feature text, "window" text, cap numeric)
            ORDER BY scope, subject, feature, "window"
            ON CONFLICT DO NOTHING;

            PERFORM c.count FROM usage_counters AS c
            JOIN jsonb_to_recordset(limits)
                AS l(scope text, subject text, feature text, "window" text, cap numeric)
                USING (scope, subject, feature, "window")
            ORDER BY c.scope, c.subject, c.feature, c."window"
            FOR UPDATE OF c;

            IF EXISTS (
                SELECT 1 FROM usage_counters AS c
                JOIN jsonb_to_recordset(limits)
                    AS l(scope text, subject text, feature text, "window" text, cap numeric)
                    USING (scope, subject, feature, "window")
                WHERE c.count >= l.cap
            ) THEN
                RETURN false;
            END IF;

            UPDATE usage_counters AS c SET count = c.count + 1
            FROM jsonb_to_recordset(limits)
                AS l(scope text, subject text, feature text, "window" text, cap numeric)
            WHERE (c.scope, c.subject, c.feature, c."window") =
                  (l.scope, l.subject, l.feature, l."window");

            {record}
            RETURN true;
        END;
        $$
    """)


def upgrade() -> None:
    op.execute("DROP FUNCTION lumiere_admit_and_charge(uuid, jsonb)")
    _create_admission_function(with_reservations=False)
    op.drop_table("usage_reservations")


def downgrade() -> None:
    op.execute("DROP FUNCTION lumiere_admit_and_charge(jsonb)")
    # Counter charges survive rollback; previously dropped audit rows do not.
    op.create_table("usage_reservations", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("provider_keys", postgresql.JSONB(), nullable=False), sa.Column("state", sa.String(16), nullable=False), sa.CheckConstraint("state IN ('reserved','dispatched','charged','success','failed','cancelled','released')", name="reservation_state"))
    _create_admission_function(with_reservations=True)
