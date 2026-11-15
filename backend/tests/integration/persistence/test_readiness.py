from collections.abc import Callable

import httpx

from lumiere.adapters.outbound.persistence.unit_of_work import PostgresAccessUnitOfWork
from lumiere.bootstrap import build_container
from lumiere.config import Settings
from lumiere.main import create_app
from tests.integration.persistence.conftest import TEST_DATABASE_URL


async def test_readiness_uses_database_without_provider(uows: Callable[[], PostgresAccessUnitOfWork]) -> None:
    settings = Settings(database_url=TEST_DATABASE_URL, tmdb_access_token="synthetic-test-only", ip_hash_key="synthetic-test-only", tmdb_base_url="http://127.0.0.1:1", **dict.fromkeys(("global_requests_per_minute", "session_requests_per_minute", "ip_requests_per_minute", "bootstrap_requests_per_ip_per_minute", "global_provider_daily", "session_provider_daily", "ip_provider_daily", "global_provider_total", "session_provider_total", "ip_provider_total"), 10))  # type: ignore[arg-type]
    container = build_container(settings)
    requests: list[httpx.Request] = []

    async def record(request: httpx.Request) -> None:
        requests.append(request)

    container.client.event_hooks["request"].append(record)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(container.services)), base_url="http://app.test") as client:
            assert (await client.get("/health/live")).status_code == 200
            assert (await client.get("/health/ready")).status_code == 200
        assert requests == []
    finally:
        await container.close()
