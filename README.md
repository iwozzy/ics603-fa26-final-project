# Lumière

Discover movies from actors, directors, and creative teams. The `/search` action
currently returns fixed sample results.

Run the app with Python 3.13+ and uv:

```bash
uv sync
uv run fastapi dev app/main.py
```

Movie-note extraction uses `LLM_API_TOKEN` and `LLM_API_GATEWAY` from the
environment, with `.env` loaded as a fallback without overriding existing values.
Keep credentials in `.env` only. The gateway must be a valid HTTP(S) URL. Without
valid configuration, the page and sample search remain available and extraction
returns 503.

Submit a note to `POST /extract-note` as JSON:

```json
{"note": "Interstellar; Prisoners"}
```

The response contains only extracted titles, for example
`{"titles": ["Interstellar", "Prisoners"]}`. Titles are cleaned and deduplicated
while retaining their first spelling and order; a note without named movies
returns an empty list. Notes must contain non-whitespace text and at most 20,000
characters before trimming. Invalid requests return 422.

Extraction uses `gpt-4.1-nano` through the configured gateway with one model request,
30-second request and transport deadlines, and no output repair or HTTP retries.
Model failures and invalid structured output return 502; timeouts return 504.
Responses use safe messages without provider error details. Extracted titles are
temporary: this action does not save notes, imports, or movie metadata. Model
availability does not establish extraction quality or gateway structured-output
compatibility; those require a separate manual check.

Run the offline checks (tests use Pydantic AI's `TestModel` and prohibit real model
requests; no gateway credentials are needed):

```bash
uv run ruff check
uv run mypy
uv run pytest
```
