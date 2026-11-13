from functools import partial

import httpx
import pytest

from lumiere.api import create_api
from lumiere.config import Settings
from lumiere.runtime import compose_api
from lumiere.search import ProviderRef, SearchPerson, search_people


class PermittedAdmission:
    def acquire(self):
        return True

    def release(self):
        pass


async def test_public_api_accepts_an_injected_search_capability():
    async def search(name):
        return [SearchPerson(ProviderRef("tmdb", "person", "42"), name, None, None, ())]

    app = create_api(
        Settings(),
        search,
        PermittedAdmission(),
        lambda: {"incoming_admitted": 1, "provider_attempts": 0},
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/people/search", params={"query": "  Supplied search  "}
        )

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "provider_ref": {
                    "provider": "tmdb",
                    "entity_type": "person",
                    "id": "42",
                },
                "name": "Supplied search",
                "portrait_url": None,
                "department": None,
                "known_for": [],
            }
        ]
    }


async def test_result_selection_is_independent_of_the_provider_adapter():
    class ReplacementProvider:
        async def search_people(self, name):
            return [
                SearchPerson(
                    ProviderRef("tmdb", "person", "1"),
                    "First",
                    None,
                    None,
                    ("One", "Two", "Three", "Four"),
                ),
                SearchPerson(
                    ProviderRef("tmdb", "person", "1"), "Duplicate", None, None, ()
                ),
                *[
                    SearchPerson(
                        ProviderRef("tmdb", "person", str(n)),
                        f"Person {n}",
                        None,
                        None,
                        (),
                    )
                    for n in range(2, 10)
                ],
            ]

    search = partial(search_people, provider=ReplacementProvider(), max_query_chars=200)
    app = create_api(Settings(), search, PermittedAdmission(), dict)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.get("/api/people/search?query=First")

    assert response.status_code == 200
    people = response.json()["results"]
    assert [row["name"] for row in people] == [
        "First",
        "Person 2",
        "Person 3",
        "Person 4",
        "Person 5",
        "Person 6",
        "Person 7",
    ]
    assert people[0]["known_for"] == ["One", "Two", "Three"]


