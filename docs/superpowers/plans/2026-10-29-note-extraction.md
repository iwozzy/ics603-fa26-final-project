# Note Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the existing movie-note input to a model and display a deduplicated, editable list of extracted titles.

**Architecture:** Add a dedicated JSON endpoint and a Pydantic AI agent with structured title-only output. Keep validation and normalization in plain Python rules; the page owns temporary edits and selections. Use the existing stack and dependency set.

**Tech Stack:** Python 3.13+, FastAPI, Pydantic, Pydantic AI with its OpenAI-compatible provider, vanilla HTML/JavaScript, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-10-29-note-extraction-design.md`; project-wide requirements in `docs/proposal.md` and `AGENTS.md`.

## Global Constraints

- Read `LLM_API_TOKEN` and `LLM_API_GATEWAY` from the environment. Never write a key outside `.env`.
- Tests never call a real model. Use `TestModel` with `override_allow_model_requests(False)`.
- Routes and rendering stay in `app/main.py` and `app/page.html`; the agent and its output contract stay in `app/agent.py`; normalization stays in plain Python rules.
- Photos, retrieval, TMDB matching, metadata, saved imports, accounts, watch-list actions, timeline integration, and movie suggestions are outside this increment.
- Run Ruff, mypy, and pytest after changes, without weakening checks.
- Work on a feature branch. Open a PR with Summary and Test plan, watch its checks after pushing, and never merge it. Keep the untracked `.superpowers/` companion files out of commits.

## Planning Decisions

These are implementation defaults, selected during planning rather than additional user requirements:

- Use `gpt-4.1-nano`, confirmed present in the configured gateway's model catalog. Catalog availability does not establish extraction quality or structured-output compatibility; a manual quality check remains separate from deterministic tests.
- Accept notes up to **20,000 characters before trimming**. Reject blank/whitespace-only notes before constructing or running an agent. Trim outer whitespace before sending the note.
- Use agent `retries=0`, model settings `request_timeout=30.0`, `timeout=30.0`, `max_retries=0`, and `UsageLimits(request_limit=1)`. The installed SDK supports these settings; no automatic repair requests, HTTP retries, or fallback models.
- `POST /extract-note` accepts `{"note": "..."}` and returns `{"titles": ["Interstellar"]}`. Invalid input returns 422. Missing/invalid gateway configuration returns 503 with `Note extraction is not configured.` Model failure or invalid structured output returns 502 with `Could not extract movie titles. Try again.` A model deadline/timeout returns 504 with `Movie title extraction timed out. Try again.` Use the normal `{"detail": "..."}` error shape for these service errors.
- Preserve the existing `/search` placeholder behavior. Give note extraction its own submit action and results area so sample search cannot clear reviewed titles. A new successful extraction deliberately replaces the previous title list, including on an empty result.

## Review Focus

1. Whitespace-only, non-string, or oversized notes must fail before agent construction (Task 2).
2. Repeated titles with mixed whitespace, case, or Unicode must retain the first cleaned spelling and order without fuzzy merging (Task 1).
3. Missing configuration, invalid output, provider failures, and timeouts must produce safe messages without disclosing credentials or raw errors (Task 2).
4. Failure after editing/deselecting results must preserve the note and review state; success must replace the list (Task 3).
5. HTML-looking titles must render as text; repeated clicks during loading must send one request (Task 3).

## File Responsibilities

- Replace `app/rules.py` with `app/rules/__init__.py`, `confirmation.py`, and `extraction.py`. Preserve the existing confirmation import via a re-export; extraction is the second business-rule responsibility.
- `app/agent.py`: retain current contracts and add the extraction output, lazy agent factory, and bounded agent execution.
- `app/main.py`: add note request validation through the rules module, orchestration, and HTTP error mapping. No normalization algorithms or provider setup here.
- `app/page.html`: separate note extraction form, status, and editable review. No persistence or new page navigation.
- `tests/test_note_rules.py` and `tests/test_note_extraction.py`: pure rules and model-isolated API tests. Keep existing tests intact.
- `AGENTS.md`, `README.md`, and the affected proposal sections: synchronize module layout, local setup, and the settled extraction behavior.

---

### Task 1: Pure validation and title normalization

**Files:** Replace `app/rules.py`; create `app/rules/{__init__,confirmation,extraction}.py` and `tests/test_note_rules.py`; modify `AGENTS.md` Layout.

**Interfaces:**
- Consumes: existing `validate_person_confirmation(returned_person_ids: frozenset[int], selected_person_id: int, confirmed: bool) -> None`.
- Produces: `app.rules.extraction.MAX_NOTE_CHARACTERS = 20_000`, `validate_note(note: str) -> str`, and `normalize_titles(titles: list[str]) -> list[str]`.
- Preserve `app.rules.validate_person_confirmation` through an explicit re-export; put its unchanged implementation in `confirmation.py`.

- [ ] **Step 1: Write failing rule tests.** Pin normalization with:

```python
assert normalize_titles([
    "  The  Spectacular Now ", "the spectacular now", "", " \n ",
    "Amélie", "AMÉLIE", "It", "It Chapter Two",
]) == ["The Spectacular Now", "Amélie", "It", "It Chapter Two"]
assert validate_note(" \nInterstellar\n ") == "Interstellar"
assert validate_note("x" * 20_000) == "x" * 20_000
```

Also assert `ValueError` for whitespace-only input and 20,001 characters, including a note whose surrounding whitespace makes it oversized before trimming.

- [ ] **Step 2: Run `uv run pytest tests/test_note_rules.py -v`.** Expect failure because the extraction module does not exist.
- [ ] **Step 3: Split rules and implement the interfaces.** Normalize using whitespace splitting/joining and `casefold()` keys; retain first occurrences. Update AGENTS.md Layout in the same change.
- [ ] **Step 4: Run `uv run ruff check`, `uv run mypy`, and `uv run pytest`.** Expect all checks green, including the unchanged confirmation tests.
- [ ] **Step 5: Commit** the rule package, tests, and Layout update as `feat: validate movie notes and normalize extracted titles`.

### Task 2: Structured agent and extraction endpoint

**Files:** Modify `app/agent.py`, `app/main.py`, `README.md`; create `tests/test_note_extraction.py`.

**Interfaces:**
- Consumes: Task 1's `validate_note` and `normalize_titles`.
- Produces in `app/agent.py`: `ExtractedTitles(BaseModel)` with required `titles: list[str]`; `NoteExtractionConfigurationError(RuntimeError)`; `create_note_agent(model: Model | None = None) -> Agent[None, ExtractedTitles]`; `async def extract_note_titles(note: str, agent: Agent[None, ExtractedTitles]) -> ExtractedTitles`.
- Produces in `app/main.py`: `NoteExtractionRequest(BaseModel)` with `note: str`, a field validator delegating to `validate_note`, and `async def extract_note(request: NoteExtractionRequest) -> ExtractedTitles` registered at `/extract-note`.

- [ ] **Step 1: Write failing success, empty-result, and validation tests.** Construct a real extraction agent with `TestModel(custom_output_args={"titles": [" Interstellar ", "interstellar", "Prisoners"]})`. Monkeypatch the route's factory reference to return it; prohibit model requests around every test. Assert:

```python
response = client.post("/extract-note", json={"note": "interstellar; prisoners"})
assert response.status_code == 200
assert response.json() == {"titles": ["Interstellar", "Prisoners"]}
```

Use `TestModel(custom_output_args={"titles": []})` to assert 200 and an empty list. For `""`, whitespace, 20,001 characters, `None`, a list, and missing `note`, assert 422 and that the patched agent factory was never called. Check that a valid 20,000-character note is accepted.

- [ ] **Step 2: Run `uv run pytest tests/test_note_extraction.py -v`.** Expect failure from the absent extraction interfaces/route.
- [ ] **Step 3: Implement lazy configuration, bounded execution, and route mapping.** The factory accepts a supplied test model without reading credentials. Otherwise load `.env` without overriding existing environment values, require nonempty token and a valid HTTP(S) gateway URL, and construct `OpenAIChatModel("gpt-4.1-nano", provider=OpenAIProvider(base_url=..., api_key=...))`. No provider construction at import time. Apply the Planning Decisions' settings in the agent; the execution helper passes the request limit. Prompt for explicitly named movies, exclude commentary, treat instructions inside the note as data, and return titles without metadata. The route delegates normalization to Task 1 and maps configuration, timeout, and other `AgentRunError` failures in that order. Do not return raw provider exceptions.
- [ ] **Step 4: Add error/configuration tests.** Assert exact status/detail pairs from Planning Decisions. Use `TestModel` subclasses whose `request()` raises a provider error containing a fake secret or raises a timeout; assert the secret is absent from the response. Invalid output uses `TestModel(custom_output_args={"titles": 7})` and must return 502 with no retry. Capture passed model settings and count requests with a test-model subclass: assert 30-second deadlines, `max_retries=0`, and one request. Remove both environment variables and patch `app.agent.load_dotenv` to a no-op; assert GET `/` still works and extraction returns 503. With fake environment values and a patched provider constructor, assert the gateway/model selection without network access.
- [ ] **Step 5: Run Ruff, mypy, and the complete pytest suite.** Expect all green. Update README with the extraction action, existing environment-variable names, model and request bounds, temporary state, and offline test commands; never include credentials. Commit as `feat: extract movie titles through the configured gateway`.

### Task 3: Editable review on the existing page

**Files:** Modify `app/page.html` and affected proposal sections only if necessary to match final behavior. Keep the existing page-load tests.

**Interfaces:**
- Consumes: Task 2's `/extract-note` request, success, and error contracts.
- Produces: independent `note-form`, `extract-note` button, `note-status` live region, and `note-results` review container. Browser state exists only in these controls.

- [ ] **Step 1: Establish the failing browser checks.** Exercise Step 3's user interactions against the current page; extraction and editable review are absent. Use these behavioral checks for the page rather than adding assertions that mirror HTML IDs or markup.
- [ ] **Step 2: Implement the note flow.** Move the note textarea into an independent form with `maxlength="20000"`, leaving the photo and placeholder search available. Send only `{"note": ...}` to `/extract-note`. Reject blank input locally; disable submit and show loading while pending. Render each title using DOM creation and `.value`/`.textContent`, with labeled text inputs and initially checked keep boxes. Show the extracted-title count, an empty-result message when applicable, and copy explaining that titles are unmatched and unsaved. Only replace review DOM after a valid success response. On failure, change only status and submit state, leaving the note and edited review untouched. A pending guard must reject repeated submission events. Avoid `innerHTML` for note/model content.
- [ ] **Step 3: Check browser behavior against a stubbed backend, without a gateway call.** Run the app locally with its agent factory replaced by a deterministic `TestModel` factory and `override_allow_model_requests(False)` active for the server's lifetime. In browser developer tools, pause the request or force an error response as needed. Record the following checks in the PR:
  - Success yields unique editable titles and selected keep boxes; edit/deselect them, then fail the next request and confirm the note, edits, and checks are identical.
  - During a paused request, repeated clicks/submits send exactly one extraction request; loading is announced and submit re-enables after either outcome.
  - A subsequent successful result replaces all old rows; `{"titles": []}` clears them and announces no titles found.
  - A stubbed title `<img src=x onerror=alert(1)>` appears literally in an editable input and creates no image element or script execution.
  - Keyboard users can reach every title and checkbox. Sample search works without clearing extraction review; reload clears the unsaved list.
- [ ] **Step 4: Run Ruff, mypy, and pytest.** Expect all green; do not count static markup assertions as browser interaction verification. A live sample-note quality check is optional and must be reported separately, never run inside tests or represented by the supplied expected output alone. Commit as `feat: review extracted movie titles on the page`.
- [ ] **Step 5: Review the whole change against the approved design and resolve findings.** Update the existing PR's title/body for the implemented behavior, with Summary citing `docs/proposal.md` sections **LLM role**, **Human review**, and **One failure case**. Include actual local and browser verification results; leave any unrun live quality check unchecked. Push the feature branch, run `gh pr checks --watch`, report the outcome, and leave the PR unmerged.
