import asyncio
import json
import logging
from dataclasses import asdict
from time import monotonic

import httpx
from fastapi import FastAPI, Request, Response

from .admission import LocalAdmission
from .config import Settings
from .schemas import SearchResponse
from .search import SearchUnavailable, search_people
from .tmdb import TmdbPeople

logger = logging.getLogger("wayfinder.operations")


def create_api(settings: Settings, client: httpx.AsyncClient) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    incoming = LocalAdmission(
        settings.incoming_concurrency,
        settings.admissions_per_minute,
        settings.admission_total,
    )
    outgoing = LocalAdmission(
        settings.outgoing_concurrency,
        settings.admissions_per_minute,
        settings.admission_total,
    )
    provider = TmdbPeople(client, settings, outgoing)

    @app.get("/api/people/search", response_model=SearchResponse)
    async def people(request: Request):
        start = monotonic()
        outcome = "rejected"
        acquired = False
        try:
            raw_query = request.query_params.get("query", "")
            name = raw_query.strip()
            target_size = len(request.scope.get("raw_path", b"")) + len(
                request.scope.get("query_string", b"")
            )
            if (
                not name
                or len(name) > settings.max_query_chars
                or target_size > settings.max_target_bytes
                or request.headers.get("transfer-encoding")
                or request.headers.get("content-length", "0") != "0"
            ):
                raise SearchUnavailable()
            acquired = incoming.acquire()
            if not acquired:
                outcome = "admission_denied"
                raise SearchUnavailable()
            outcome = "failed"
            async with asyncio.timeout(settings.operation_timeout):
                results = await search_people(name, provider)
            body = SearchResponse.model_validate(
                {
                    "results": [
                        asdict(row) | {"known_for": list(row.known_for)}
                        for row in results
                    ]
                }
            )
            outcome = "success" if results else "empty"
            return Response(
                body.model_dump_json(),
                media_type="application/json",
                headers={"Cache-Control": "private, max-age=60"},
            )
        except (SearchUnavailable, TimeoutError):
            return Response(status_code=500, headers={"Cache-Control": "no-store"})
        except Exception:  # noqa: BLE001 - redact all unexpected boundary failures
            # Status-only boundary; never expose/log exception values or request data.
            outcome = "internal_failure"
            return Response(status_code=500, headers={"Cache-Control": "no-store"})
        finally:
            if acquired:
                incoming.release()
            logger.info(
                json.dumps(
                    {
                        "operation": "people_search",
                        "outcome": outcome,
                        "elapsed_ms": round((monotonic() - start) * 1000, 2),
                        "incoming_admitted": incoming.admitted,
                        "provider_attempts": outgoing.admitted,
                    }
                )
            )

    return app
