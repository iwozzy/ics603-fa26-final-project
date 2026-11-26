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


def map_filmography(dto: FilmographyDTO, identity: PersonIdentity) -> PersonFilmography:
    if dto.id != identity.provider_id:
        raise HydrationFailed("provider_identity_mismatch")

    credit_identities: dict[str, tuple[object, ...]] = {}
    credits: dict[str, FilmographyCredit] = {}
    groups: tuple[tuple[Literal["cast", "crew"], list[CreditDTO]], ...] = (
        ("cast", dto.movie_credits.cast),
        ("crew", dto.movie_credits.crew),
    )
    for credit_type, group in groups:
        for item in group:
            character = nonblank(item.character)
            department = nonblank(item.department)
            job = nonblank(item.job)
            credit_identity = (
                item.id,
                credit_type,
                character,
                item.order,
                department,
                job,
            )
            if (
                credit_identities.setdefault(item.credit_id, credit_identity)
                != credit_identity
            ):
                raise HydrationFailed("provider_credit_conflict")

            release_date = _release_date(item.release_date)
            if release_date is None or item.credit_id in credits:
                continue
            credits[item.credit_id] = FilmographyCredit(
                provider_credit_id=item.credit_id,
                movie_provider_id=item.id,
                person_provider_id=dto.id,
                title=item.title,
                overview=nonblank(item.overview),
                poster_path=profile_path(item.poster_path),
                release_date=release_date,
                credit_type=credit_type,
                character=character,
                order=item.order,
                department=department,
                job=job,
            )

    person = FilmographyPerson(identity, dto.name, nonblank(dto.known_for_department))
    return PersonFilmography(person, tuple(credits.values()))
