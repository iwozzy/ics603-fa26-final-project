from datetime import date
from typing import Literal

from lumiere.adapters.outbound.clients.tmdb_filmography.dto import (
    CreditDTO,
    FilmographyDTO,
)
from lumiere.adapters.outbound.clients.tmdb_people.mapper import nonblank, profile_path
from lumiere.domain.errors import HydrationFailed
from lumiere.domain.filmography import (
    FilmographyCredit,
    FilmographyPerson,
    PersonFilmography,
)
from lumiere.domain.following import PersonIdentity


def _release_date(value: object) -> date | None:
    raw = nonblank(value)
    if raw is None:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _credit_identity(credit: FilmographyCredit) -> tuple[object, ...]:
    return (
        credit.movie_provider_id,
        credit.person_provider_id,
        credit.credit_type,
        credit.character,
        credit.order,
        credit.department,
        credit.job,
    )


def map_filmography(dto: FilmographyDTO, identity: PersonIdentity) -> PersonFilmography:
    if dto.id != identity.provider_id:
        raise HydrationFailed("provider_identity_mismatch")

    credits: dict[str, FilmographyCredit] = {}
    groups: tuple[tuple[Literal["cast", "crew"], list[CreditDTO]], ...] = (
        ("cast", dto.movie_credits.cast),
        ("crew", dto.movie_credits.crew),
    )
    for credit_type, group in groups:
        for item in group:
            release_date = _release_date(item.release_date)
            if release_date is None:
                continue
            credit = FilmographyCredit(
                provider_credit_id=item.credit_id,
                movie_provider_id=item.id,
                person_provider_id=dto.id,
                title=item.title,
                overview=nonblank(item.overview),
                poster_path=profile_path(item.poster_path),
                release_date=release_date,
                credit_type=credit_type,
                character=nonblank(item.character),
                order=item.order,
                department=nonblank(item.department),
                job=nonblank(item.job),
            )
            previous = credits.setdefault(credit.provider_credit_id, credit)
            if previous is not credit and _credit_identity(
                previous
            ) != _credit_identity(credit):
                raise HydrationFailed("provider_credit_conflict")

    person = FilmographyPerson(identity, dto.name, nonblank(dto.known_for_department))
    return PersonFilmography(person, tuple(credits.values()))
