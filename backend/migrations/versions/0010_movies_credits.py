"""Add the movie catalog, person credits, and hydration timestamps."""

from alembic import op
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Text,
    text,
)

revision = "0010_movies_credits"
down_revision = "0009_people_known_for_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("people", Column("tmdb_last_movies_hydration", DateTime(timezone=True)))
    op.create_table(
        "movies",
        Column("id", BigInteger, Identity(always=True), primary_key=True),
        Column("tmdb_id", BigInteger, nullable=False, unique=True),
        Column("title", Text, nullable=False),
        Column("overview", Text),
        Column("tmdb_poster_path", Text),
        Column("release_date", Date, nullable=False),
        Column("tmdb_last_credits_hydration", DateTime(timezone=True)),
        CheckConstraint("tmdb_id > 0", name="positive_movie_tmdb_id"),
        CheckConstraint("title ~ '[^[:space:]]'", name="nonblank_movie_title"),
    )
    op.create_table(
        "credits",
        Column("id", BigInteger, Identity(always=True), primary_key=True),
        Column("tmdb_id", Text, nullable=False, unique=True),
        Column("movie_id", BigInteger, ForeignKey("movies.id"), nullable=False),
        Column("person_id", BigInteger, ForeignKey("people.id"), nullable=False),
        Column("credit_type", Text, nullable=False),
        Column("credit_character", Text),
        Column("credit_order", Integer),
        Column("credit_department", Text),
        Column("credit_job", Text),
        CheckConstraint("tmdb_id ~ '[^[:space:]]'", name="nonblank_credit_tmdb_id"),
        CheckConstraint("credit_type IN ('cast', 'crew')", name="valid_credit_type"),
    )
    op.create_index("ix_movies_release_date_id", "movies", [text("release_date DESC"), text("id DESC")])
    op.create_index("ix_credits_person_id_movie_id", "credits", ["person_id", "movie_id"])
    op.create_index("ix_credits_movie_id_person_id", "credits", ["movie_id", "person_id"])


def downgrade() -> None:
    op.drop_table("credits")
    op.drop_table("movies")
    op.drop_column("people", "tmdb_last_movies_hydration")
