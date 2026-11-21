"""App-owned summaries of selected TMDB people."""
from alembic import op

revision = "0007_people"
down_revision = "0006_usage_flush_function"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE people (
            id bigint PRIMARY KEY DEFAULT ((('x'::text || substr(replace((gen_random_uuid())::text, '-'::text, ''::text), 1, 10)))::bit(40))::bigint,
            tmdb_id bigint NOT NULL UNIQUE CHECK (tmdb_id > 0),
            known_for_department text,
            name text NOT NULL CHECK (length(btrim(name)) > 0),
            known_for jsonb NOT NULL,
            tmdb_profile_path text
        )
    """)


def downgrade() -> None:
    op.drop_table("people")
