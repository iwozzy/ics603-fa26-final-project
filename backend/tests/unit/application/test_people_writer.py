import asyncio
from inspect import signature

from lumiere.application.people_writer import PeopleWriter
from lumiere.application.ports.people import PeopleWriteEvent
from tests.fakes.people import ControlledPeoplePersistence
from tests.fakes.search import sample_person


async def entered(store: ControlledPeoplePersistence, identifier: int) -> None:
    await asyncio.wait_for(store.entry(identifier).wait(), 1)


async def test_inflight_counts_toward_capacity() -> None:
    store = ControlledPeoplePersistence()
    store.barrier(1)
    writer = PeopleWriter(store, shutdown_timeout=.01)
    writer.start()
    try:
        assert writer.enqueue((sample_person(1),))
        await entered(store, 1)
        for i in range(2, 1025):
            assert writer.enqueue((sample_person(i),))
        assert writer.outstanding == 1024
        assert not writer.enqueue((sample_person(1025),))
    finally:
        await writer.close()
    assert writer.outstanding == 0 and writer.in_flight == 0


async def test_ten_batches_run_concurrently_and_next_starts_on_completion() -> None:
    store = ControlledPeoplePersistence()
    for i in range(1, 12):
        store.barrier(i)
    writer = PeopleWriter(store, shutdown_timeout=.01)
    writer.start()
    try:
        for i in range(1, 12):
            assert writer.enqueue((sample_person(i),))
        await asyncio.gather(*(entered(store, i) for i in range(1, 11)))
        assert writer.in_flight == 10 and store.max_active == 10
        assert len(store.active_session_tokens) == 10
        assert not store.entry(11).is_set()
        store.barrier(1).set()
        await entered(store, 11)
        assert writer.in_flight == 10 and writer.outstanding == 10
    finally:
        await writer.close()
    assert not store.active_session_tokens


async def test_empty_and_stopped_enqueue_do_not_write() -> None:
    store = ControlledPeoplePersistence()
    writer = PeopleWriter(store)
    assert not writer.enqueue((sample_person(),))
    writer.start()
    assert not writer.enqueue(())
    await writer.close()
    await writer.close()
    assert not writer.enqueue((sample_person(),))
    assert store.attempts == 0


async def test_three_attempts_then_drop() -> None:
    store = ControlledPeoplePersistence()
    store.upsert_errors = [RuntimeError('private detail') for _ in range(3)]
    events: list[PeopleWriteEvent] = []
    writer = PeopleWriter(store, retry_delay=.001, report=events.append)
    writer.start()
    writer.enqueue((sample_person(),))
    await asyncio.wait_for(writer.drain(), 1)
    await writer.close()
    assert store.attempts == store.rollbacks == 3
    assert store.commits == writer.outstanding == writer.in_flight == 0
    assert [e.kind for e in events].count('retry') == 2
    assert [e.kind for e in events].count('failed') == 1
    assert [e.attempt for e in events if e.kind == 'retry'] == [1, 2]


async def test_each_attempt_has_five_second_timeout() -> None:
    assert signature(PeopleWriter).parameters['attempt_timeout'].default == 5
    store = ControlledPeoplePersistence()
    store.allow_commit.clear()
    writer = PeopleWriter(store, attempt_timeout=.01, retry_delay=.001)
    writer.start()
    writer.enqueue((sample_person(),))
    await asyncio.wait_for(writer.drain(), 1)
    await writer.close()
    assert store.attempts == store.rollbacks == 3
    assert not store.active_session_tokens


async def test_retry_retains_capacity_and_dispatch_slot() -> None:
    store = ControlledPeoplePersistence()
    store.upsert_errors = [RuntimeError('synthetic')]
    retry = asyncio.Event()
    def report(event: PeopleWriteEvent) -> None:
        if event.kind == 'retry':
            retry.set()
    writer = PeopleWriter(store, max_pending=2, max_concurrent=1, retry_delay=.03, report=report)
    writer.start()
    try:
        writer.enqueue((sample_person(1),))
        await asyncio.wait_for(retry.wait(), 1)
        assert writer.outstanding == writer.in_flight == 1
        assert writer.enqueue((sample_person(2),))
        assert not writer.enqueue((sample_person(3),))
        assert not store.entry(2).is_set()
        await asyncio.wait_for(writer.drain(), 1)
        assert store.attempts == 3 and store.commits == 2
    finally:
        await writer.close()


async def test_primary_key_collision_retries_whole_batch() -> None:
    from sqlalchemy.exc import IntegrityError
    store = ControlledPeoplePersistence()
    store.upsert_errors = [IntegrityError('synthetic', None, Exception('primary key collision'))]
    writer = PeopleWriter(store, retry_delay=.001)
    writer.start()
    batch = (sample_person(1), sample_person(2))
    writer.enqueue(batch)
    await asyncio.wait_for(writer.drain(), 1)
    await writer.close()
    assert store.batches == [batch, batch]
    assert store.commits == store.rollbacks == 1


