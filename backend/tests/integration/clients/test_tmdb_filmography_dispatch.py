import asyncio
from typing import override
from uuid import uuid4

import httpx
import pytest

from lumiere.adapters.outbound.clients.tmdb_filmography.client import (
    TMDBFilmographyCatalog,
)
from lumiere.application.provider_dispatch import ProviderDispatch
from lumiere.domain.access import GuestContext
from lumiere.domain.errors import HydrationFailed, HydrationThrottled
from lumiere.domain.filmography import PersonFilmography
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.fakes.hydration import ControlledHydrationClock, RecordingAdmission

GUEST = GuestContext(uuid4(), "synthetic-ip")
OTHER_GUEST = GuestContext(uuid4(), "other-synthetic-ip")


class HeldClose(httpx.AsyncByteStream):
    def __init__(self, *, fail: bool = False) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.fail = fail

    @override
    async def aclose(self) -> None:
        self.started.set()
        await self.release.wait()
        if self.fail:
            raise httpx.CloseError("synthetic close failure")


def success(person_id: int) -> httpx.Response:
    return httpx.Response(200, json={
        "id": person_id, "name": "Synthetic Person", "movie_credits": {"cast": [], "crew": []},
    })


async def test_receipt_blocks_dispatch_during_close_and_later_receipt_extends_it() -> None:
    clock, admission = ControlledHydrationClock(), RecordingAdmission()
    dispatch = ProviderDispatch(admission, clock)
    starts: list[tuple[str, float]] = []
    close = HeldClose()
    first_headers, second_headers = asyncio.Event(), asyncio.Event()

    async def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        starts.append((path, clock.monotonic()))
        if path == "/3/person/1":
            await first_headers.wait()
            return httpx.Response(429, headers={"Retry-After": "95"}, stream=close)
        if path == "/3/person/2":
            await second_headers.wait()
            return httpx.Response(429, headers={"Retry-After": "Thu, 26 Nov 2026 00:02:00 GMT"})
        return success(3)

    async with httpx.AsyncClient(base_url="https://provider.test", transport=httpx.MockTransport(respond)) as client:
        catalog = TMDBFilmographyCatalog(client, clock, on_throttle=dispatch.observe_throttle)

        async def fetch(person_id: int, context: GuestContext) -> PersonFilmography:
            identity = PersonIdentity(CatalogProvider.TMDB, person_id)
            return await dispatch.run(context, lambda: catalog.fetch(identity))

        async with asyncio.TaskGroup() as group:
            async def expect_throttle(person_id: int) -> None:
                with pytest.raises(HydrationThrottled):
                    await fetch(person_id, GUEST)

            first = group.create_task(expect_throttle(1))
            second = group.create_task(expect_throttle(2))
            await asyncio.sleep(0)
            first_headers.set()
            await asyncio.wait_for(close.started.wait(), 1)
            third = group.create_task(fetch(3, OTHER_GUEST))
            await clock.advance(20)
            assert starts == [("/3/person/1", 0), ("/3/person/2", 0)]
            assert admission.charged_contexts == [GUEST, GUEST]
            second_headers.set()
            await second
            await clock.advance(30)
            close.release.set()
            await first
            await clock.advance(69.75)
            assert len(starts) == len(admission.charged_contexts) == 2
            await clock.advance(0.25)
            assert (await asyncio.wait_for(third, 1)).person.identity.provider_id == 3
            assert starts[-1] == ("/3/person/3", 120)
            assert admission.charged_contexts == [GUEST, GUEST, OTHER_GUEST]


@pytest.mark.parametrize("outcome", ["failure", "cancellation", "timeout"])
async def test_interrupted_close_preserves_receipt_deadline(outcome: str) -> None:
    clock, admission = ControlledHydrationClock(), RecordingAdmission()
    dispatch = ProviderDispatch(admission, clock)
    starts: list[tuple[str, float]] = []
    close = HeldClose(fail=outcome == "failure")

    def respond(request: httpx.Request) -> httpx.Response:
        starts.append((request.url.path, clock.monotonic()))
        if request.url.path == "/3/person/1":
            return httpx.Response(429, headers={"Retry-After": "95"}, stream=close)
        return success(2)

    async with httpx.AsyncClient(base_url="https://provider.test", transport=httpx.MockTransport(respond)) as client:
        catalog = TMDBFilmographyCatalog(client, clock, on_throttle=dispatch.observe_throttle)
        first_identity = PersonIdentity(CatalogProvider.TMDB, 1)
        second_identity = PersonIdentity(CatalogProvider.TMDB, 2)
        first = asyncio.create_task(dispatch.run(GUEST, lambda: catalog.fetch(first_identity)))
        await asyncio.wait_for(close.started.wait(), 1)
        await clock.advance(15)
        if outcome == "failure":
            close.release.set()
            with pytest.raises(HydrationFailed):
                await first
        elif outcome == "cancellation":
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
        else:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(first, 0)

        async with asyncio.TaskGroup() as group:
            second = group.create_task(dispatch.run(OTHER_GUEST, lambda: catalog.fetch(second_identity)))
            await clock.advance(79.75)
            assert starts == [("/3/person/1", 0)]
            assert admission.charged_contexts == [GUEST]
            await clock.advance(0.25)
            assert (await asyncio.wait_for(second, 1)).person.identity == second_identity
            assert starts == [("/3/person/1", 0), ("/3/person/2", 95)]
            assert admission.charged_contexts == [GUEST, OTHER_GUEST]
