import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import override
from uuid import uuid4

import pytest

from lumiere.application.provider_dispatch import ProviderDispatch
from lumiere.application.use_cases.hydrate_filmography import HydrateFilmography
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import HydrationFailed, HydrationThrottled, SearchFailed
from lumiere.domain.filmography import PersonFilmography
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.fakes.hydration import (
    ControlledFilmography,
    ControlledFilmographyCatalog,
    ControlledHydrationClock,
    RecordingAdmission,
)

IDENTITY = PersonIdentity(CatalogProvider.TMDB, 4139)
GUEST = GuestContext(uuid4(), 'synthetic-ip')


@dataclass
class Setup:
    clock: ControlledHydrationClock
    store: ControlledFilmography
    catalog: ControlledFilmographyCatalog
    admission: RecordingAdmission
    hydrate: HydrateFilmography


def setup(*, timeout: float = 5) -> Setup:
    clock = ControlledHydrationClock()
    store = ControlledFilmography(clock)

    class CatalogWithoutTransaction(ControlledFilmographyCatalog):
        @override
        async def fetch(self, identity: PersonIdentity) -> PersonFilmography:
            assert not store.active
            return await super().fetch(identity)

    catalog = CatalogWithoutTransaction()
    admission = RecordingAdmission()
    hydrate = HydrateFilmography(store, catalog, ProviderDispatch(admission, clock), clock,
                                attempt_timeout=timeout)
    return Setup(clock, store, catalog, admission, hydrate)


@pytest.mark.parametrize(('age', 'eligible'), [
    ('missing', True),
    (None, True),
    (timedelta(hours=24), True),
    (timedelta(hours=24) - timedelta(microseconds=1), False),
    (-timedelta(days=1), False),
])
async def test_freshness_edge_precedes_admission(age: str | timedelta | None, eligible: bool) -> None:
    env = setup()
    if age != 'missing':
        env.store.timestamps[IDENTITY] = env.clock.now() - age if isinstance(age, timedelta) else None

    await env.hydrate.execute(IDENTITY, GUEST)

    assert env.store.reads == [IDENTITY]
    assert env.catalog.calls == ([IDENTITY] if eligible else [])
    assert env.admission.charged_contexts == ([GUEST] if eligible else [])
    assert not env.store.active
    if eligible:
        assert env.store.stored[IDENTITY].credits == ()
        assert env.store.timestamps[IDENTITY] == env.clock.now()
    else:
        assert not env.store.stored


async def test_provider_retry_rechecks_freshness_in_a_closed_read_transaction() -> None:
    env = setup()
    env.catalog.errors.append(HydrationFailed('provider_transport', retryable=True))
    task = asyncio.create_task(env.hydrate.execute(IDENTITY, GUEST))
    await env.catalog.fetching.wait()
    assert len(env.store.transactions) == 1
    assert not env.store.active
    env.store.timestamps[IDENTITY] = env.clock.now()
    await env.clock.advance(0.5)
    assert len(env.store.transactions) == 1
    await env.clock.advance(0.5)
    await asyncio.wait_for(task, 1)

    assert env.store.reads == [IDENTITY, IDENTITY]
    assert len(env.store.transactions) == 2
    assert not env.store.active
    assert env.admission.charged_contexts == [GUEST]
    assert env.catalog.calls == [IDENTITY]
    assert not env.store.writes


@pytest.mark.parametrize('retryable_error', ['provider_transport', 'provider_status'])
async def test_provider_retries_end_after_three_charged_attempts(retryable_error: str) -> None:
    env = setup()
    env.catalog.errors.extend([HydrationFailed(retryable_error, retryable=True)] * 3)
    task = asyncio.create_task(env.hydrate.execute(IDENTITY, GUEST))
    await env.catalog.fetching.wait()
    await env.clock.advance(1)
    await env.clock.advance(1)
    with pytest.raises(HydrationFailed, match=retryable_error):
        await asyncio.wait_for(task, 1)
    assert env.admission.charged_contexts == [GUEST] * 3
    assert env.store.reads == [IDENTITY] * 3
    assert env.catalog.calls == [IDENTITY] * 3
    assert not env.store.writes and not env.store.timestamps