async def test_commit_ack_loss_retries_without_double_release() -> None:
    store = ControlledPeoplePersistence()
    store.ack_losses = 1
    writer = PeopleWriter(store, retry_delay=.001)
    writer.start()
    writer.enqueue((sample_person(),))
    await asyncio.wait_for(writer.drain(), 1)
    await writer.close()
    assert store.attempts == store.commits == 2
    assert writer.outstanding == writer.in_flight == 0


async def test_failed_batch_does_not_stop_later_batches() -> None:
    store = ControlledPeoplePersistence()
    store.upsert_errors = [RuntimeError('synthetic') for _ in range(3)]
    writer = PeopleWriter(store, max_concurrent=1, retry_delay=.001)
    writer.start()
    writer.enqueue((sample_person(1),))
    writer.enqueue((sample_person(2),))
    await asyncio.wait_for(writer.drain(), 1)
    await writer.close()
    assert store.attempts == 4 and store.commits == 1


async def test_shutdown_drains_then_cancels_and_awaits() -> None:
    store = ControlledPeoplePersistence()
    store.allow_commit.clear()
    writer = PeopleWriter(store, shutdown_timeout=.02, max_concurrent=1)
    writer.start()
    writer.enqueue((sample_person(1),))
    writer.enqueue((sample_person(2),))
    await asyncio.wait_for(store.committing.wait(), 1)
    await asyncio.wait_for(writer.close(), 1)
    await writer.close()
    assert store.rollbacks == 1 and not store.active_session_tokens
    assert writer.outstanding == writer.in_flight == 0
    await asyncio.wait_for(writer.drain(), .1)
    assert not [t for t in asyncio.all_tasks() if t.get_name().startswith('people-')]


async def test_cancelled_batch_rolls_back() -> None:
    store = ControlledPeoplePersistence()
    store.barrier(1)
    writer = PeopleWriter(store, shutdown_timeout=.01)
    writer.start()
    writer.enqueue((sample_person(1),))
    await entered(store, 1)
    await writer.close()
    assert store.rollbacks == 1 and store.commits == 0


async def test_shutdown_drains_successfully_before_timeout() -> None:
    store = ControlledPeoplePersistence()
    store.allow_commit.clear()
    writer = PeopleWriter(store)
    writer.start()
    writer.enqueue((sample_person(),))
    await asyncio.wait_for(store.committing.wait(), 1)
    closing = asyncio.create_task(writer.close())
    await asyncio.sleep(0)
    assert not closing.done()
    assert not writer.enqueue((sample_person(),))
    store.allow_commit.set()
    await asyncio.wait_for(closing, 1)
    assert store.commits == 1


async def test_dead_dispatcher_rejects_enqueue() -> None:
    store = ControlledPeoplePersistence()
    writer = PeopleWriter(store)
    writer.start()
    dispatcher = writer._dispatcher
    assert dispatcher is not None
    dispatcher.cancel()
    await asyncio.gather(dispatcher, return_exceptions=True)
    assert not writer.enqueue((sample_person(),))
    await writer.close()


async def test_report_failure_cannot_break_enqueue_or_dispatch() -> None:
    store = ControlledPeoplePersistence()
    def broken(event: PeopleWriteEvent) -> None:
        raise RuntimeError('private data')
    writer = PeopleWriter(store, report=broken)
    writer.start()
    assert writer.enqueue((sample_person(),))
    await asyncio.wait_for(writer.drain(), 1)
    await writer.close()
    assert store.commits == 1


async def test_terminal_telemetry_reports_released_counts() -> None:
    store = ControlledPeoplePersistence()
    events: list[PeopleWriteEvent] = []
    writer = PeopleWriter(store, report=events.append)
    writer.start()
    writer.enqueue((sample_person(),))
    await asyncio.wait_for(writer.drain(), 1)
    await writer.close()
    assert [(e.kind, e.outstanding, e.in_flight) for e in events] == [('accepted', 1, 0), ('started', 1, 1), ('succeeded', 0, 0)]


async def test_shutdown_cancellation_reports_inflight_drop_after_release() -> None:
    store = ControlledPeoplePersistence()
    store.allow_commit.clear()
    events: list[PeopleWriteEvent] = []
    writer = PeopleWriter(store, shutdown_timeout=.01, report=events.append)
    writer.start()
    writer.enqueue((sample_person(),))
    await asyncio.wait_for(store.committing.wait(), 1)
    await writer.close()
    assert [(e.kind, e.outstanding, e.in_flight) for e in events] == [('accepted', 1, 0), ('started', 1, 1), ('dropped', 0, 0)]
    assert store.rollbacks == 1
