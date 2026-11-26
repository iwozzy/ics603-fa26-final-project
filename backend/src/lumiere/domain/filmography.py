from dataclasses import dataclass
from datetime import date
from typing import Literal

from lumiere.domain.following import PersonIdentity


@dataclass(frozen=True)
class FilmographyPerson:
    identity: PersonIdentity
    name: str
    known_for_department: str | None


@dataclass(frozen=True)
class FilmographyCredit:
    provider_credit_id: str
    movie_provider_id: int
    person_provider_id: int
    title: str
    overview: str | None
    poster_path: str | None
    release_date: date
    credit_type: Literal["cast", "crew"]
    character: str | None
    order: int | None
    department: str | None
    job: str | None


@dataclass(frozen=True)
class PersonFilmography:
    person: FilmographyPerson
    credits: tuple[FilmographyCredit, ...]
