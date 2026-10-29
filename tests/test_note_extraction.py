from collections.abc import Iterator
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.exceptions import (
    ModelHTTPError,
    ModelRequestTimeout,
    ModelTimeoutError,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, UserPromptPart
from pydantic_ai.models import ModelRequestParameters, override_allow_model_requests
from pydantic_ai.models.test import TestModel as ExtractionTestModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from app import agent as agent_module
from app import main as main_module


@pytest.fixture(autouse=True)
def prohibit_model_requests(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LLM_API_TOKEN", "fake-test-token")
    monkeypatch.setenv("LLM_API_GATEWAY", "https://gateway.example.test/v1")
    monkeypatch.setattr(agent_module, "load_dotenv", Mock(), raising=False)
    with override_allow_model_requests(False):
        yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(main_module.app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    ("titles", "expected"),
    [
        ([" Interstellar ", "interstellar", "Prisoners"], ["Interstellar", "Prisoners"]),
        ([], []),
    ],
)
def test_extracts_normalized_titles(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    titles: list[str],
    expected: list[str],
) -> None:
    agent = agent_module.create_note_agent(
        ExtractionTestModel(custom_output_args={"titles": titles})
    )
    monkeypatch.setattr(main_module, "create_note_agent", lambda: agent)

    response = client.post("/extract-note", json={"note": "interstellar; prisoners"})

    assert response.status_code == 200
    assert response.json() == {"titles": expected}


@pytest.mark.parametrize(
    "payload",
    [
        {"note": ""},
        {"note": " \n\t"},
        {"note": "x" * 20_001},
        {"note": None},
        {"note": []},
        {},
    ],
)
def test_invalid_notes_fail_before_agent_construction(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, payload: dict[str, object]
) -> None:
    factory = Mock(side_effect=AssertionError("Agent must not be constructed"))
    monkeypatch.setattr(main_module, "create_note_agent", factory, raising=False)

    response = client.post("/extract-note", json=payload)

    assert response.status_code == 422
    factory.assert_not_called()


def test_accepts_note_at_character_limit(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    agent = agent_module.create_note_agent(
        ExtractionTestModel(custom_output_args={"titles": []})
    )
    monkeypatch.setattr(main_module, "create_note_agent", lambda: agent)

    response = client.post("/extract-note", json={"note": "x" * 20_000})

    assert response.status_code == 200
    assert response.json() == {"titles": []}


class RecordingTestModel(ExtractionTestModel):
    def __init__(self, titles: object, failure: Exception | None = None) -> None:
        super().__init__(custom_output_args={"titles": titles})
        self.failure = failure
        self.request_count = 0
        self.received_settings: ModelSettings | None = None
        self.received_messages: list[ModelMessage] = []

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        self.request_count += 1
        self.received_settings = model_settings
        self.received_messages = messages
        if self.failure is not None:
            raise self.failure
        return await super().request(messages, model_settings, model_request_parameters)


@pytest.mark.parametrize(
    ("failure", "status", "detail"),
    [
        (
            ModelHTTPError(500, "test", body="fake-secret-in-provider-error"),
            502,
            "Could not extract movie titles. Try again.",
        ),
        (
            ModelTimeoutError("test", "fake-secret-in-provider-error"),
            504,
            "Movie title extraction timed out. Try again.",
        ),
        (
            ModelRequestTimeout("test", 30.0),
            504,
            "Movie title extraction timed out. Try again.",
        ),
    ],
)
def test_model_errors_have_safe_responses_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    failure: Exception,
    status: int,
    detail: str,
) -> None:
    model = RecordingTestModel([], failure)
    agent = agent_module.create_note_agent(model)
    monkeypatch.setattr(main_module, "create_note_agent", lambda: agent)

    response = client.post("/extract-note", json={"note": "Interstellar"})

    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert "fake-secret-in-provider-error" not in response.text
    assert model.request_count == 1


def test_invalid_structured_output_fails_without_retry(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    model = RecordingTestModel(7)
    agent = agent_module.create_note_agent(model)
    monkeypatch.setattr(main_module, "create_note_agent", lambda: agent)

    response = client.post("/extract-note", json={"note": "Interstellar"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Could not extract movie titles. Try again."}
    assert model.request_count == 1


def test_request_has_deadlines_no_http_retries_and_trimmed_note(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    model = RecordingTestModel(["Interstellar"])
    agent = agent_module.create_note_agent(model)
    run = AsyncMock(wraps=agent.run)
    monkeypatch.setattr(agent, "run", run)
    monkeypatch.setattr(main_module, "create_note_agent", lambda: agent)

    response = client.post("/extract-note", json={"note": "  Interstellar \n"})

    assert response.status_code == 200
    assert model.request_count == 1
    assert model.received_settings is not None
    assert model.received_settings["request_timeout"] == 30.0
    assert model.received_settings["timeout"] == 30.0
    assert model.received_settings["max_retries"] == 0
    assert run.call_args.kwargs["usage_limits"].request_limit == 1
    prompts = [
        part.content
        for message in model.received_messages
        for part in message.parts
        if isinstance(part, UserPromptPart)
    ]
    assert prompts == ["Interstellar"]


@pytest.mark.parametrize(
    ("token", "gateway"),
    [
        (None, None),
        ("", "https://gateway.example.test/v1"),
        ("  ", "https://gateway.example.test/v1"),
        ("fake-test-token", None),
        ("fake-test-token", ""),
        ("fake-test-token", "not-a-url"),
        ("fake-test-token", "ftp://gateway.example.test/v1"),
        ("fake-test-token", "https://"),
    ],
)
def test_invalid_configuration_keeps_page_available(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    token: str | None,
    gateway: str | None,
) -> None:
    for name, value in [("LLM_API_TOKEN", token), ("LLM_API_GATEWAY", gateway)]:
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    provider = Mock(side_effect=AssertionError("Invalid config must not build provider"))
    monkeypatch.setattr(agent_module, "OpenAIProvider", provider, raising=False)

    page = client.get("/")
    response = client.post("/extract-note", json={"note": "Interstellar"})

    assert page.status_code == 200
    assert response.status_code == 503
    assert response.json() == {"detail": "Note extraction is not configured."}
    provider.assert_not_called()


def test_supplied_model_does_not_read_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_API_TOKEN", raising=False)
    monkeypatch.delenv("LLM_API_GATEWAY", raising=False)
    dotenv = Mock(side_effect=AssertionError("Supplied model must not load credentials"))
    monkeypatch.setattr(agent_module, "load_dotenv", dotenv)
    model = ExtractionTestModel(custom_output_args={"titles": []})

    agent = agent_module.create_note_agent(model)

    assert agent.model is model
    dotenv.assert_not_called()


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_configured_factory_uses_gateway_and_selected_model(
    monkeypatch: pytest.MonkeyPatch, scheme: str
) -> None:
    gateway = f"{scheme}://gateway.example.test/v1"
    monkeypatch.setenv("LLM_API_GATEWAY", gateway)
    provider = Mock(wraps=OpenAIProvider)
    dotenv = Mock()
    monkeypatch.setattr(agent_module, "OpenAIProvider", provider)
    monkeypatch.setattr(agent_module, "load_dotenv", dotenv)

    agent = agent_module.create_note_agent()

    assert agent.model is not None
    assert not isinstance(agent.model, str)
    assert agent.model.model_name == "gpt-4.1-nano"
    provider.assert_called_once_with(base_url=gateway, api_key="fake-test-token")
    dotenv.assert_called_once_with(override=False)