async def test_retry_in_cooldown_is_outside_provider_timeout() -> None:
    env = setup(timeout=0.02)
    env.catalog.errors.append(HydrationThrottled(None))
    task = asyncio.create_task(env.hydrate.execute(IDENTITY, GUEST))
    await env.catalog.fetching.wait()
    await env.clock.advance(1)
    await asyncio.sleep(0.03)
    assert not task.done()
    assert len(env.catalog.calls) == 1
    assert not env.store.active

    await env.clock.advance(59)
    await asyncio.wait_for(task, 1)
    assert env.admission.charged_contexts == [GUEST, GUEST]
    assert env.store.timestamps[IDENTITY] == env.clock.now()


@pytest.mark.parametrize('category', ['provider_status', 'provider_response', 'provider_oversize'])
async def test_terminal_provider_failure_never_retries_or_marks_fresh(category: str) -> None:
    env = setup()
    env.catalog.errors.append(HydrationFailed(category))
    with pytest.raises(HydrationFailed, match=category):
        await env.hydrate.execute(IDENTITY, GUEST)
    assert env.admission.charged_contexts == [GUEST]
    assert env.catalog.calls == [IDENTITY]
    assert not env.store.writes and not env.store.timestamps


async def test_accounting_rejection_never_dispatches_or_retries() -> None:
    env = setup()
    env.admission.reject = True
    with pytest.raises(SearchFailed, match='quota'):
        await env.hydrate.execute(IDENTITY, GUEST)
    assert env.store.reads == [IDENTITY]
    assert not env.catalog.calls and not env.store.timestamps
    assert not env.admission.charged_contexts


@pytest.mark.parametrize('failed_commits', [2, 3])
async def test_database_retries_reuse_payload(failed_commits: int) -> None:
    env = setup()
    env.store.fail_commits = failed_commits
    task = asyncio.create_task(env.hydrate.execute(IDENTITY, GUEST))
    await env.store.committing.wait()
    await env.clock.advance(1)
    assert not env.store.active and not env.store.timestamps
    await env.clock.advance(1)

    if failed_commits == 3:
        with pytest.raises(HydrationFailed, match='storage'):
            await asyncio.wait_for(task, 1)
        assert not env.store.stored and not env.store.timestamps
    else:
        await asyncio.wait_for(task, 1)
        assert env.store.stored[IDENTITY] is env.store.writes[0]
        assert env.store.timestamps[IDENTITY] == env.clock.now()
    assert env.store.rollbacks == failed_commits
    assert len(env.store.transactions) == 4
    assert len(env.store.writes) == 3
    assert all(payload is env.store.writes[0] for payload in env.store.writes)
    assert env.catalog.calls == [IDENTITY]
    assert env.admission.charged_contexts == [GUEST]


async def test_freshness_read_timeout_closes_the_transaction_without_charging() -> None:
    env = setup(timeout=0.01)
    env.store.allow_read.clear()

    with pytest.raises(HydrationFailed, match='storage'):
        await asyncio.wait_for(env.hydrate.execute(IDENTITY, GUEST), 1)

    assert not env.store.active and not env.admission.charged_contexts


async def test_provider_attempt_timeout_retries_with_a_new_charge() -> None:
    env = setup(timeout=0.01)
    env.catalog.allow_fetch.clear()
    task = asyncio.create_task(env.hydrate.execute(IDENTITY, GUEST))
    try:
        await asyncio.wait_for(env.catalog.fetching.wait(), 1)
        await asyncio.sleep(0.03)
        assert not task.done() and not env.store.writes
        env.catalog.allow_fetch.set()
        await env.clock.advance(1)
        await asyncio.wait_for(task, 1)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    assert env.catalog.calls == [IDENTITY, IDENTITY]
    assert env.admission.charged_contexts == [GUEST, GUEST]
    assert env.store.timestamps[IDENTITY] == env.clock.now()
