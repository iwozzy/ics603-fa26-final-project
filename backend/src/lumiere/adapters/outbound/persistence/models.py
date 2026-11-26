from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    LargeBinary,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GuestProfileRow(Base):
    __tablename__ = "guest_profiles"
    id: Mapped[UUID] = mapped_column(primary_key=True)


class GuestCredentialRow(Base):
    __tablename__ = "guest_credentials"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("guest_profiles.id"), nullable=False)
    token_digest: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)


class CounterRow(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (CheckConstraint("count >= 0", name="nonnegative_count"),)
    scope: Mapped[str] = mapped_column(String(16), primary_key=True)
    subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    feature: Mapped[str] = mapped_column(String(32), primary_key=True)
    window: Mapped[str] = mapped_column(String(32), primary_key=True)
    count: Mapped[int] = mapped_column(default=0, nullable=False)


class UsageFlushCheckpointRow(Base):
    __tablename__ = "usage_flush_checkpoints"
    __table_args__ = (CheckConstraint("sequence >= 0", name="nonnegative_flush_sequence"),)
    writer_id: Mapped[UUID] = mapped_column(primary_key=True)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PersonRow(Base):
    __tablename__ = "people"
    __table_args__ = (
        CheckConstraint("tmdb_id > 0"),
        CheckConstraint("length(btrim(name)) > 0"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, server_default=text("((('x'::text || substr(replace((gen_random_uuid())::text, '-'::text, ''::text), 1, 10)))::bit(40))::bigint"))
    tmdb_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    known_for_department: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    known_for: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    tmdb_profile_path: Mapped[str | None] = mapped_column(Text)
    tmdb_last_movies_hydration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FollowRow(Base):
    __tablename__ = 'follows'
    profile_id: Mapped[UUID] = mapped_column(ForeignKey('guest_profiles.id'), primary_key=True)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('people.id'), primary_key=True)
    followed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('clock_timestamp()'))


class MovieRow(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    tmdb_poster_path: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    tmdb_last_credits_hydration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("tmdb_id > 0", name="positive_movie_tmdb_id"),
        CheckConstraint("title ~ '[^[:space:]]'", name="nonblank_movie_title"),
        Index("ix_movies_release_date_id", release_date.desc(), id.desc()),
    )


class CreditRow(Base):
    __tablename__ = "credits"
    __table_args__ = (
        CheckConstraint("tmdb_id ~ '[^[:space:]]'", name="nonblank_credit_tmdb_id"),
        CheckConstraint("credit_type IN ('cast', 'crew')", name="valid_credit_type"),
        Index("ix_credits_person_id_movie_id", "person_id", "movie_id"),
        Index("ix_credits_movie_id_person_id", "movie_id", "person_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tmdb_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    movie_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("movies.id"), nullable=False)
    person_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("people.id"), nullable=False)
    credit_type: Mapped[str] = mapped_column(Text, nullable=False)
    credit_character: Mapped[str | None] = mapped_column(Text)
    credit_order: Mapped[int | None]
    credit_department: Mapped[str | None] = mapped_column(Text)
    credit_job: Mapped[str | None] = mapped_column(Text)
