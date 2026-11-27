import asyncio
from uuid import uuid4

from lumiere.application.filmography_hydrator import FilmographyHydrator
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import HydrationFailed
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.unit.application.test_hydrate_filmography import setup


def identity(number: int) -> PersonIdentity:
    return PersonIdentity(CatalogProvider.TMDB, number)


async def test_duplicate_enqueue_keeps_first_requester_through_retry() -> None:
    first_guest, second_guest = GuestContext(uuid4(), 'first-ip'), GuestContext(uuid4(), 'second-ip')
    env = setup()
    env.catalog.errors.append(HydrationFailed('provider_transport', retryable=True))
    hydrator = FilmographyHydrator(env.hydrate)
    hydrator.start()
    try:
        assert hydrator.enqueue(identity(1), first_guest)
        assert not hydrator.enqueue(identity(1), second_guest)
        assert hydrator.outstanding == 1
        await asyncio.wait_for(env.catalog.fetching.wait(), 1)
        assert hydrator.in_flight == 1
        assert not hydrator.enqueue(identity(1), second_guest)
        await env.clock.advance(1)
        await asyncio.wait_for(hydrator.drain(), 1)
        assert env.admission.charged_contexts == [first_guest, first_guest]
        assert hydrator.in_flight == hydrator.outstanding == 0
        assert hydrator.enqueue(identity(1), second_guest)
        await asyncio.wait_for(hydrator.drain(), 1)
        assert env.admission.charged_contexts == [first_guest, first_guest]
    finally:
        await hydrator.close()


async def test_queue_caps_distinct_outstanding_including_open_transactions() -> None:
    guest = GuestContext(uuid4(), 'synthetic-ip')
    env = setup()
    env.store.allow_read.clear()
    hydrator = FilmographyHydrator(env.hydrate, shutdown_timeout=0.01)
    assert not hydrator.enqueue(identity(1), guest)
    hydrator.start()
    try:
        for number in range(1, 1025):
            assert hydrator.enqueue(identity(number), guest)
        await asyncio.wait_for(env.store.reading.wait(), 1)
        assert len(env.store.active) == hydrator.in_flight == 10
        assert hydrator.outstanding == 1024
        assert not hydrator.enqueue(identity(1025), guest)
    finally:
        await hydrator.close()
    assert hydrator.in_flight == hydrator.outstanding == 0
    assert not env.store.active and not env.admission.charged_contexts
    assert not hydrator.enqueue(identity(1025), guest)
