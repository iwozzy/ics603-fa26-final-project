import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import asdict
from time import monotonic

from fastapi import FastAPI, Request, Response

from .config import Settings
from .schemas import SearchResponse
from .search import Admission, SearchOperation, SearchUnavailable, normalize_search_name

logger = logging.getLogger("lumiere.operations")


def create_api(
    settings: Settings,
    search: SearchOperation,
    incoming: Admission,
    usage: Callable[[], dict[str, int]],
) -> FastAPI:
    app = FastAPI(title="Lumiere", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/api/people/search", response_model=SearchResponse)
    async def people(request: Request):
        start = monotonic()
        outcome = "rejected"
        acquired = False
        try:
            name = normalize_search_name(
                request.query_params.get("query", ""), settings.max_query_chars
            )
            target_size = len(request.scope.get("raw_path", b"")) + len(
                request.scope.get("query_string", b"")
            )
            if (
                target_size > settings.max_target_bytes
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
                results = await search(name)
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
                        **usage(),
                    }
                )
            )

    return app
