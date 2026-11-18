"""Explicit export check, using a mocked provider and existing process configuration."""

import asyncio
import os

import httpx
from opentelemetry.trace import get_current_span

from lumiere.adapters.tmdb import TMDBSearch
from lumiere.bootstrap import create_app
from lumiere.config import Settings


async def smoke() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"results": [{"name": "Smoke fixture"}]}
            )
        )
    ) as provider_client:
        metadata = TMDBSearch(provider_client, "fixture")
        app = create_app(Settings(telemetry_enabled=True), metadata=metadata)
        async with app.router.lifespan_context(app):
            metadata.telemetry = app.state.telemetry
            with app.state.telemetry.span(
                "F001 exported tracing smoke", feature="F001"
            ):
                trace_id = get_current_span().get_span_context().trace_id
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://smoke"
                ) as client:
                    response = await client.get(
                        "/api/people/search", params={"query": "smoke"}
                    )
                    if response.status_code != 200:
                        raise RuntimeError("Smoke request failed")
            if not app.state.telemetry.force_flush():
                raise RuntimeError("Telemetry flush did not finish")
        print(f"Trace submitted: {trace_id:032x}")
        print("Verify HTTP request and TMDB people search share this trace in Logfire.")
        print("A successful flush alone does not confirm remote receipt.")


if __name__ == "__main__":
    if not os.environ.get("LOGFIRE_TOKEN"):
        raise SystemExit(
            "Export configuration unavailable in the process; smoke check not run."
        )
    asyncio.run(smoke())
