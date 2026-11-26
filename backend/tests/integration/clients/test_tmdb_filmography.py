import gzip
import json
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import override

import httpx
import pytest

from lumiere.adapters.outbound.clients.tmdb_filmography.client import (
    TMDBFilmographyCatalog,
)
from lumiere.domain.errors import HydrationFailed, HydrationThrottled
from lumiere.domain.filmography import FilmographyCredit, PersonFilmography
from lumiere.domain.following import PersonIdentity
from lumiere.domain.people import CatalogProvider

FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "docs/samples/api/tmdb/v3/people/details_movie_credits.json"
)
IDENTITY = PersonIdentity(CatalogProvider.TMDB, 10297)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


def movie_credit(**overrides: object) -> dict[str, object]:
    return {
        "id": 101,
        "credit_id": "acting-1",
        "title": "Film",
        "release_date": "2020-01-02",
        **overrides,
    }


def filmography_response(
    cast: object = (), crew: object = (), **overrides: object
) -> dict[str, object]:
    return {
        "id": 10297,
        "name": "Example Actor",
        "known_for_department": "Acting",
        "movie_credits": {"cast": cast, "crew": crew},
        **overrides,
    }


async def fetch_response(
    response: httpx.Response, *, max_bytes: int = 10 * 1024 * 1024
) -> PersonFilmography:
    transport = httpx.MockTransport(lambda _: response)
    async with httpx.AsyncClient(
        base_url="https://catalog.test", transport=transport
    ) as client:
        return await TMDBFilmographyCatalog(
            client, FixedClock(), max_bytes=max_bytes
        ).fetch(IDENTITY)


async def fetch_json(payload: object) -> PersonFilmography:
    return await fetch_response(httpx.Response(200, json=payload))


async def test_cast_and_crew_keep_separate_credit_ids() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=FIXTURE.read_bytes())

    async with httpx.AsyncClient(
        base_url="https://catalog.test", transport=httpx.MockTransport(respond)
    ) as client:
        payload = await TMDBFilmographyCatalog(client, FixedClock()).fetch(IDENTITY)

    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert (
        requests[0].url
        == "https://catalog.test/3/person/10297?append_to_response=movie_credits"
    )
    assert payload.person.identity == IDENTITY
    assert payload.person.name == "Matthew McConaughey"
    assert payload.person.known_for_department == "Acting"
    assert [c.credit_type for c in payload.credits] == ["cast"] * 87 + ["crew"] * 4
    credits = [c for c in payload.credits if c.movie_provider_id == 7364]
    assert [c.credit_type for c in credits] == ["cast", "crew"]
    assert {c.movie_provider_id for c in credits} == {7364}
    assert {c.person_provider_id for c in credits} == {10297}
    assert [c.provider_credit_id for c in credits] == [
        "52fe447cc3a36847f8098e35",
        "52fe447cc3a36847f8098ef1",
    ]
    assert credits[0].character == "Dirk Pitt"
    assert credits[0].order == 0
    assert credits[1].department == "Production"
    assert credits[1].job == "Executive Producer"
    assert credits[0].poster_path == "/kyY1onYxkKBDlJsheRsVbMaoQEM.jpg"


async def test_undated_movies_drop_both_movie_and_credit_inputs() -> None:
    missing_date = movie_credit(id=102, credit_id="missing")
    del missing_date["release_date"]
    payload = await fetch_json(
        filmography_response(
            cast=[
                missing_date,
                movie_credit(id=103, credit_id="blank", release_date=" "),
                movie_credit(id=104, credit_id="impossible", release_date="2023-02-29"),
                movie_credit(id=105, credit_id="compact", release_date="20200102"),
            ],
            crew=[
                movie_credit(id=106, credit_id="null", release_date=None),
                movie_credit(id=107, credit_id="not-a-date", release_date=20200102),
                movie_credit(id=108, credit_id="week-date", release_date="2020-W01-4"),
                movie_credit(id=109, credit_id="valid", release_date="2024-02-29"),
            ],
        )
    )

    assert [
        (credit.movie_provider_id, credit.provider_credit_id, credit.release_date)
        for credit in payload.credits
    ] == [
        (109, "valid", date(2024, 2, 29)),
    ]
    undated = await fetch_json(filmography_response(cast=[missing_date]))
    assert undated.person.identity == IDENTITY
    assert undated.credits == ()