@pytest.mark.asyncio
async def test_search_translates_first_page_into_small_transient_contract():
    attempts = []

    async def tmdb(request):
        attempts.append(request)
        return httpx.Response(
            200,
            json={
                "page": 1,
                "results": [
                    {
                        "id": 4139,
                        "name": "Tom Skerritt",
                        "profile_path": "/portrait.jpg",
                        "known_for_department": "Acting",
                        "known_for": [
                            {"media_type": "movie", "title": "Alien"},
                            {"media_type": "tv", "name": "Picket Fences"},
                        ],
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(tmdb)) as provider:
        app = compose_api(Settings(tmdb_token="test-secret"), provider)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/people/search", params={"query": "  Tóm  S  "}
            )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=60"
    assert response.json() == {
        "results": [
            {
                "provider_ref": {
                    "provider": "tmdb",
                    "entity_type": "person",
                    "id": "4139",
                },
                "name": "Tom Skerritt",
                "portrait_url": "https://image.tmdb.org/t/p/w180_and_h180_face/portrait.jpg",
                "department": "Acting",
                "known_for": ["Alien", "Picket Fences"],
            }
        ]
    }
    assert len(attempts) == 1
    assert attempts[0].url.path == "/3/search/person"
    assert dict(attempts[0].url.params) == {"query": "Tóm  S", "page": "1"}
    assert attempts[0].headers["authorization"] == "Bearer test-secret"


async def request_with(
    payload, query="Tom", *, status=200, settings=None, failure=None
):
    attempts = []

    async def tmdb(request):
        attempts.append(request)
        if failure:
            raise failure
        return httpx.Response(status, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(tmdb)) as provider:
        app = compose_api(settings or Settings(tmdb_token="test-secret"), provider)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/people/search", params={} if query is None else {"query": query}
            )
    return response, attempts


async def test_invalid_rows_are_skipped_and_first_valid_duplicates_keep_provider_order():
    rows = [
        None,
        {},
        {"id": True, "name": "boolean"},
        {"id": "2", "name": "string"},
        {"id": 0, "name": "zero"},
        {"id": 2, "name": "  "},
        {
            "id": 2,
            "name": "First",
            "popularity": 0,
            "profile_path": "//first.jpg",
            "known_for_department": "  Directing  ",
            "known_for": [
                None,
                {"media_type": "movie", "name": "wrong field"},
                {"media_type": "movie", "title": "  "},
                {"media_type": "tv", "name": "  Series  "},
                {"media_type": "person", "name": "wrong type"},
                {"media_type": "movie", "title": "Film"},
                {"media_type": "movie", "title": "Third"},
                {"media_type": "tv", "name": "Fourth"},
            ],
        },
        {"id": 2, "name": "Duplicate", "popularity": 999},
        {
            "id": 3,
            "name": "Second",
            "profile_path": "https://evil.test/a.jpg",
            "known_for": {},
            "known_for_department": 12,
        },
    ]
    rows += [{"id": n, "name": f"Person {n}"} for n in range(4, 15)]
    response, attempts = await request_with({"results": rows, "total_pages": 99})
    people = response.json()["results"]
    assert [p["name"] for p in people] == [
        "First",
        "Second",
        "Person 4",
        "Person 5",
        "Person 6",
        "Person 7",
        "Person 8",
    ]
    assert (
        people[0]["portrait_url"]
        == "https://image.tmdb.org/t/p/w180_and_h180_face/first.jpg"
    )
    assert people[0]["department"] == "Directing"
    assert people[0]["known_for"] == ["Series", "Film", "Third"]
    assert people[1] == {
        "provider_ref": {"provider": "tmdb", "entity_type": "person", "id": "3"},
        "name": "Second",
        "portrait_url": None,
        "department": None,
        "known_for": [],
    }
    assert len(attempts) == 1


@pytest.mark.parametrize("query", [None, "", " \t\n ", "x" * 201, "é" * 1000])
async def test_rejected_input_never_calls_provider(query):
    response, attempts = await request_with({"results": []}, query)
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.content == b""
    assert attempts == []


@pytest.mark.parametrize(
    "payload", [{"results": []}, {"results": [None, {}, {"id": 2, "name": " "}]}]
)
async def test_readable_empty_searches_are_cacheable_successes(payload):
    response, attempts = await request_with(payload)
    assert response.status_code == 200
    assert response.json() == {"results": []}
    assert response.headers["cache-control"] == "private, max-age=60"
    assert len(attempts) == 1


@pytest.mark.parametrize(
    "payload,status,failure",
    [
        ({}, 200, None),
        ({"results": None}, 200, None),
        ([], 200, None),
        ({"results": []}, 401, None),
        ({"results": []}, 429, None),
        ({"results": []}, 503, None),
        (None, 200, httpx.ReadTimeout("secret query")),
        (None, 200, httpx.ConnectError("secret credential")),
    ],
)
async def test_provider_failure_is_status_only_without_retry(payload, status, failure):
    response, attempts = await request_with(payload, status=status, failure=failure)
    assert response.status_code == 500
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    assert len(attempts) == 1


async def test_oversized_provider_response_is_rejected():
    response, attempts = await request_with(
        {"results": [], "padding": "x" * 200},
        settings=Settings(tmdb_token="test", max_provider_bytes=50),
    )
    assert response.status_code == 500
    assert len(attempts) == 1


async def test_public_api_bounds_incoming_and_outgoing_work_without_waiting():
    import asyncio

    started = asyncio.Event()
    finish = asyncio.Event()
    attempts = []

    async def tmdb(request):
        attempts.append(request)
        started.set()
        await finish.wait()
        return httpx.Response(200, json={"results": []})

    settings = Settings(
        tmdb_token="test",
        incoming_concurrency=2,
        outgoing_concurrency=1,
        admission_total=3,
    )
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(tmdb)) as provider,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(compose_api(settings, provider)),
            base_url="http://test",
        ) as client,
    ):
        pending = asyncio.create_task(client.get("/api/people/search?query=A"))
        await started.wait()
        denied = await client.get("/api/people/search?query=B")
        assert denied.status_code == 500
        assert denied.headers["cache-control"] == "no-store"
        assert len(attempts) == 1
        finish.set()
        assert (await pending).status_code == 200
        assert (await client.get("/api/people/search?query=C")).status_code == 200
        assert (await client.get("/api/people/search?query=D")).status_code == 500
        assert len(attempts) == 2


