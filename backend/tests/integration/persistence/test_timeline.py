from collections.abc import Callable
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import delete, event, text

from lumiere.adapters.inbound.http.timeline_cursor import Base64TimelineCursorCodec
from lumiere.adapters.outbound.persistence.models import (
    CreditRow,
    FollowRow,
    GuestProfileRow,
    MovieRow,
    PersonRow,
)
from lumiere.adapters.outbound.persistence.timeline_unit_of_work import (
    PostgresTimelineUnitOfWork,
)
from lumiere.application.use_cases.list_timeline import ListTimeline
from lumiere.domain.access import GuestContext
from lumiere.domain.timeline import (
    MovieSummary,
    TimelineCursor,
    TimelinePage,
    TimelineRequest,
    TimelineSelection,
)

type TimelineUows = Callable[[], PostgresTimelineUnitOfWork]

PAST = date(2024, 2, 29)
FUTURE = date(2199, 1, 1)
UTC_DAY = "SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date"
INITIAL = TimelineRequest()


async def seed_owners(uow: PostgresTimelineUnitOfWork) -> tuple[GuestContext, GuestContext]:
    owner = GuestContext(uuid4(), 'synthetic-owner')
    other = GuestContext(uuid4(), 'synthetic-other')
    uow.session.add_all([
        GuestProfileRow(id=owner.profile_id), GuestProfileRow(id=other.profile_id),
        PersonRow(id=1, tmdb_id=101, name='Actor'),
        PersonRow(id=2, tmdb_id=102, name='Director'),
        PersonRow(id=3, tmdb_id=103, name='Unrelated actor'),
    ])
    await uow.session.flush()
    uow.session.add_all([
        FollowRow(profile_id=owner.profile_id, person_id=1),
        FollowRow(profile_id=owner.profile_id, person_id=2),
        FollowRow(profile_id=other.profile_id, person_id=3),
    ])
    await uow.session.flush()
    return owner, other


async def seed_movies(uow: PostgresTimelineUnitOfWork, *dates: date) -> list[int]:
    movies = [
        MovieRow(tmdb_id=i, title=f'Movie {i}', release_date=release_date)
        for i, release_date in enumerate(dates, start=1)
    ]
    uow.session.add_all(movies)
    await uow.session.flush()
    uow.session.add_all([
        CreditRow(tmdb_id=f'cast-{movie.tmdb_id}', movie_id=movie.id, person_id=1, credit_type='cast')
        for movie in movies
    ])
    return [movie.id for movie in movies]


async def remove_movies(uow: PostgresTimelineUnitOfWork, *movie_ids: int) -> None:
    await uow.session.execute(delete(CreditRow).where(CreditRow.movie_id.in_(movie_ids)))
    await uow.session.execute(delete(MovieRow).where(MovieRow.id.in_(movie_ids)))
    await uow.commit()


async def read(
    factory: TimelineUows, owner: GuestContext, request: TimelineRequest = INITIAL,
    *, explain: str | None = None,
) -> TimelinePage:
    statements: list[tuple[str, dict[str, object]]] = []

    def capture(conn: object, cursor: object, stmt: str, params: dict[str, object], context: object, many: bool) -> None:
        statements.append((stmt, params))

    async with factory() as observer:
        connection = await observer.session.connection()
        sync_connection = connection.sync_connection
        assert sync_connection is not None
        engine = sync_connection.engine
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            page = await ListTimeline(factory, Base64TimelineCursorCodec()).execute(request, owner)
        finally:
            event.remove(engine, 'before_cursor_execute', capture)
        assert len(statements) == 1
        if explain:
            statement, params = statements[0]
            plan = await connection.exec_driver_sql(f'EXPLAIN (ANALYZE, BUFFERS) {statement}', params)
            print(f'Timeline plan for {explain}\n' + '\n'.join(str(line) for line in plan.scalars()))
    return page



def ids(page: TimelinePage) -> list[int]:
    return [item.id for item in page.items]


