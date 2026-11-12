import asyncio
import json
from pathlib import Path

import httpx
import pytest

from lumiere.adapters.tmdb import TMDBSearch
from lumiere.application.search_people import SearchFailed


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_first_page_fixture_normalization_and_single_request() -> None:
    fixture = json.loads(
        (
            Path(__file__).parents[2] / "docs/samples/api/tmdb/v3/search/person.json"
        ).read_text()
    )
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=fixture)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        people = await TMDBSearch(client, "test-token").search_people("Tom")

    assert len(requests) == 1
    assert requests[0].url.path == "/3/search/person"
    assert dict(requests[0].url.params) == {"query": "Tom", "page": "1"}
    assert requests[0].headers["Authorization"] == "Bearer test-token"
    assert [person.name for person in people] == [
        person["name"] for person in fixture["results"][:7]
    ]
    assert people[0].department == "Acting"
    assert people[0].known_for == ("Alien", "Top Gun", "Contact")
    assert people[0].portrait_url == (
        "https://image.tmdb.org/t/p/w180_and_h180_face/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg"
    )


async def search(payload: object) -> list:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        return await TMDBSearch(client, "test-token").search_people("name")


@pytest.mark.anyio
async def test_tv_mixed_and_absent_hints_remain_eligible() -> None:
    people = await search(
        {
            "results": [
                {"name": "TV", "known_for": [{"media_type": "tv", "name": " Series "}]},
                {
                    "name": "Mixed",
                    "known_for": [
                        {"media_type": "person", "name": "Ignore"},
                        {"media_type": "movie", "title": " "},
                        {"media_type": "movie", "title": " Film "},
                        {"media_type": "tv", "name": "Show"},
                        {"media_type": "movie", "title": "Third"},
                        {"media_type": "movie", "title": "Fourth"},
                    ],
                },
                {"name": "Unknown"},
            ]
        }
    )
    assert [person.name for person in people] == ["TV", "Mixed", "Unknown"]
    assert [person.known_for for person in people] == [
        ("Series",),
        ("Film", "Show", "Third"),
        (),
    ]
    assert people[2].portrait_url is None
    assert people[2].department is None


@pytest.mark.anyio
async def test_skips_bad_people_before_taking_seven() -> None:
    people = await search(
        {
            "results": [None, 42, {}, {"name": " "}, {"name": 42}]
            + [{"name": f"Person {i}"} for i in range(9)]
        }
    )
    assert [person.name for person in people] == [f"Person {i}" for i in range(7)]


@pytest.mark.parametrize(
    "optional",
    [
        {"profile_path": 42, "known_for_department": [], "known_for": "bad"},
        {
            "profile_path": "https://other.example/image.jpg",
            "known_for_department": " ",
        },
        {"profile_path": "//other.example/image.jpg", "known_for": [None, 42, {}]},
        {
            "profile_path": "/../bad.jpg",
            "known_for": [{"media_type": "movie", "title": 42}],
        },
    ],
)
@pytest.mark.anyio
async def test_invalid_optional_fields_degrade_and_log_safely(
    optional: dict, caplog
) -> None:
    people = await search({"results": [{"name": "private-name", **optional}]})
    assert len(people) == 1
    assert people[0].portrait_url is None
    assert people[0].department is None
    assert people[0].known_for == ()
    assert "malformed" in caplog.text.lower()
    assert "private-name" not in caplog.text


@pytest.mark.anyio
async def test_bad_hint_does_not_remove_good_hints_or_department() -> None:
    people = await search(
        {
            "results": [
                {
                    "name": "Person",
                    "known_for_department": " Directing ",
                    "known_for": [
                        None,
                        {"media_type": "movie", "title": []},
                        {"media_type": "tv", "name": "Usable"},
                    ],
                }
            ]
        }
    )
    assert people[0].department == "Directing"
    assert people[0].known_for == ("Usable",)


@pytest.mark.anyio
async def test_genuinely_empty_page_is_successful() -> None:
    assert await search({"results": []}) == []


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"results": None},
        {"results": {}},
        {"results": [None, {}, {"name": " "}]},
    ],
)
@pytest.mark.anyio
async def test_invalid_envelope_or_all_unusable_people_fail(payload: object) -> None:
    with pytest.raises(SearchFailed):
        await search(payload)


@pytest.mark.parametrize("status", [401, 429, 500, 503])
@pytest.mark.anyio
async def test_upstream_failure_is_translated_without_retry(status: int) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, text="private upstream body")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SearchFailed):
            await TMDBSearch(client, "test-token").search_people("private-query")
    assert len(requests) == 1


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError])
@pytest.mark.anyio
async def test_transport_failure_is_translated(error) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise error("private transport details")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SearchFailed):
            await TMDBSearch(client, "test-token").search_people("name")


@pytest.mark.anyio
async def test_complete_provider_operation_has_ten_second_deadline(monkeypatch) -> None:
    original_timeout = asyncio.timeout
    deadlines = []

    def controlled_timeout(delay):
        deadlines.append(delay)
        return original_timeout(0)

    monkeypatch.setattr(asyncio, "timeout", controlled_timeout)
    requests = []

    async def delayed(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(delayed)) as client:
        with pytest.raises(SearchFailed):
            await TMDBSearch(client, "test-token").search_people("name")
    assert deadlines == [10]
    assert len(requests) == 1


@pytest.mark.anyio
async def test_invalid_json_is_a_provider_failure() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"not JSON")
        )
    ) as client:
        with pytest.raises(SearchFailed):
            await TMDBSearch(client, "test-token").search_people("name")