async def test_total_provider_deadline_is_bounded_and_logs_exclude_content(caplog):
    import asyncio
    import logging

    caplog.set_level(logging.INFO, logger="lumiere.operations")

    async def tmdb(request):
        await asyncio.sleep(0.2)
        return httpx.Response(200, json={"results": []})

    settings = Settings(
        tmdb_token="credential-secret", provider_timeout=0.02, operation_timeout=0.05
    )
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(tmdb)) as provider,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(compose_api(settings, provider)),
            base_url="http://test",
        ) as client,
    ):
        response = await client.get("/api/people/search?query=private-name")
    assert response.status_code == 500
    assert "private-name" not in caplog.text
    assert "credential-secret" not in caplog.text
    assert '"outcome": "failed"' in caplog.text
    assert '"provider_attempts": 1' in caplog.text
    assert '"elapsed_ms":' in caplog.text


@pytest.mark.parametrize(
    "bound", ["incoming_concurrency", "admissions_per_minute", "admission_total"]
)
async def test_incoming_admission_refuses_before_provider_and_never_retries(bound):
    import asyncio

    started = asyncio.Event()
    finish = asyncio.Event()
    attempts = []

    async def tmdb(request):
        attempts.append(request)
        started.set()
        await finish.wait()
        return httpx.Response(200, json={"results": []})

    settings = Settings(tmdb_token="test", **{bound: 1})
    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(tmdb)) as provider,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(compose_api(settings, provider)),
            base_url="http://test",
        ) as client,
    ):
        pending = asyncio.create_task(client.get("/api/people/search?query=First"))
        await started.wait()
        denied = await client.get("/api/people/search?query=Second")
        assert denied.status_code == 500
        assert denied.headers["cache-control"] == "no-store"
        assert len(attempts) == 1
        finish.set()
        assert (await pending).status_code == 200
        if bound == "incoming_concurrency":
            assert (
                await client.get("/api/people/search?query=Third")
            ).status_code == 200
        else:
            assert (
                await client.get("/api/people/search?query=Third")
            ).status_code == 500
            assert len(attempts) == 1


async def test_api_rejects_search_request_bodies_and_encoded_request_targets():
    attempts = []

    async def tmdb(request):
        attempts.append(request)
        return httpx.Response(200, json={"results": []})

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(tmdb)) as provider,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(
                compose_api(Settings(tmdb_token="test"), provider)
            ),
            base_url="http://test",
        ) as client,
    ):
        assert (
            await client.request(
                "GET", "/api/people/search?query=X", content=b"unneeded body"
            )
        ).status_code == 500
        assert (
            await client.get(
                "/api/people/search", params={"query": "X", "padding": "a" * 4096}
            )
        ).status_code == 500
        assert attempts == []


async def test_optional_metadata_never_hides_an_otherwise_usable_person():
    response, _ = await request_with(
        {
            "results": [
                {"id": 1, "name": "Uppercase extension", "profile_path": "/file.JPG"},
                {
                    "id": 2,
                    "name": "Broken metadata",
                    "profile_path": 123,
                    "known_for_department": {},
                    "known_for": [False, {"media_type": "movie", "title": 2}],
                },
                {"id": 3, "name": "Bad image path", "profile_path": "/../file.jpg"},
            ]
        }
    )
    assert response.status_code == 200
    assert [row["name"] for row in response.json()["results"]] == [
        "Uppercase extension",
        "Broken metadata",
        "Bad image path",
    ]
    assert response.json()["results"][0]["portrait_url"].endswith("/file.JPG")
    assert response.json()["results"][1]["known_for"] == []
    assert response.json()["results"][2]["portrait_url"] is None