async def test_overlapping_follows_and_credit_roles_return_one_movie_per_owned_id(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        owner, other = await seed_owners(uow)
        shared = MovieRow(tmdb_id=1, title='Shared', release_date=PAST, overview='Overview', tmdb_poster_path='///valid.jpg')
        private = MovieRow(tmdb_id=2, title='Private', release_date=PAST, tmdb_poster_path='https://outside.invalid/image.jpg')
        uow.session.add_all([shared, private])
        await uow.session.flush()
        uow.session.add_all([
            CreditRow(tmdb_id='actor', movie_id=shared.id, person_id=1, credit_type='cast'),
            CreditRow(tmdb_id='actor-director', movie_id=shared.id, person_id=1, credit_type='crew'),
            CreditRow(tmdb_id='director', movie_id=shared.id, person_id=2, credit_type='crew'),
            CreditRow(tmdb_id='other', movie_id=private.id, person_id=3, credit_type='crew'),
        ])
        await uow.commit()

    owner_page = await read(timeline_uows, owner)
    assert owner_page.items == (
        MovieSummary(shared.id, 'Shared', 'Overview', 'https://image.tmdb.org/t/p/w500/valid.jpg', PAST),
    )
    assert owner_page.older_cursor is None and owner_page.newer_cursor is None
    assert (await read(timeline_uows, other)).items == (MovieSummary(private.id, 'Private', None, None, PAST),)


async def test_initial_includes_today_using_utc_in_the_same_transaction(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        today, hour = (await uow.session.execute(text("""
            SELECT utc::date, EXTRACT(hour FROM utc)
            FROM (SELECT CURRENT_TIMESTAMP AT TIME ZONE 'UTC' AS utc) AS clock
        """))).one()
        zone = '+12:00' if hour >= 12 else '-12:00'
        await uow.session.execute(text(f"SET LOCAL TIME ZONE INTERVAL '{zone}' HOUR TO MINUTE"))
        assert await uow.session.scalar(text("SELECT CURRENT_DATE")) != today
        owner, _ = await seed_owners(uow)
        past, current, _ = await seed_movies(uow, today - timedelta(days=1), today, today + timedelta(days=1))
        await uow.session.flush()

        window = await uow.timeline.read(owner.profile_id, TimelineSelection('initial', 20))

        assert window.as_of == today
        assert [item.id for item in window.items] == [current, past]
        assert window.has_newer and not window.has_older


async def test_future_only_initial_keeps_newer_cursor(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        owner, _ = await seed_owners(uow)
        first, second, third = await seed_movies(uow, FUTURE, FUTURE, FUTURE)
        await uow.commit()

    page = await read(timeline_uows, owner, TimelineRequest(limit=2))
    assert page.items == () and page.older_cursor is None
    assert page.newer_cursor is not None and page.as_of is not None
    assert Base64TimelineCursorCodec().decode(page.newer_cursor, owner.profile_id) == TimelineCursor('future_boundary', page.as_of)

    newer = await read(timeline_uows, owner, TimelineRequest(limit=2, cursor=page.newer_cursor, direction='newer'))
    assert ids(newer) == [second, first]
    assert newer.as_of is None and newer.older_cursor is None and newer.newer_cursor
    end = await read(timeline_uows, owner, TimelineRequest(limit=2, cursor=newer.newer_cursor, direction='newer'))
    assert ids(end) == [third]
    assert end.older_cursor is not None and end.newer_cursor is None


async def test_future_boundary_request_uses_the_original_date_after_midnight(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        today = await uow.session.scalar(text(UTC_DAY))
        assert isinstance(today, date)
        yesterday = today - timedelta(days=1)
        owner, _ = await seed_owners(uow)
        _, _, current, future = await seed_movies(uow, yesterday, yesterday, today, today + timedelta(days=1))
        await uow.commit()

    # Today's transaction simulates consuming a cursor from an initial response yesterday.
    cursor = Base64TimelineCursorCodec().encode(TimelineCursor('future_boundary', yesterday), owner.profile_id)
    page = await read(timeline_uows, owner, TimelineRequest(cursor=cursor, direction='newer'))
    assert ids(page) == [future, current]
    assert page.as_of is None and page.older_cursor is not None and page.newer_cursor is None


async def test_same_day_keysets_walk_both_directions_without_gaps(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        owner, _ = await seed_owners(uow)
        first, second, third, fourth, fifth = await seed_movies(uow, *([PAST] * 5))
        await uow.commit()

    top = await read(timeline_uows, owner, TimelineRequest(limit=2))
    assert ids(top) == [fifth, fourth]
    assert top.older_cursor and top.newer_cursor is None

    middle = await read(timeline_uows, owner, TimelineRequest(2, top.older_cursor, 'older'))
    assert ids(middle) == [third, second]
    assert middle.older_cursor and middle.newer_cursor and middle.as_of is None

    bottom = await read(timeline_uows, owner, TimelineRequest(2, middle.older_cursor, 'older'))
    assert ids(bottom) == [first]
    assert bottom.older_cursor is None and bottom.newer_cursor and bottom.as_of is None

    back = await read(timeline_uows, owner, TimelineRequest(2, bottom.newer_cursor, 'newer'))
    assert ids(back) == [third, second]
    assert back.older_cursor and back.newer_cursor and back.as_of is None

    newest = await read(timeline_uows, owner, TimelineRequest(2, back.newer_cursor, 'newer'))
    assert ids(newest) == [fifth, fourth]
    assert newest.older_cursor and newest.newer_cursor is None and newest.as_of is None


async def test_deleted_cursor_and_anchor_continue_from_sort_values(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        owner, _ = await seed_owners(uow)
        first, second, third, fourth = await seed_movies(uow, *([PAST] * 4))
        await uow.commit()
    top = await read(timeline_uows, owner, TimelineRequest(limit=2))
    assert ids(top) == [fourth, third] and top.older_cursor

    async with timeline_uows() as uow:
        await remove_movies(uow, third)
    older = await read(timeline_uows, owner, TimelineRequest(2, top.older_cursor, 'older'))
    assert ids(older) == [second, first]
    assert older.older_cursor is None and older.newer_cursor is not None

    anchor = TimelineRequest(anchor_date=PAST, anchor_id=third)
    anchored = await read(timeline_uows, owner, anchor)
    assert ids(anchored) == [fourth, second, first] and anchored.anchor_index == 1

    async with timeline_uows() as uow:
        await remove_movies(uow, first, second)
    anchored = await read(timeline_uows, owner, anchor)
    assert ids(anchored) == [fourth] and anchored.anchor_index is None
    assert anchored.older_cursor is None and anchored.newer_cursor is None

    exhausted = await read(timeline_uows, owner, TimelineRequest(2, top.older_cursor, 'older'))
    assert (exhausted.items, exhausted.older_cursor, exhausted.newer_cursor, exhausted.as_of) == ((), None, None, None)


async def test_default_anchored_window_is_bounded(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        owner, _ = await seed_owners(uow)
        movies = await seed_movies(uow, *([PAST] * 50))
        await uow.commit()

    page = await read(timeline_uows, owner, TimelineRequest(anchor_date=PAST, anchor_id=movies[24]))
    assert ids(page) == movies[44:4:-1]
    assert len(page.items) == 40 and page.anchor_index == 20
    assert page.as_of is not None
    assert page.older_cursor and page.newer_cursor


async def test_empty_catalog_keeps_initial_and_anchor_boundary_metadata(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        owner, _ = await seed_owners(uow)
        await uow.commit()

    for request in (TimelineRequest(), TimelineRequest(anchor_date=PAST, anchor_id=1)):
        page = await read(timeline_uows, owner, request)
        assert page.items == () and page.as_of is not None and page.anchor_index is None
        assert page.older_cursor is None and page.newer_cursor is None


async def test_representative_sparse_and_overlapping_query_plans(timeline_uows: TimelineUows) -> None:
    async with timeline_uows() as uow:
        owner, _ = await seed_owners(uow)
        await uow.session.execute(text("""
            INSERT INTO movies (tmdb_id, title, release_date)
            SELECT i, 'Movie ' || i, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date + 1200 - (i % 8000)
            FROM generate_series(1, 50000) AS i
        """))
        await uow.session.execute(text("""
            INSERT INTO credits (tmdb_id, movie_id, person_id, credit_type)
            SELECT 'catalog-' || id, id, 3, 'cast' FROM movies
            UNION ALL
            SELECT 'actor-' || id, id, 1, 'cast' FROM movies WHERE tmdb_id % 200 = 0
            UNION ALL
            SELECT 'director-' || id, id, 2, 'crew' FROM movies WHERE tmdb_id % 300 = 0
        """))
        await uow.session.execute(text("ANALYZE movies, credits, follows"))
        index_names = (await uow.session.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename IN ('movies', 'credits', 'follows')
        """))).scalars()
        assert set(index_names) >= {
            'ix_movies_release_date_id', 'ix_credits_person_id_movie_id',
            'ix_credits_movie_id_person_id', 'follows_pkey',
        }
        await uow.commit()

    initial = await read(timeline_uows, owner, explain='initial')
    assert len(initial.items) == len(set(ids(initial))) == 20
    assert initial.older_cursor and initial.newer_cursor
    older = await read(
        timeline_uows, owner, TimelineRequest(cursor=initial.older_cursor, direction='older'), explain='older',
    )
    assert older.newer_cursor and older.items[0].release_date <= initial.items[-1].release_date
    newer = await read(
        timeline_uows, owner, TimelineRequest(cursor=older.newer_cursor, direction='newer'), explain='newer',
    )
    assert ids(newer) == ids(initial)
    future = await read(
        timeline_uows, owner, TimelineRequest(cursor=initial.newer_cursor, direction='newer'), explain='future boundary',
    )
    assert initial.as_of and all(item.release_date > initial.as_of for item in future.items)

    oldest = initial.items[-1]
    anchored = await read(
        timeline_uows, owner, TimelineRequest(anchor_date=oldest.release_date, anchor_id=oldest.id), explain='anchored',
    )
    assert len(anchored.items) == len(set(ids(anchored))) == 40
    assert anchored.anchor_index == 20 and anchored.items[20].id == oldest.id
