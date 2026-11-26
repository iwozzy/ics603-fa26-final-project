from typing import Protocol

from lumiere.domain.filmography import PersonFilmography
from lumiere.domain.following import PersonIdentity


class FilmographyCatalog(Protocol):
    async def fetch(self, identity: PersonIdentity) -> PersonFilmography: ...
