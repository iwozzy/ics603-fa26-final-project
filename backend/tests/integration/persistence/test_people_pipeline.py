import json
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import select

from lumiere.adapters.outbound.clients.tmdb_people.client import TMDBPeopleCatalog
from lumiere.adapters.outbound.persistence.models import PersonRow
from lumiere.adapters.outbound.persistence.people_unit_of_work import (
    PostgresPeopleUnitOfWork,
)
from lumiere.adapters.outbound.persistence.pools import PoolRegistry
from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.application.people_writer import PeopleWriter
from lumiere.application.use_cases.search_people import SearchPeople
from lumiere.domain.access import GuestContext
from tests.fakes.search import FakeAdmission, FakeClock
from tests.integration.persistence.conftest import TEST_DATABASE_URL

FIXTURE = Path(__file__).resolve().parents[4] / 'docs/samples/api/tmdb/v3/search/person.json'


async def test_real_provider_to_selected_people_pool_pipeline(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    registry = PoolRegistry()
    pool = registry.register('people_writer', TEST_DATABASE_URL)
    def people_uows() -> PostgresPeopleUnitOfWork:
        return PostgresPeopleUnitOfWork(pool.sessions)
    writer = PeopleWriter(people_uows)
    writer.start()
    try:
        async with httpx.AsyncClient(base_url='https://provider.test', transport=httpx.MockTransport(lambda _: httpx.Response(200, json=json.loads(FIXTURE.read_text())))) as client:
            search = SearchPeople(TMDBPeopleCatalog(client), FakeAdmission(), FakeClock(), writer)
            result = await search.execute('Tom', GuestContext(uuid4(), 'synthetic'))
            assert len(result.people) == 7
            await writer.drain()
            async with people_uows() as uow:
                rows = (await uow.session.scalars(select(PersonRow))).all()
                before = {row.tmdb_id: row.id for row in rows}
                assert set(before) == {p.provider_id for p in result.people}
                stored = next(row for row in rows if row.tmdb_id == 4139)
                assert stored.name == 'Tom Skerritt'
                assert stored.known_for_department == 'Acting'
                assert stored.known_for == ['Alien', 'Top Gun', 'Contact']
                assert stored.tmdb_profile_path == '/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg'
            await search.execute('Tom', GuestContext(uuid4(), 'synthetic'))
            await writer.drain()
            async with people_uows() as uow:
                assert {row.tmdb_id: row.id for row in (await uow.session.scalars(select(PersonRow))).all()} == before
    finally:
        await writer.close()
        await registry.close()
