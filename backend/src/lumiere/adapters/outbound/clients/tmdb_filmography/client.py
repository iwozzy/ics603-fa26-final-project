import asyncio

import httpx
from pydantic import ValidationError

from lumiere.adapters.outbound.clients.tmdb_filmography.dto import FilmographyDTO
from lumiere.adapters.outbound.clients.tmdb_filmography.mapper import map_filmography
from lumiere.adapters.outbound.clients.tmdb_filmography.response_body import read_body
from lumiere.adapters.outbound.clients.tmdb_filmography.retry_after import (
    parse_retry_after,
)
from lumiere.application.ports.clock import Clock
from lumiere.domain.errors import HydrationFailed, HydrationThrottled
from lumiere.domain.filmography import PersonFilmography
from lumiere.domain.following import PersonIdentity


class TMDBFilmographyCatalog:
    def __init__(
        self,
        client: httpx.AsyncClient,
        clock: Clock,
        *,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.client = client
        self.clock = clock
        self.max_bytes = max_bytes

    async def fetch(self, identity: PersonIdentity) -> PersonFilmography:
        try:
            async with asyncio.timeout(5):
                async with self.client.stream(
                    "GET",
                    f"/3/person/{identity.provider_id}",
                    params={"append_to_response": "movie_credits"},
                    headers={"Accept-Encoding": "gzip, identity"},
                    follow_redirects=False,
                ) as response:
                    if response.status_code == 429:
                        delay = parse_retry_after(
                            response.headers.get("Retry-After"), self.clock.now()
                        )
                        raise HydrationThrottled(delay)
                    if not response.is_success:
                        raise HydrationFailed(
                            "provider_status", retryable=response.is_server_error
                        )
                    body = await read_body(response, self.max_bytes)
            dto = FilmographyDTO.model_validate_json(body)
        except (httpx.TransportError, TimeoutError):
            raise HydrationFailed("provider_transport", retryable=True) from None
        except (httpx.DecodingError, ValidationError):
            raise HydrationFailed("provider_response") from None
        return map_filmography(dto, identity)
