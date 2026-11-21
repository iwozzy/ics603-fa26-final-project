import asyncio
from collections.abc import Callable

import httpx
from pydantic import ValidationError

from lumiere.adapters.outbound.clients.tmdb_people.dto import Envelope, PersonDTO
from lumiere.adapters.outbound.clients.tmdb_people.mapper import map_person
from lumiere.domain.errors import SearchFailed
from lumiere.domain.people import PersonSummary


class TMDBPeopleCatalog:
    def __init__(self, client: httpx.AsyncClient, max_bytes: int = 1048576, report: Callable[[int, int], None] | None = None) -> None:
        self.client = client
        self.max_bytes = max_bytes
        self.report = report

    async def search_first_page(self, query: str) -> tuple[PersonSummary, ...]:
        try:
            async with asyncio.timeout(5):
                async with self.client.stream("GET", "/3/search/person", params={"query": query}) as response:
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > self.max_bytes:
                            raise SearchFailed("provider_oversize")
            envelope = Envelope.model_validate_json(bytes(data))
        except (httpx.HTTPError, ValidationError, TimeoutError, ValueError):
            raise SearchFailed("provider_response") from None
        people: list[PersonSummary] = []
        for raw in envelope.results:
            try:
                person = map_person(PersonDTO.model_validate(raw))
            except ValidationError:
                continue
            if person is not None:
                people.append(person)
        if self.report:
            try:
                self.report(min(len(people), 7), len(envelope.results) - len(people))
            except Exception:  # noqa: BLE001, S110 — diagnostics cannot fail catalog mapping
                pass
        return tuple(people)
