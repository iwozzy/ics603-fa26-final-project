"""Check every quota and charge a provider attempt in one database call."""
from alembic import op

revision = "0002_atomic_admission"
down_revision = "0001_guest_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("reservation_state", "usage_reservations", type_="check")
    op.create_check_constraint("reservation_state", "usage_reservations", "state IN ('reserved','dispatched','charged','success','failed','cancelled','released')")
    op.execute("""
        CREATE FUNCTION lumiere_admit_and_charge(attempt_id uuid, limits jsonb)
        RETURNS boolean
        LANGUAGE plpgsql
        AS $$
        BEGIN
            -- Both creation and locking use the same order across callers.
            INSERT INTO usage_counters (scope, subject, feature, "window", count)
            SELECT scope, subject, feature, "window", 0
            FROM jsonb_to_recordset(limits)
                AS l(scope text, subject text, feature text, "window" text, cap numeric)
            ORDER BY scope, subject, feature, "window"
            ON CONFLICT DO NOTHING;

            PERFORM c.count
            FROM usage_counters AS c
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

            INSERT INTO usage_reservations (id, provider_keys, state)
            SELECT attempt_id,
                COALESCE(jsonb_agg(key - 'cap' ORDER BY key->>'scope', key->>'subject', key->>'feature', key->>'window')
                    FILTER (WHERE key->>'feature' = 'people_provider'), '[]'::jsonb),
                'charged'
            FROM jsonb_array_elements(limits) AS keys(key);

            RETURN true;
        END;
        $$
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION lumiere_admit_and_charge(uuid, jsonb)")
    # Older code must continue treating unknown charged attempts as nonrefundable.
    op.execute("UPDATE usage_reservations SET state = 'dispatched' WHERE state = 'charged'")
    op.drop_constraint("reservation_state", "usage_reservations", type_="check")
    op.create_check_constraint("reservation_state", "usage_reservations", "state IN ('reserved','dispatched','success','failed','cancelled','released')")
