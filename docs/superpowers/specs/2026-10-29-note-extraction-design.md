# Note extraction design

Draft for approval. This is a small increment connecting the existing page to the model.

## Intent and scope

Let someone paste a messy movie note and review a clean list of movie titles. Establish the first useful page-to-model flow using the existing FastAPI and Pydantic AI stack. This implements the first increment described in the proposal's **LLM role**, **Human review**, and **One failure case** sections.

The selected scope includes structured title extraction, duplicate removal, editable review, loading feedback, and retry without losing existing input or review work. Photos, retrieval, TMDB matching, metadata, saved imports, accounts, watch-list actions, timeline integration, and movie suggestions are outside this increment. The complete V1 goals in the proposal still apply to later work.

## Approaches

- **A: Note extraction — selected by the user.** Reuses the existing note field and sample input/output; provides a straightforward first model connection. It does not resolve movie identities or test image-reading quality.
- **B: Photo extraction.** Addresses the proposal's main feasibility uncertainty sooner, but adds image validation, vision-model compatibility, and harder-to-assess recognition errors.
- **C: Three movie suggestions.** Demonstrates discovery sooner, but needs temporary manual inputs for favorite people and seen movies, and produces recommendations without TMDB verification.

A was recommended because it has the smallest scope and concrete sample material for reviewing extraction quality.

## Proposed behavior

1. The user pastes a note and selects **Extract movie titles**. Whitespace-only input produces a helpful validation message without a model request.
2. The page shows loading feedback and prevents duplicate submissions while the request is pending. The server sends the note to a Pydantic AI agent that returns a structured list of titles. The prompt treats note content as data and asks for titles explicitly present in the note, without commentary or invented movie metadata.
3. Plain Python rules remove blank entries and duplicates. My proposed default is to trim and collapse whitespace, compare titles case-insensitively, and retain the first spelling and order. Different titles are not merged using fuzzy matching.
4. The page displays a title count and editable rows with keep/deselect checkboxes. It explains that titles have not been matched to movie records and that nothing is saved. A successful request replaces the previous review list; a successful empty result says no titles were found.
5. Failed extraction shows a retry message. The current note, previous results, edits, and selections remain intact. A page reload clears this unsaved state.

## Boundaries and constraints

My proposed implementation uses a separate note-extraction endpoint and title-only contract, so this flow does not require fabricated release years or other fields from the existing `Movie` model. Routes and rendering stay in `app/main.py` and `app/page.html`; the agent and its output contract stay in `app/agent.py`; normalization stays in plain Python rules. Follow AGENTS.md's responsibility-splitting rule and update its Layout section if the rules module is split.

Read `LLM_API_TOKEN` and `LLM_API_GATEWAY` from the environment. Missing configuration must not prevent the page from loading; extraction should return a helpful error. Never expose gateway credentials or raw provider errors to the browser. Planning will settle the gateway-supported text model, request bounds, timeout, and exact HTTP contract before implementation.

## Verification

Use `TestModel` with `override_allow_model_requests(False)` for agent and endpoint tests. Cover successful structured extraction, duplicate cleanup, empty input without a model call, no titles found, and model failure. Verify page loading, editable review, loading feedback, and preservation of input and edits on retry. Keep the existing skeleton and person-confirmation behavior covered.

The supplied sample note and expected output provide a reference for a later manual extraction-quality check; deterministic tests must never call a real model. Run Ruff, mypy, and pytest after changes, without weakening checks.
