import logging

import pytest
from httpx import ASGITransport, AsyncClient

from lumiere.bootstrap import create_app
from lumiere.config import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("LUMIERE_TELEMETRY_ENABLED", "false")
    return Settings()


@pytest.mark.anyio
async def test_health_and_openapi(settings: Settings) -> None:
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "/health" in (await client.get("/openapi.json")).json()["paths"]
        assert (
            "/api/people/search" in (await client.get("/openapi.json")).json()["paths"]
        )


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [("http://localhost:8081", True), ("https://untrusted.example", False)],
)
@pytest.mark.anyio
async def test_cors(settings: Settings, origin: str, allowed: bool) -> None:
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.get("/health", headers={"Origin": origin})
        assert (
            response.headers.get("access-control-allow-origin") == origin
        ) == allowed


@pytest.mark.anyio
async def test_failure_is_generic_and_request_data_is_not_logged(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(settings)

    @app.get("/broken")
    async def broken() -> None:
        raise RuntimeError("private upstream payload")

    with caplog.at_level(logging.INFO, logger="lumiere"):
        async with (
            app.router.lifespan_context(app),
            AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client,
        ):
            response = await client.get(
                "/broken?query=private-search-text",
                headers={"Origin": "http://localhost:8081"},
            )
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "Unable to complete request.",
    }
    application_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("lumiere")
    )
    assert "RuntimeError" in application_logs
    assert "status=500" in application_logs
    assert "private-search-text" not in application_logs
    assert "private upstream payload" not in application_logs


def test_process_environment_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMIERE_CORS_ORIGINS", '["http://localhost:9000"]')
    monkeypatch.setenv("LUMIERE_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("LUMIERE_TELEMETRY_ENABLED", "false")
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:9000"]
    assert settings.log_level == "WARNING"
    assert settings.telemetry_enabled is False
