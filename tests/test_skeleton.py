from fastapi.testclient import TestClient
from pydantic_ai.models import override_allow_model_requests

from app.main import app


def test_page_loads_with_form() -> None:
    with override_allow_model_requests(False), TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "<form" in response.text


def test_search_accepts_request_and_returns_declared_fields() -> None:
    with override_allow_model_requests(False), TestClient(app) as client:
        response = client.post(
            "/search",
            json={"category": "cast_crew", "query": "Matthew McConaughey"},
        )

    assert response.status_code == 200
    assert set(response.json()) == {"message", "people", "movies"}
