import asyncio
from collections.abc import Callable

import pytest
from sqlalchemy import event, select

from lumiere.adapters.outbound.persistence.models import PersonRow
from lumiere.adapters.outbound.persistence.people_unit_of_work import (
    PostgresPeopleUnitOfWork,
)
from lumiere.domain.errors import SearchFailed
from tests.fakes.search import sample_person


async def test_bulk_upsert_preserves_ids_and_replaces_summary(people_uows: Callable[[], PostgresPeopleUnitOfWork]) -> None:
    statements: list[str] = []
    async with people_uows() as uow:
        connection = await uow.session.connection()
        def capture(conn: object, cursor: object, stmt: str, params: object, context: object, many: bool) -> None:
            statements.append(stmt)
        event.listen(connection.sync_connection, 'before_cursor_execute', capture)
        await uow.people.upsert_batch((sample_person(2, known_for_department='Acting', provider_profile_path='/a.jpg', known_for=('Old',)), sample_person(1)))
        await uow.commit()
    assert len(statements) == 1
    assert 'INSERT INTO people' in statements[0]
    assert 'RETURNING' not in statements[0] and 'SELECT' not in statements[0]
    async with people_uows() as uow:
        before = (await uow.session.scalars(select(PersonRow).where(PersonRow.tmdb_id == 2))).one()
        identifier = before.id
        assert 0 <= identifier < 2**40
    async with people_uows() as uow:
        await uow.people.upsert_batch((sample_person(2, name='Updated', known_for=('Updated',)),))
        await uow.commit()
    async with people_uows() as uow:
        rows = (await uow.session.scalars(select(PersonRow).order_by(PersonRow.tmdb_id))).all()
        assert len(rows) == 2
        assert rows[1].id == identifier
        assert rows[1].name == 'Updated' and rows[1].known_for == ['Updated']
        assert rows[1].known_for_department is None and rows[1].tmdb_profile_path is None


async def test_duplicate_tmdb_ids_use_first_occurrence(people_uows: Callable[[], PostgresPeopleUnitOfWork]) -> None:
    async with people_uows() as uow:
        await uow.people.upsert_batch((sample_person(2, name='First'), sample_person(1), sample_person(2, name='Second')))
        await uow.commit()
    async with people_uows() as uow:
        rows = (await uow.session.scalars(select(PersonRow).order_by(PersonRow.tmdb_id))).all()
        assert len(rows) == 2 and rows[1].name == 'First'


async def test_batch_rollback_is_atomic(people_uows: Callable[[], PostgresPeopleUnitOfWork]) -> None:
    async with people_uows() as uow:
        await uow.people.upsert_batch((sample_person(1, name='Before'),))
        await uow.commit()
    with pytest.raises(SearchFailed, match='storage'):
        async with people_uows() as uow:
            await uow.people.upsert_batch((sample_person(1, name='Changed'), sample_person(2, name=' ')))
            await uow.commit()
    async with people_uows() as uow:
        rows = (await uow.session.scalars(select(PersonRow))).all()
        assert len(rows) == 1 and rows[0].name == 'Before'


async def test_overlapping_batches_preserve_unique_identity(people_uows: Callable[[], PostgresPeopleUnitOfWork]) -> None:
    async def write(ids: tuple[int, ...]) -> None:
        async with people_uows() as uow:
            await uow.people.upsert_batch(tuple(sample_person(i) for i in ids))
            await uow.commit()
    await asyncio.wait_for(asyncio.gather(write((3, 2, 1)), write((1, 2, 3))), 3)
    async with people_uows() as uow:
        rows = (await uow.session.scalars(select(PersonRow))).all()
        before = {r.tmdb_id: r.id for r in rows}
    await asyncio.gather(write((2, 1)), write((3, 2)))
    async with people_uows() as uow:
        assert {r.tmdb_id: r.id for r in (await uow.session.scalars(select(PersonRow))).all()} == before


async def test_empty_batch_issues_no_write(people_uows: Callable[[], PostgresPeopleUnitOfWork]) -> None:
    async with people_uows() as uow:
        statements: list[str] = []
        connection = await uow.session.connection()
        def capture(conn: object, cursor: object, stmt: str, params: object, context: object, many: bool) -> None:
            statements.append(stmt)
        event.listen(connection.sync_connection, 'before_cursor_execute', capture)
        await uow.people.upsert_batch(())
        await uow.commit()
        assert statements == []


async def test_people_cancellation_discards_connection(people_uows: Callable[[], PostgresPeopleUnitOfWork], monkeypatch: pytest.MonkeyPatch) -> None:
    started, release = asyncio.Event(), asyncio.Event()
    async def work() -> None:
        async with people_uows() as uow:
            await uow.people.upsert_batch((sample_person(),))
            original = uow.session.rollback
            async def stalled() -> None:
                await release.wait()
                await original()
            monkeypatch.setattr(uow.session, 'rollback', stalled)
            started.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(work())
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, .2)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    async with people_uows() as uow:
        assert (await uow.session.scalars(select(PersonRow))).all() == []
