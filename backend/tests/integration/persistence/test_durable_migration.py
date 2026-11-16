from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text

from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.use_cases.guest_identity import GuestIdentityService
from lumiere.domain.access import UsagePolicy
from lumiere.domain.errors import SearchFailed
from tests.fakes.accounting import running_accounting

NOW = datetime(2026, 11, 15, tzinfo=UTC)
POLICY = UsagePolicy(100, 100, 100, 100, 100, 100, 100, 100, 5, 100)


async def test_durable_migration_preserves_profiles_proofs_and_aggregate_usage(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    revision = ScriptDirectory(str(Path(__file__).parents[3] / "migrations")).get_revision("0003_durable_guests")
    assert revision is not None
    migration = revision.module
    first_profile, second_profile = uuid4(), uuid4()
    credentials = [uuid4(), uuid4(), uuid4()]
    proofs = ["synthetic-proof-one", "synthetic-proof-two", "synthetic-proof-three"]
    orphan = uuid4()
    windows = [("people_request", "2026-11-15T00:00"), ("people_provider", "2026-11-15"), ("people_provider", "total")]

    def verify_guest_counts(connection: Connection) -> None:
        for feature, window in windows:
            for profile, expected in ((first_profile, 5), (second_profile, 4)):
                assert connection.scalar(text('SELECT count FROM usage_counters WHERE scope = :scope AND subject = :subject AND feature = :feature AND "window" = :window'), {"scope": "guest", "subject": str(profile), "feature": feature, "window": window}) == expected
        assert connection.scalar(text("SELECT count FROM usage_counters WHERE scope = 'global'")) == 17
        assert connection.scalar(text("SELECT count FROM usage_counters WHERE scope = 'ip'")) == 13
        assert connection.scalar(text("SELECT count FROM usage_counters WHERE scope = 'session' AND subject = :subject"), {"subject": str(orphan)}) == 7

    def seed_and_roundtrip(connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            connection.execute(text("INSERT INTO guest_profiles (id) VALUES (:id)"), [{"id": first_profile}, {"id": second_profile}])
            for credential, profile, proof, count in zip(credentials, [first_profile, first_profile, second_profile], proofs, [2, 3, 4], strict=True):
                connection.execute(text("INSERT INTO guest_sessions (id, profile_id, token_digest, expires_at) VALUES (:id, :profile_id, :digest, :expiry)"), {"id": credential, "profile_id": profile, "digest": sha256(proof.encode()).digest(), "expiry": NOW - timedelta(days=2)})
                for feature, window in windows:
                    connection.execute(text('INSERT INTO usage_counters (scope, subject, feature, "window", count) VALUES (:scope, :subject, :feature, :window, :count)'), {"scope": "session", "subject": str(credential), "feature": feature, "window": window, "count": count})
            for scope, subject, count in (("global", "all", 17), ("ip", "synthetic-ip", 13), ("session", str(orphan), 7)):
                connection.execute(text('INSERT INTO usage_counters (scope, subject, feature, "window", count) VALUES (:scope, :subject, :feature, :window, :count)'), {"scope": scope, "subject": subject, "feature": "people_provider", "window": "total", "count": count})
            migration.upgrade()
            verify_guest_counts(connection)
            assert connection.scalar(text("SELECT COUNT(*) FROM guest_credentials")) == 3
            assert connection.scalar(text("SELECT COUNT(*) FROM guest_profiles")) == 2
            assert connection.scalar(text("SELECT COUNT(*) FROM usage_counters WHERE scope = 'session'")) == 1
            migration.downgrade()
            for feature, window in windows:
                assert connection.scalar(text('SELECT SUM(count) FROM usage_counters WHERE scope = :scope AND subject IN (:first, :second) AND feature = :feature AND "window" = :window'), {"scope": "session", "first": str(credentials[0]), "second": str(credentials[1]), "feature": feature, "window": window}) == 5
            migration.upgrade()
            verify_guest_counts(connection)

    async with uows() as uow:
        await (await uow.session.connection()).run_sync(seed_and_roundtrip)
        await uow.commit()
    guests = GuestIdentityService(uows, POLICY)
    for proof in proofs[:2]:
        context = await guests.resolve(proof, "synthetic-ip-new", NOW + timedelta(days=365))
        assert context.profile_id == first_profile
        async with running_accounting(uows, POLICY, NOW + timedelta(days=365)) as admission:
            with pytest.raises(SearchFailed, match="quota"):
                await admission.admit_and_charge(context, NOW + timedelta(days=365))
    returning = await guests.bootstrap(proofs[2], "synthetic-ip-new", NOW + timedelta(days=365))
    assert returning.context.profile_id == second_profile
    assert returning.proof == proofs[2]
    assert not returning.is_new
