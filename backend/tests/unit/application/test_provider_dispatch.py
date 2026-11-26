import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest

from lumiere.application.provider_dispatch import ProviderDispatch
from lumiere.domain.access import CounterKey, GuestContext, UsagePolicy
from lumiere.domain.errors import HydrationFailed, HydrationThrottled, SearchFailed
from lumiere.domain.filmography import FilmographyPerson, PersonFilmography
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider
from tests.fakes.accounting import ControlledAccess, running_accounting
from tests.fakes.hydration import ControlledHydrationClock, RecordingAdmission

CONTEXT = GuestContext(uuid4(), "synthetic-ip")
OTHER_CONTEXT = GuestContext(uuid4(), "another-synthetic-ip")
PAYLOAD = PersonFilmography(FilmographyPerson(PersonIdentity(CatalogProvider.TMDB, 1), "One", None), ())


async def test_eleventh_start_waits_for_rolling_window() -> None:
    clock = ControlledHydrationClock()
    dispatch = ProviderDispatch(RecordingAdmission(), clock)
    start_times: list[float] = []

    async def operation() -> PersonFilmography:
        start_times.append(clock.monotonic())
        return PAYLOAD

    for _ in range(5):
        await dispatch.run(CONTEXT, operation)
    await clock.advance(0.5)
    for _ in range(5):
        await dispatch.run(CONTEXT, operation)

    queued = [asyncio.create_task(dispatch.run(CONTEXT, operation)) for _ in range(10)]
    await asyncio.sleep(0)
    await clock.advance(0.25)
    assert len(start_times) == 10
    assert all(not attempt.done() for attempt in queued)
    await clock.advance(0.25)
    assert start_times == [0.0] * 5 + [0.5] * 5 + [1.0] * 5
    await clock.advance(0.25)
    assert len(start_times) == 15
    await clock.advance(0.25)
    assert start_times == [0.0] * 5 + [0.5] * 5 + [1.0] * 5 + [1.5] * 5
    assert await asyncio.gather(*queued) == [PAYLOAD] * 10


async def test_in_flight_never_exceeds_ten() -> None:
    clock = ControlledHydrationClock()
    dispatch = ProviderDispatch(RecordingAdmission(), clock)
    release = asyncio.Event()
    active = peak_in_flight = 0

    async def operation() -> PersonFilmography:
        nonlocal active, peak_in_flight
        active += 1
        peak_in_flight = max(peak_in_flight, active)
        try:
            await release.wait()
            return PAYLOAD
        finally:
            active -= 1

    requests = [asyncio.create_task(dispatch.run(CONTEXT, operation)) for _ in range(11)]
    await asyncio.sleep(0)
    await clock.advance(1)
    assert active == peak_in_flight == 10

    requests[0].cancel()
    with pytest.raises(asyncio.CancelledError):
        await requests[0]
    assert active == 10  # The eleventh call took the cancelled call's slot.
    release.set()
    assert await asyncio.gather(*requests[1:]) == [PAYLOAD] * 10
    assert active == 0


async def test_429_pauses_other_people_and_longer_delay_extends() -> None:
    clock = ControlledHydrationClock()
    dispatch = ProviderDispatch(RecordingAdmission(), clock)
    first, longer, shorter = asyncio.Event(), asyncio.Event(), asyncio.Event()
    other_start_times: list[float] = []
    other_payload = PersonFilmography(FilmographyPerson(PersonIdentity(CatalogProvider.TMDB, 2), "Two", None), ())

    async def throttle(release: asyncio.Event, delay: float | None) -> PersonFilmography:
        await release.wait()
        raise HydrationThrottled(delay)

    async def other_person() -> PersonFilmography:
        other_start_times.append(clock.monotonic())
        return other_payload

    routes = [(first, None), (longer, 120), (shorter, 1)]
    responses = [
        asyncio.create_task(dispatch.run(CONTEXT, lambda event=event, delay=delay: throttle(event, delay)))
        for event, delay in routes
    ]
    await asyncio.sleep(0)
    first.set()
    with pytest.raises(HydrationThrottled):
        await responses[0]

    queued = [asyncio.create_task(dispatch.run(OTHER_CONTEXT, other_person)) for _ in range(11)]
    await asyncio.sleep(0)
    await clock.advance(40)
    assert other_start_times == []
    longer.set()
    with pytest.raises(HydrationThrottled):
        await responses[1]  # This caller exits without a retry and still extends the cooldown.
    await clock.advance(20)
    assert other_start_times == []
    shorter.set()
    with pytest.raises(HydrationThrottled):
        await responses[2]
    await clock.advance(99.75)
    assert other_start_times == []
    await clock.advance(0.25)
    assert other_start_times == [160.0] * 10
    await clock.advance(1)
    assert other_start_times == [160.0] * 10 + [161.0]
    assert await asyncio.gather(*queued) == [other_payload] * 11


