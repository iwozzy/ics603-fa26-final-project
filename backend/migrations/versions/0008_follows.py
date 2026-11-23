"""Profile-owned follows of existing people."""
from alembic import op

revision = '0008_follows'
down_revision = '0007_people'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
        CREATE TABLE follows (
            profile_id uuid NOT NULL REFERENCES guest_profiles(id),
            person_id bigint NOT NULL REFERENCES people(id),
            followed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (profile_id, person_id)
        )
    ''')


def downgrade() -> None:
    op.drop_table('follows')
