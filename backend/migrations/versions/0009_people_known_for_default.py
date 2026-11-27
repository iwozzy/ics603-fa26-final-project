"""Default omitted known-for titles to an empty JSONB array."""
from alembic import op
from sqlalchemy import text

revision = "0009_people_known_for_default"
down_revision = "0008_follows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("people", "known_for", server_default=text("'[]'::jsonb"))


def downgrade() -> None:
    op.alter_column("people", "known_for", server_default=None)
