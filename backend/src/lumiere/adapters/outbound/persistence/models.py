from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String
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