async def test_optional_credit_fields_remain_nullable() -> None:
    payload = await fetch_json(
        filmography_response(
            cast=[movie_credit()],
            crew=[
                movie_credit(
                    id=102,
                    credit_id="crew-2",
                    overview=" ",
                    job=" ",
                    department=None,
                    order=None,
                    character=" ",
                )
            ],
            known_for_department=" ",
        )
    )

    assert payload.person.known_for_department is None
    assert payload.credits == (
        FilmographyCredit(
            "acting-1",
            101,
            10297,
            "Film",
            None,
            None,
            date(2020, 1, 2),
            "cast",
            None,
            None,
            None,
            None,
        ),
        FilmographyCredit(
            "crew-2",
            102,
            10297,
            "Film",
            None,
            None,
            date(2020, 1, 2),
            "crew",
            None,
            None,
            None,
            None,
        ),
    )


async def test_repeated_credits_keep_first_movie_metadata() -> None:
    first = movie_credit(
        title=" First title ",
        overview=" Overview ",
        poster_path=" //poster.jpg ",
        character=" Lead ",
    )
    payload = await fetch_json(
        filmography_response(
            cast=[
                first,
                first,
                {
                    **first,
                    "title": "Alternate title",
                    "overview": "Updated",
                    "release_date": "2021-01-02",
                },
            ],
        )
    )

    assert payload.credits == (
        FilmographyCredit(
            "acting-1",
            101,
            10297,
            "First title",
            "Overview",
            "/poster.jpg",
            date(2020, 1, 2),
            "cast",
            "Lead",
            None,
            None,
            None,
        ),
    )


@pytest.mark.parametrize(
    ("cast", "crew"),
    [
        ([movie_credit(), movie_credit(id=102)], []),
        ([movie_credit()], [movie_credit()]),
        ([movie_credit(character="Lead"), movie_credit(character="Cameo")], []),
        ([], [movie_credit(job="Director"), movie_credit(job="Producer")]),
    ],
)
async def test_reused_credit_id_with_incompatible_identity_is_terminal(
    cast: object, crew: object
) -> None:
    with pytest.raises(HydrationFailed) as failure:
        await fetch_json(filmography_response(cast=cast, crew=crew))
    assert failure.value.category == "provider_credit_conflict"
    assert not failure.value.retryable


@pytest.mark.parametrize(
    "poster_path",
    [
        None,
        "",
        " ",
        "/",
        "/../a.jpg",
        "https://external.test/a.jpg",
        "/a?b",
        "/a#b",
        "/a b.jpg",
        "/a%20b.jpg",
        ["invalid"],
    ],
)
async def test_unsafe_poster_path_becomes_null(poster_path: object) -> None:
    payload = await fetch_json(
        filmography_response(cast=[movie_credit(poster_path=poster_path)])
    )
    assert payload.credits[0].poster_path is None


async def test_mismatched_person_identity_is_terminal() -> None:
    with pytest.raises(HydrationFailed) as failure:
        await fetch_json(filmography_response(id=10298))
    assert failure.value.category == "provider_identity_mismatch"
    assert not failure.value.retryable


@pytest.mark.parametrize("identifier", [True, 0, -1, "10297", 1.5, 2**63, None])
async def test_required_ids_are_strict_positive_integers(identifier: object) -> None:
    for invalid_payload in (
        filmography_response(id=identifier),
        filmography_response(cast=[movie_credit(id=identifier)]),
    ):
        with pytest.raises(HydrationFailed) as failure:
            await fetch_json(invalid_payload)
        assert failure.value.category == "provider_response"
        assert not failure.value.retryable


async def test_provider_movie_ids_use_the_catalog_bigint_range() -> None:
    payload = await fetch_json(filmography_response(cast=[movie_credit(id=2**63 - 1)]))
    assert payload.credits[0].movie_provider_id == 2**63 - 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", " "),
        ("title", 42),
        ("title", None),
        ("credit_id", " "),
        ("credit_id", 42),
        ("credit_id", None),
        ("order", True),
        ("order", False),
        ("order", "1"),
        ("order", 1.0),
        ("character", 42),
        ("job", []),
    ],
)
async def test_invalid_credit_field_types_and_blank_required_fields_are_terminal(
    field: str, value: object
) -> None:
    invalid_credit = movie_credit(**{field: value})
    with pytest.raises(HydrationFailed) as failure:
        await fetch_json(filmography_response(cast=[invalid_credit]))
    assert not failure.value.retryable


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        filmography_response(name=" "),
        filmography_response(movie_credits=None),
        filmography_response(movie_credits={"cast": []}),
        filmography_response(cast=None),
        filmography_response(crew={}),
        filmography_response(cast=[None]),
        filmography_response(crew=[{}]),
        filmography_response(crew=[movie_credit(id=True, release_date="")]),
    ],
)
async def test_structural_errors_are_terminal(payload: object) -> None:
    with pytest.raises(HydrationFailed) as failure:
        await fetch_json(payload)
    assert failure.value.category == "provider_response"
    assert not failure.value.retryable


