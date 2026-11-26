from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from lumiere.adapters.outbound.clients.tmdb_people.mapper import profile_path
from lumiere.domain.timeline import (
    MovieSummary,
    TimelineMode,
    TimelineSelection,
    TimelineWindow,
)

_ELIGIBLE = """
    EXISTS (
        SELECT 1
        FROM credits
        JOIN follows ON follows.person_id = credits.person_id
        WHERE credits.movie_id = movies.id AND follows.profile_id = :profile_id
    )
"""
_MOVIE_KEY = '(release_date, id)'
_POSITION = '(:position_date, :position_id)'
_TODAY = "(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date"
_AS_OF = '(SELECT as_of FROM params)'


def _scan(predicate: str, *, newer: bool) -> str:
    order = 'ASC' if newer else 'DESC'
    return f"""
        SELECT id, title, overview, tmdb_poster_path, release_date, {newer} AS is_newer
        FROM movies
        WHERE {predicate} AND {_ELIGIBLE}
        ORDER BY release_date {order}, id {order}
        LIMIT :scan_limit
    """


def _available(predicate: str) -> str:
    return f'EXISTS (SELECT 1 FROM movies WHERE {predicate} AND {_ELIGIBLE})'


def _statement(mode: TimelineMode) -> TextClause:
    as_of = _TODAY if mode in ('initial', 'anchored') else 'NULL::date'
    opposite_older = opposite_newer = 'FALSE'

    # An opposite probe includes a surviving row cursor. Because each scan
    # starts at the closest eligible movie, there can be no skipped rows
    # between that edge and the cursor.
    match mode:
        case 'initial':
            candidates = _scan(f'release_date <= {_AS_OF}', newer=False)
            opposite_newer = _available(f'release_date > {_AS_OF}')
        case 'older':
            candidates = _scan(f'{_MOVIE_KEY} < {_POSITION}', newer=False)
            opposite_newer = _available(f'{_MOVIE_KEY} >= {_POSITION}')
        case 'newer':
            candidates = _scan(f'{_MOVIE_KEY} > {_POSITION}', newer=True)
            opposite_older = _available(f'{_MOVIE_KEY} <= {_POSITION}')
        case 'future_boundary':
            candidates = _scan('release_date > :boundary_date', newer=True)
            opposite_older = _available('release_date <= :boundary_date')
        case 'anchored':
            older = _scan(f'{_MOVIE_KEY} <= {_POSITION}', newer=False)
            newer = _scan(f'{_MOVIE_KEY} > {_POSITION}', newer=True)
            candidates = f'({older}) UNION ALL ({newer})'

    return text(f"""
        WITH params AS (SELECT {as_of} AS as_of),
        candidates AS ({candidates}),
        metadata AS (
            SELECT as_of, {opposite_older} AS opposite_older, {opposite_newer} AS opposite_newer
            FROM params
        )
        SELECT candidates.*, metadata.*
        FROM metadata LEFT JOIN candidates ON TRUE
        ORDER BY candidates.release_date DESC, candidates.id DESC
    """)


_STATEMENTS = {mode: _statement(mode) for mode in (
    'initial', 'older', 'newer', 'future_boundary', 'anchored',
)}


class PostgresTimelineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def read(self, profile_id: UUID, selection: TimelineSelection) -> TimelineWindow:
        params: dict[str, UUID | date | int] = {'profile_id': profile_id, 'scan_limit': selection.limit + 1}
        if selection.position is not None:
            params.update(position_date=selection.position.release_date, position_id=selection.position.id)
        if selection.boundary_date is not None:
            params['boundary_date'] = selection.boundary_date

        rows = (await self.session.execute(_STATEMENTS[selection.mode], params)).all()
        older: list[MovieSummary] = []
        newer: list[MovieSummary] = []
        for row in rows:
            if row.id is not None:
                path = profile_path(row.tmdb_poster_path)
                movie = MovieSummary(
                    id=row.id, title=row.title, overview=row.overview, release_date=row.release_date,
                    poster_image_url=f'https://image.tmdb.org/t/p/w500{path}' if path else None,
                )
                (newer if row.is_newer else older).append(movie)

        # The SQL output is descending. The extra row is at the top for the
        # ascending newer scan and at the bottom for the descending older scan.
        limit = selection.limit
        kept_newer = newer[-limit:]
        metadata = rows[0]
        return TimelineWindow(
            items=tuple(kept_newer + older[:limit]),
            has_older=metadata.opposite_older or len(older) > limit,
            has_newer=metadata.opposite_newer or len(newer) > limit,
            as_of=metadata.as_of,
            anchor_index=len(kept_newer) if selection.mode == 'anchored' and older else None,
        )
