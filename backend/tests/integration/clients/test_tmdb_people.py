import json
from pathlib import Path

import httpx
import pytest

from lumiere.adapters.outbound.clients.tmdb_people.client import TMDBPeopleCatalog
from lumiere.domain.errors import SearchFailed

FIXTURE = Path(__file__).resolve().parents[4] / "docs/samples/api/tmdb/v3/search/person.json"


async def test_fixture_order_titles_and_images() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=json.loads(FIXTURE.read_text()))

    async with httpx.AsyncClient(base_url="https://catalog.test", transport=httpx.MockTransport(respond)) as client:
        people = await TMDBPeopleCatalog(client).search_first_page("Tom")
    assert len(requests) == 1
    assert requests[0].url.path == "/3/search/person"
    assert dict(requests[0].url.params) == {"query": "Tom"}
    assert [p.name for p in people[:7]] == ["Tom Skerritt", "Tom Holland", "Tom Hanks", "Tom Cruise", "Tom Hopper", "Tom Hardy", "Tom Welling"]
    assert people[4].known_for == ("The Umbrella Academy", "Resident Evil: Welcome to Raccoon City", "I Feel Pretty")
    assert people[6].known_for == ("Smallville", "Lucifer", "The Fog")
    assert people[0].profile_image_url == "https://image.tmdb.org/t/p/w180_and_h180_face/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg"


async def test_strict_required_tolerant_optional_fields() -> None:
    records: list[object] = [None, 4, {}, {"id": 1, "name": " "}, {"id": 1, "name": 9}]
    records += [{"id": value, "name": "Skip"} for value in (True, "42", 0, -1, 1.5, None)]
    records += [{"id": 2, "name": " 李😀 ", "known_for_department": 7, "profile_path": "https://evil.test/image", "known_for": [{"media_type": "tv", "name": " A "}, None, {"media_type": "movie", "title": " B "}, {"media_type": "movie", "title": " "}, {"media_type": "tv", "name": "C"}, {"media_type": "movie", "title": "D"}]}, {"id": 3, "name": "Fallback", "known_for": "invalid", "profile_path": []}]
    async with httpx.AsyncClient(base_url="https://catalog.test", transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": records}))) as client:
        people = await TMDBPeopleCatalog(client).search_first_page("Timothée O'Neil & 李😀")
    assert [p.name for p in people] == ["李😀", "Fallback"]
    assert people[0].known_for == ("A", "B", "C")
    assert people[0].department is None
    assert people[0].profile_image_url is None
    assert people[1].known_for == ()
    assert people[1].profile_image_url is None


async def test_duplicates_preserve_sequence() -> None:
    rows = [{"id": 1, "name": "Tom"}, {"id": 1, "name": "Tom"}]
    async with httpx.AsyncClient(base_url="https://catalog.test", transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": rows}))) as client:
        people = await TMDBPeopleCatalog(client).search_first_page("Tom")
    assert [p.name for p in people] == ["Tom", "Tom"]


@pytest.mark.parametrize("payload", [None, [], {}, {"results": None}, {"results": {}}, {"results": "invalid"}])
async def test_bad_envelope_is_failure_not_empty(payload: object) -> None:
    async with httpx.AsyncClient(base_url="https://catalog.test", transport=httpx.MockTransport(lambda _: httpx.Response(200, content=json.dumps(payload)))) as client:
        with pytest.raises(SearchFailed):
            await TMDBPeopleCatalog(client).search_first_page("Tom")


@pytest.mark.parametrize("kind", ["timeout", "throttle", "bad_json", "oversize"])
async def test_timeout_throttle_bad_json_oversize_have_one_attempt(kind: str) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("synthetic")
        if kind == "throttle":
            return httpx.Response(429)
        return httpx.Response(200, content=b"x" * (1025 if kind == "oversize" else 1))

    async with httpx.AsyncClient(base_url="https://catalog.test", transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SearchFailed):
            await TMDBPeopleCatalog(client, max_bytes=1024).search_first_page("Tom")
    assert len(requests) == 1