async def test_malformed_json_is_terminal() -> None:
    with pytest.raises(HydrationFailed) as failure:
        await fetch_response(httpx.Response(200, content=b'{"private_unparsed_value":'))
    assert failure.value.category == "provider_response"
    assert str(failure.value) == "provider_response"
    assert not failure.value.retryable


@pytest.mark.parametrize(
    ("header", "delay"),
    [
        ("120", 120.0),
        ("Thu, 26 Nov 2026 12:02:00 GMT", 120.0),
        ("Thursday, 26-Nov-26 12:02:00 GMT", 120.0),
        (
            "Tuesday, 26-Nov-69 12:02:00 GMT",
            (
                datetime(2069, 11, 26, 12, 2, tzinfo=UTC) - FixedClock().now()
            ).total_seconds(),
        ),
        ("Monday, 26-Nov-77 12:02:00 GMT", None),
        ("Thu Nov 26 12:02:00 2026", 120.0),
        ("0", 0.0),
        ("Thu, 26 Nov 2026 12:00:00 GMT", 0.0),
        ("Thu, 26 Nov 2026 11:59:59 GMT", None),
        (" \t120\t ", 120.0),
        ("   ", None),
        ("120.5", None),
        ("-120", None),
        ("+120", None),
        ("next Thursday", None),
        ("Thu, 26 Nov 2026 12:02:00", None),
        ("Thu, 26 Nov 2026 12:02:00 GMT trailing", None),
        (None, None),
    ],
)
async def test_throttle_exposes_normalized_retry_after(
    header: str | None, delay: float | None
) -> None:
    headers = {} if header is None else {"Retry-After": header}
    with pytest.raises(HydrationThrottled) as failure:
        await fetch_response(httpx.Response(429, headers=headers))
    assert failure.value.retryable
    assert failure.value.retry_after_seconds == delay


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(404, False), (401, False), (302, False), (500, True), (503, True)],
)
async def test_http_status_emits_one_attempt_with_correct_retryability(
    status: int, retryable: bool
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status,
            headers={"Location": "/redirected"},
            text="synthetic provider failure",
        )

    async with httpx.AsyncClient(
        base_url="https://catalog.test",
        transport=httpx.MockTransport(respond),
        follow_redirects=True,
    ) as client:
        with pytest.raises(HydrationFailed) as failure:
            await TMDBFilmographyCatalog(client, FixedClock()).fetch(IDENTITY)
    assert len(requests) == 1
    assert failure.value.retryable is retryable
    assert "synthetic provider failure" not in str(failure.value)


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError])
async def test_transport_failure_is_retryable_without_retrying(
    error: type[httpx.TransportError],
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise error("synthetic transport failure")

    async with httpx.AsyncClient(
        base_url="https://catalog.test", transport=httpx.MockTransport(respond)
    ) as client:
        with pytest.raises(HydrationFailed) as failure:
            await TMDBFilmographyCatalog(client, FixedClock()).fetch(IDENTITY)
    assert len(requests) == 1
    assert failure.value.retryable
    assert "synthetic transport failure" not in str(failure.value)


class CompressedBody(httpx.AsyncByteStream):
    def __init__(self, body: bytes) -> None:
        self.data = gzip.compress(body)

    @override
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self.data[:15]
        yield self.data[15:]


async def test_response_bound_applies_to_decompressed_stream() -> None:
    body = json.dumps(filmography_response(ignored_padding="x" * 1000)).encode()
    stream = CompressedBody(body)
    assert len(stream.data) < 256 < len(body)
    with pytest.raises(HydrationFailed) as failure:
        await fetch_response(
            httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=stream),
            max_bytes=256,
        )
    assert failure.value.category == "provider_oversize"
    assert not failure.value.retryable