async def test_cooldown_uses_monotonic_time_after_a_wall_clock_jump() -> None:
    clock = ControlledHydrationClock()
    dispatch = ProviderDispatch(RecordingAdmission(), clock, rate_limit=1)

    async def throttle(release: asyncio.Event) -> PersonFilmography:
        await release.wait()
        raise HydrationThrottled(None)

    async def operation() -> PersonFilmography:
        return PAYLOAD

    release = asyncio.Event()
    first = asyncio.create_task(dispatch.run(CONTEXT, lambda: throttle(release)))
    second = asyncio.create_task(dispatch.run(OTHER_CONTEXT, operation))
    await asyncio.sleep(0)  # The second call is already parked behind the rolling gate.
    release.set()
    with pytest.raises(HydrationThrottled):
        await first

    clock.jump_wall(timedelta(days=1))
    await clock.advance(1)
    assert not second.done()
    await clock.advance(58.75)
    assert not second.done()
    await clock.advance(0.25)
    assert second.done()
    assert second.result() == PAYLOAD


async def test_cancellation_while_parked_does_not_charge() -> None:
    admission = RecordingAdmission()
    clock = ControlledHydrationClock()
    dispatch = ProviderDispatch(admission, clock, rate_limit=1)

    async def operation() -> PersonFilmography:
        return PAYLOAD

    await dispatch.run(CONTEXT, operation)
    parked = asyncio.create_task(dispatch.run(OTHER_CONTEXT, operation))
    await asyncio.sleep(0)
    parked.cancel()
    with pytest.raises(asyncio.CancelledError):
        await parked
    assert admission.charged_contexts == [CONTEXT]


async def test_admission_rejection_leaves_capacity_and_never_calls_provider() -> None:
    admission = RecordingAdmission()
    dispatch = ProviderDispatch(admission, ControlledHydrationClock(), rate_limit=1, max_in_flight=1)
    provider_calls = 0

    async def operation() -> PersonFilmography:
        nonlocal provider_calls
        provider_calls += 1
        return PAYLOAD

    admission.reject = True
    with pytest.raises(SearchFailed, match="quota"):
        await dispatch.run(CONTEXT, operation)
    assert provider_calls == 0
    assert admission.charged_contexts == []

    admission.reject = False
    result = await asyncio.wait_for(dispatch.run(CONTEXT, operation), 1)
    assert result == PAYLOAD
    assert provider_calls == 1


async def test_dispatch_charges_each_retry_without_holding_an_accounting_session_while_parked() -> None:
    clock = ControlledHydrationClock()
    store = ControlledAccess()
    policy = UsagePolicy(*(100 for _ in range(10)))
    provider_calls = 0

    async def operation() -> PersonFilmography:
        nonlocal provider_calls
        assert not store.active
        provider_calls += 1
        if provider_calls == 1:
            raise HydrationFailed("provider_network", retryable=True)
        return PAYLOAD

    async with running_accounting(store, policy, clock.now()) as admission:
        dispatch = ProviderDispatch(admission, clock, rate_limit=1)
        with pytest.raises(HydrationFailed):
            await dispatch.run(CONTEXT, operation)
        await admission.drain()
        opens = store.opens

        retry = asyncio.create_task(dispatch.run(CONTEXT, operation))
        await asyncio.sleep(0)
        assert not retry.done()
        assert not store.active
        assert store.opens == opens
        assert provider_calls == 1
        await clock.advance(1)
        assert retry.result() == PAYLOAD
        await admission.drain()

    assert provider_calls == 2
    assert len(store.counts) == 6
    assert store.counts[CounterKey("guest", str(CONTEXT.profile_id), "people_provider", "total")] == 2
    assert set(store.counts.values()) == {2}
