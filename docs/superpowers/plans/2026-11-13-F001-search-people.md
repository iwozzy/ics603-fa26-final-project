# F001 Search People Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver working people search from the supplied wireframes, returning the first seven valid people from TMDB's default first page in provider order.

**Architecture:** An Expo client calls a same-origin FastAPI API. Backend and client use cases depend on owned ports; TMDB, HTTP, session storage, and usage accounting are adapters. Only guest/session and usage state is persisted; search data and catalog identities remain transient.

**Tech Stack:** Python 3.13+/uv, FastAPI/Pydantic, HTTPX, async SQLAlchemy/psycopg/Alembic, Postgres/Neon, Logfire; TypeScript, Expo/React Native/web/Router, npm, Jest/jest-expo, React Native Testing Library, Zod, Hey API code generation, Playwright, Docker/Caddy.

**Spec:** [Approved F001 design](../specs/2026-11-13-F001-search-people-design.md), read with the [amended application architecture](../specs/2026-11-09-application-architecture-design.md).

## Global Constraints

- Python 3.13+; preserve existing uv, Ruff, Pyrefly, and coverage configuration. Keep dependency resolution's existing `exclude-newer = "3 days"` policy.
- Submit on Enter/Return or clicking/tapping the search icon. Typing does not initiate search.
- Use only the provider's first page; return up to the first seven valid people in provider order. No sorting, deduplication, or additional-page requests.
- A valid person has a usable provider ID and a nonblank name. Optional display omissions never exclude a person.
- Send only TMDB's required `query` parameter; omit optional parameters. Authentication uses the authorization header.
- All search API failures return HTTP `500`; a successful empty list returns `200`. Both display a blank results area without an added message.
- Every successful search response has exactly `Cache-Control: private, max-age=300`. Omit `Vary: Cookie`; errors use `Cache-Control: no-store`.
- Preserve the wireframe's initial/loading example-search guidance; add no other hint messages.
- Display up to three provider-ordered known-for titles, including TV. Use `https://image.tmdb.org/t/p/w180_and_h180_face/` plus `profile_path`, with one joining slash.
- Omit IDs from the response. Store no people, source mappings, provider payloads, queries, or search results. Selection capture and identity mappings belong to the following feature.
- Retain ports/adapters in backend and client; keep framework/provider/storage dependencies outside cores. No future-feature scaffolding, workers, AI, registration, or native release work.
- Enforce durable global/session/IP admission and provider budgets; count dispatched failures conservatively. No hidden provider retry layers.
- Follow AGENTS.md: do not inspect or write operator secrets, print them, or commit them. Runtime access is operator-supplied. Test values are synthetic and isolated; never load existing credential files.

## Review Focus

1. Non-BMP names, accents, apostrophes, and boundary-length input: encode once, preserve text, and count Unicode code points consistently (Tasks 1, 5, 6).
2. Heterogeneous provider records and broken optional values: skip only unusable IDs/names and preserve usable people and movie/TV order (Task 2).
3. Clearing/editing during overlapping requests, including old failures: only the latest submission can change current results or loading (Task 6).
4. Concurrent admission, crashes, and UTC rollover: durable limits cannot overspend or reset cumulative usage after restart (Task 3).
5. Browser caching obscured by mocks, cookie changes, or forced revalidation: prove real HTTP-cache reuse without Playwright routing and preserve the exact production header (Tasks 5, 8).

## File map and implementation choices

The repository has no product code. Create focused feature and adapter modules, not empty packages for future capabilities. Add normal Python `__init__.py` files to created package directories. Paths below are relative to the repository root.

| Area | Files and responsibility |
| --- | --- |
| Backend search core | `src/movie_discovery/people/models.py`, `ports.py`, `use_cases.py`: display DTOs, catalog/clock contracts, query validation and ordered selection. |
| Access core | `src/movie_discovery/access/models.py`, `ports.py`: guest context, session, admission, and reservation contracts. Search imports the access-owned admission port. |
| Provider | `src/movie_discovery/people/adapters/tmdb.py`: strict required-field validation, tolerant optional translation, bounded HTTPX call. |
| Database | `src/movie_discovery/access/postgres.py`, `storage/tables.py`, `storage/engine.py`, `alembic.ini`, `migrations/env.py`, `migrations/versions/0001_guest_usage.py`: sessions and durable admission only. |
| HTTP | `src/movie_discovery/http/app.py`, `schemas.py`, `context.py`, `search_routes.py`, `session_routes.py`, `errors.py`: request/response and cookie transport. |
| Composition | `src/movie_discovery/bootstrap/settings.py`, `dependencies.py`, `asgi.py`, `observability.py`: runtime wiring, configuration, lifecycle, safe telemetry. |
| Client core | `client/src/people/models.ts`, `ports.ts`, `controller.ts`: display model, search port, submission state machine without React/fetch/Expo. |
| Client adapters | `client/src/people/adapters/http.ts`, `guestSession.ts`, `generated/`: transport, bootstrap, generated types/validators. |
| Client view | `client/src/people/views/SearchPeopleScreen.tsx`, `PersonRow.tsx`, `useSearchPeople.ts`, `client/app/_layout.tsx`, `index.tsx`: platform UI and React lifecycle glue. |
| Contract/tooling | `contracts/openapi.json`, `scripts/export_openapi.py`, `client/openapi-ts.config.ts`, `scripts/check_boundaries.py`: reproducible schema and import boundaries. |
| Delivery | `Dockerfile.api`, `Dockerfile.web`, `Caddyfile`, `compose.yaml`, `compose.test.yaml`, `.dockerignore`, `README.md`, `.github/workflows/ci.yml`: local/test and deployable runtime without hosted publishing. |
| Verification | `tests/unit/`, `tests/integration/`, `tests/http/`, `tests/support/`, colocated client `*.test.ts(x)`, `client/e2e/`, `client/playwright.config.ts`. |

Use root `pyproject.toml` with a Hatchling `src/` package and pytest's test path configured; add `uv.lock` through normal dependency resolution at execution. Add FastAPI, Pydantic Settings (no dotenv file loading), HTTPX with HTTP/2 support, SQLAlchemy, psycopg, Alembic, Logfire; add pytest-asyncio and ASGI lifespan test support to dev dependencies. Keep existing tooling. Resolve compatible releases when executing and commit locks; do not guess future package versions here.

For the client, use npm and Expo's default SDK 58 Router template, then remove the generated demo routes/assets not needed for search. Official Expo documentation currently identifies `default@sdk-58`; recheck compatibility at execution, record the actual SDK/Node requirements, and use Expo's installer for its peer dependencies. Use StyleSheet, React local lifecycle glue, and an injected plain controller; no app query-cache library. Generate TypeScript definitions and Zod v4 validators with `@hey-api/openapi-ts`, without a generated request SDK. Keep the hand-written HTTP adapter in control of browser cache behavior.

Tasks are sequential except for independent reads/checks. Each task ends with its targeted checks and an explicit-file commit; do not stage unrelated workspace changes. Test-first cycles apply to behavior. Configuration belongs to its owning deliverable, without artificial tests of static boilerplate.

### Task 1: Backend use case and owned contracts

**Files:** Modify `pyproject.toml`; create `uv.lock`, search/access core files from the file map, `tests/support/fakes.py`, `tests/unit/test_search_people.py`.

**Interfaces:**
- `PersonSummary(name: str, department: str | None, profile_image_url: str | None, known_for: tuple[str, ...])` and `SearchPeopleResult(query: str, people: tuple[PersonSummary, ...])`: frozen dataclasses, no IDs.
- `GuestContext(profile_id: UUID, session_id: UUID, ip_key: str)`; `Reservation(id: UUID)`; `AttemptOutcome` enum `SUCCESS`, `FAILED`, `CANCELLED`.
- `PeopleCatalog.search_first_page(query: str) -> tuple[PersonSummary, ...]` (async): adapter returns all valid first-page candidates, without sorting.
- `UsageAdmission.admit(context: GuestContext, now: datetime) -> Reservation`, `mark_dispatched(reservation: Reservation) -> None`, `finish(reservation: Reservation, outcome: AttemptOutcome) -> None`, `release_undispatched(reservation: Reservation) -> None` (async).
- `Clock.now() -> datetime`; `SearchPeople(catalog: PeopleCatalog, admission: UsageAdmission, clock: Clock).execute(raw_query: str, context: GuestContext) -> SearchPeopleResult` (async).
- `SearchFailed(category: str)` is the owned failure; internal categories are telemetry-only. No HTTP/framework types in these contracts.

- [ ] Add the build/test dependencies and package configuration needed to run the behavioral tests, preserving existing settings. Configure pytest-asyncio with `asyncio_mode = "auto"` for the async tests below.
- [ ] Write failing async tests. Define `FakeCatalog`, `FakeAdmission`, `FixedClock`, and `person(name)` in `tests/support/fakes.py`; they record calls and permit injected failures. Core assertions:

```python
async def test_preserves_provider_order_and_limits_to_seven():
    catalog = FakeCatalog(tuple(person(str(i)) for i in range(10)))
    admission = FakeAdmission()
    result = await SearchPeople(catalog, admission, FixedClock()).execute(" Tom ", CONTEXT)
    assert result.query == "Tom"
    assert [p.name for p in result.people] == [str(i) for i in range(7)]
    assert catalog.queries == ["Tom"]
    assert admission.dispatch_count == 1
    assert admission.outcomes == [AttemptOutcome.SUCCESS]
```

Also write `test_empty_and_short_pages_do_not_request_more` (0 and 3 entries unchanged), `test_query_codepoint_boundaries` (1 and 200 accepted, 201/blank rejected, accents/non-BMP preserved), `test_failed_admission_never_dispatches`, and `test_provider_failure_and_cancellation_account_for_dispatch` (no retry; completion is conservative).
- [ ] Run `uv run pytest tests/unit/test_search_people.py -q`; confirm behavioral failures before implementation, not unresolved dependencies.
- [ ] Implement the contracts/use case. Validate before external admission; mark dispatch durably before invoking the catalog; select `candidates[:7]`; never retain results. Release proven-undispatched reservations only; uncertain/dispatched attempts remain charged. Ensure cancellation cleanup cannot erase possibly spent allowance.
- [ ] Re-run the command; expect all tests passing. Run `uv run ruff check src tests` and `uv run pyrefly check`.
- [ ] Commit the task's files: `feat: add people search use case and owned ports`.

### Task 2: TMDB adapter and fixture translation

**Files:** Create `src/movie_discovery/people/adapters/tmdb.py`, `tests/unit/test_tmdb_people.py`; reuse `docs/samples/api/tmdb/v3/search/person.json` unchanged.

**Interfaces:** Consume Task 1's `PeopleCatalog`, `PersonSummary`, and `SearchFailed`. Produce `TMDBPeopleCatalog(client: httpx.AsyncClient, max_bytes: int = 1048576)` implementing `search_first_page(query)`; composition supplies the base URL and authorization header.

- [ ] Write failing tests with `httpx.MockTransport`, loading the repository fixture. In `test_fixture_order_titles_and_images`, assert:

```python
assert request.url.path == "/3/search/person"
assert dict(request.url.params) == {"query": "Tom"}
assert [p.name for p in people[:7]] == [
    "Tom Skerritt", "Tom Holland", "Tom Hanks", "Tom Cruise",
    "Tom Hopper", "Tom Hardy", "Tom Welling",
]
assert people[4].known_for == ("The Umbrella Academy", "Resident Evil: Welcome to Raccoon City", "I Feel Pretty")
assert people[6].known_for == ("Smallville", "Lucifer", "The Fog")
assert people[0].profile_image_url == "https://image.tmdb.org/t/p/w180_and_h180_face/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg"
```

Add `test_required_fields_are_strict_optional_fields_are_tolerant`: IDs `True`, `"4139"`, zero, negative, or missing and blank/nonstring names are skipped; null/bad photo, department, or known-for values retain the person with fallbacks; mixed movie/TV entries preserve order up to three nonblank titles. Add `test_duplicate_valid_records_preserve_sequence`, `test_invalid_envelope_fails_but_invalid_records_do_not`, and `test_one_attempt_on_timeout_throttle_bad_json_or_oversize`; assert no detail/configuration/page-two calls and no retry.
- [ ] Run `uv run pytest tests/unit/test_tmdb_people.py -q`; expect failures on missing behavior.
- [ ] Implement envelope/per-record Pydantic validation and translation. Stream with a byte cap before decoding; tolerate malformed optional values. Strictly validate only required ID/name, then discard source IDs. Join the fixed image base with the relative path after stripping leading slashes; unusable/absolute URL values become `None`. Read movie `title`/TV `name`, trimming/omitting unusable text without filtering people.
- [ ] Run `uv run pytest tests/unit/test_search_people.py tests/unit/test_tmdb_people.py -q`; expect pass. Confirm transport retries are zero and the adapter does not retain its last response.
- [ ] Commit: `feat: add bounded TMDB people search adapter`.

### Task 3: Durable guest sessions and admission

**Files:** Create access/storage adapter files, `alembic.ini`, migration files, `compose.test.yaml`, `tests/integration/conftest.py`, `test_access.py`, `test_admission.py`.

**Interfaces:** Consume Task 1 access contracts. Produce `PostgresUsageAdmission(session_factory, policy)` implementing `UsageAdmission`; `PostgresGuestSessions(session_factory).bootstrap(cookie: str | None, ip_key: str, now: datetime) -> GuestSession` and `.resolve(cookie: str | None, ip_key: str, now: datetime) -> GuestContext` (async). Declare `GuestSessions` in `access/ports.py` with those same bootstrap/resolve signatures; HTTP/composition depend on that protocol, not the concrete adapter. Define `GuestSession(context: GuestContext, cookie_value: str, is_new: bool)` and `UsagePolicy` in `access/models.py`. Invalid resolution raises `SearchFailed("session")`.

`UsagePolicy` names required positive integer caps: `global_requests_per_minute`, `session_requests_per_minute`, `ip_requests_per_minute`, `bootstrap_requests_per_ip_per_minute`, and `global/session/ip_provider_daily` plus `global/session/ip_provider_total`. Supply all explicitly through deployment configuration; refuse live provider admission without a complete policy. Tests use small explicit caps (daily global 2, session 2, IP 2; request caps high enough to isolate that test). No operating allowance is inferred from environment absence.

- [ ] Write failing real-Postgres tests. `compose.test.yaml` uses a disposable Postgres 18 service, test-only trust authentication, and loopback binding; no operator credential files. The test harness receives an isolated test URL via its launcher and guards against non-test database use. Assertions for `test_concurrent_admission_caps_and_restart`:

```python
outcomes = await asyncio.gather(*(try_admit() for _ in range(20)))
assert outcomes.count("admitted") == 2
assert await fresh_adapter.try_admit_same_context() == "rejected"
assert await read_global_daily_count() == 2
```

Define these helpers in the integration test module over the concrete adapter; no production inspection endpoints. Add `test_utc_rollover_keeps_cumulative_cap`, `test_undispatched_release_is_idempotent`, `test_dispatch_or_crash_reservation_remains_charged`, `test_session_bootstrap_reuses_valid_cookie_and_replaces_expired_cookie`, `test_bootstrap_ip_limit_and_cookie_digest_storage`, and `test_database_outage_prevents_admission`.
- [ ] Start only the isolated test database with `docker compose --env-file /dev/null -f compose.test.yaml up -d --wait`. Run `uv run pytest tests/integration -q`; expect behavioral failures before adapter implementation.
- [ ] Implement migrations for **only** guest profiles/sessions, usage counters, and reservations. Store session-token digests, expiry, internal profile/session UUIDs, and keyed IP identifiers; never store search content. Generate runtime session proofs internally; use a session-only cookie later, a 24-hour server expiry, and rotation on replacement. Bootstrap is idempotent for a valid cookie and IP-throttled.
- [ ] Implement counters keyed by scope, feature, and UTC window. Insert missing counters safely, lock affected rows in a consistent order, and check/update every scope in one transaction. Admission counts request usage and reserves one provider attempt; marking/finishing are idempotent. Release provider allowance only for a reservation proven undispatched, retaining request usage. A crash/unknown outcome never automatically refunds possibly spent capacity. Never hold a transaction during provider network I/O.
- [ ] Re-run integration and Task 1 tests; expect pass, including concurrency/restart assertions against Postgres rather than SQLite. Tear down the isolated database when finished.
- [ ] Commit: `feat: persist guest sessions and atomic search admission`.

### Task 4: HTTP endpoints, lifecycle, and OpenAPI

**Files:** Create HTTP/composition files from the map, `scripts/export_openapi.py`, `contracts/openapi.json`, `tests/http/conftest.py`, `test_search.py`, `test_session.py`, `test_openapi.py`.

**Interfaces:** `create_app(dependencies: Dependencies) -> FastAPI` must be importable without loading operator configuration or making network/database calls. `build_dependencies(settings: Settings) -> Dependencies` owns concrete adapters/lifecycle. `POST /api/v1/guest-session` bootstraps a guest with `200`/no-store and an empty body; `GET /api/v1/people/search` exposes the exact approved response. `PersonResponse` and `SearchPeopleResponse` are Pydantic boundary schemas, including max seven people/max three titles.

- [ ] Write failing API tests with fake ports and lifespan-managed ASGI transport. `test_search_success_and_blank_success_headers` asserts:

```python
assert response.status_code == 200
assert response.headers["cache-control"] == "private, max-age=300"
assert "cookie" not in response.headers.get("vary", "").lower()
assert "set-cookie" not in response.headers
assert set(response.json()) == {"query", "people"}
assert set(response.json()["people"][0]) == {"name", "department", "profile_image_url", "known_for"}
```

Also test `people: []`. Parameterize `test_every_search_failure_is_empty_500` over missing/blank/overlong query, absent/expired session, request limits, all budget scopes, upstream non-2xx/malformed envelope, timeout, database outage, response-validation error, and unexpected exception: `status_code == 500`, `content == b""`, `cache-control == "no-store"`, no dispatch when rejected before dispatch. `test_openapi_only_advertises_search_200_and_500` asserts exactly those response keys. `test_bootstrap_cookie_and_origin` asserts HttpOnly, same-site lax, Path=/, Secure in HTTPS mode, no persistent-cookie expiry, no-store, and rejection of an untrusted mutation Origin.
- [ ] Run `uv run pytest tests/http -q`; expect failures before implementation.
- [ ] Implement request parsing, owned error translation, and route-aware exception handlers that also cover dependency/validation/unhandled failures. Prevent FastAPI's automatic `422` entry in this operation's OpenAPI contract. Leave unrelated future routes free to choose their own policies. Request context uses the real peer IP unless an explicitly trusted proxy supplied a sanitized forwarding chain; normalize IPv4/IPv6 before keyed derivation. Add forged-forwarding-header and IPv6-equivalence tests in `test_session.py`.
- [ ] Wire one long-lived HTTPX client with HTTP/2 fallback, zero transport retries, connect timeout 2 seconds, overall provider deadline 5 seconds, max 1 MiB response, and a bounded connection pool (20 connections, 10 keepalive). Use one async database session per transaction, pool size 5 plus max overflow 5. App request deadline is 7 seconds. Lifespan closes both pools. Settings load named runtime variables without dotenv files; use Pydantic's `hide_input_in_errors=True` and sanitized startup errors that report field names, never supplied values. Readiness checks database connectivity without provider dispatch.
- [ ] Implement `scripts/export_openapi.py` using a schema-only app with inert dependencies; it writes deterministic sorted JSON without runtime configuration. Run `uv run python scripts/export_openapi.py`, then `uv run pytest tests/http tests/unit -q`; expect pass and an OpenAPI contract with only the agreed statuses and fields.
- [ ] Commit: `feat: expose people search and guest HTTP contracts`.

### Task 5: Expo foundation, generated contracts, and client HTTP adapters

**Files:** Create `client/package.json`, `package-lock.json`, `app.json`, `tsconfig.json`, `jest.config.js`, `openapi-ts.config.ts`, client models/ports/adapters/generated files from the map, `http.test.ts`, `guestSession.test.ts`. Update `.gitignore` for client builds, test artifacts, and dependencies.

**Interfaces:** `PersonSummary = { name: string; department: string | null; profileImageUrl: string | null; knownFor: readonly string[] }`; `SearchResult = { query: string; people: readonly PersonSummary[] }`; `PeopleSearchPort.search(query: string, signal: AbortSignal): Promise<SearchResult>` rejects on every failure. `GuestSessionPort.ensure(signal: AbortSignal): Promise<void>` and `invalidate(): void` hide cookie transport. `HttpPeopleSearch(fetchImpl, sessions)` implements the search port; `HttpGuestSession(fetchImpl)` implements session bootstrap. Generated names remain behind these adapters.

- [ ] Initialize the Expo SDK 58 Router client at execution using `npx create-expo-app@latest client --template default@sdk-58`; remove demo routes. Install compatible jest-expo/Jest/React Native Testing Library, Zod v4, Hey API generator, and Playwright. Configure `npm test -- --runInBand`, `npm run typecheck`, `npm run lint`, `npm run generate:api`, and `npm run export:web` (`expo export --platform web`). Lock compatible versions; setup alone is not a test cycle.
- [ ] Configure Hey API input `../contracts/openapi.json`, output `src/people/adapters/generated`, plugins `@hey-api/typescript` and `zod` with definitions enabled. Generate checked-in validators/types; wrap the generated search-response validator in the HTTP adapter rather than exposing it to the core.
- [ ] Write failing adapter tests. `test_encodes_query_once_and_uses_normal_browser_cache` captures calls and asserts:

```typescript
expect(searchUrl).toBe('/api/v1/people/search?query=' + encodeURIComponent("Timothée O'Neil & 李😀"));
expect(searchOptions.credentials).toBe('same-origin');
expect(searchOptions.cache).toBeUndefined();
expect(searchOptions.headers?.['Cache-Control']).toBeUndefined();
expect(result.people[0]).not.toHaveProperty('id');
```

`test_repeated_searches_use_transport_without_query_cache` observes two transport calls for two searches (actual HTTP caching belongs to the browser). `test_rejects_500_bad_json_invalid_schema_and_abort` asserts rejection, no automatic search retry, and session readiness invalidation after a non-cancellation failure. `test_bootstrap_is_coalesced_and_reused` asserts one bootstrap for concurrent/normal subsequent searches; after explicit invalidation the next manual attempt bootstraps once. Bootstrap failure never dispatches search.
- [ ] Run `npm --prefix client test -- --runInBand`; confirm behavioral failures before adapter bodies.
- [ ] Implement the owned models and adapters: same-origin relative URLs, default fetch cache behavior, cookie credentials, generated runtime validation, and DTO-to-client field translation. Combine caller cancellation with an 8-second client deadline in the adapter. Session bootstrap stores only an in-memory readiness promise, not an exposed cookie or cached search result; on failure, recover only on the next explicit submission, never replay search automatically.
- [ ] Run client tests, typecheck/lint, schema export, and generation again. `git diff --exit-code -- contracts/openapi.json client/src/people/adapters/generated` must show no drift after the generated files are committed in this task. Before that commit, compare a second generation with the first using temporary copies.
- [ ] Commit: `feat: add Expo search transport and generated validation`.

### Task 6: Submission controller and wireframe screen

**Files:** Create `client/src/people/controller.ts`, `controller.test.ts`, view files and `SearchPeopleScreen.test.tsx`, `PersonRow.test.tsx`; replace the scaffolded routes with `client/app/_layout.tsx` and `client/app/index.tsx` (move the template's route root if necessary rather than retaining two Router roots).

**Interfaces:** `SearchState = { draft: string; submitted: string | null; phase: 'initial' | 'loading' | 'results' | 'blank'; people: readonly PersonSummary[] }`. `SearchPeopleController(port: PeopleSearchPort)` exposes `getSnapshot(): SearchState`, `subscribe(listener: () => void): () => void`, `setDraft(value: string): void`, `submit(): Promise<void>`, `dispose(): void`. Framework glue in `useSearchPeople.ts` subscribes with React lifecycle APIs and disposes on unmount; core contains no React, DOM, Expo, or fetch imports.

- [ ] Write failing controller tests with manually resolved/rejected promises. `test_latest_submission_wins_even_after_old_failure` submits A, then B, resolves B, rejects A, and asserts:

```typescript
expect(controller.getSnapshot()).toMatchObject({ phase: 'results', submitted: 'B', people: peopleB });
```

`test_clear_invalidates_pending_work` resolves an old request after clearing and asserts `phase === 'initial'` and `people` empty. `test_duplicate_pending_query_is_ignored` asserts one port call. `test_failure_and_empty_success_are_blank` asserts `phase === 'blank'`, no people, no loading. `test_codepoint_length_and_no_typing_dispatch` accepts 200 non-BMP code points and rejects 201, preserving accents/apostrophes. Invalid submissions must invalidate earlier work so a delayed result cannot refill the blank state.
- [ ] Write view tests: Enter/Return and icon submit, typing does not; an active IME composition does not submit; input remains editable/focused; changed draft enables submission during loading; stale draft edits retain completed results. Assert the exact placeholder `Search for actors, directors, or creative team to follow`, heading `Cast & Crew`, initial/loading `Example searches:` and all three names/roles from the spec. After empty/failure completion, examples disappear and no message replaces them. Rows have no Follow/Movies controls, no IDs or clickable person action, up to three mixed titles, and image-error/missing-image silhouettes without broken separators.

```typescript
expect(screen.queryByText('Timothée Chalamet (Actor)')).not.toBeNull();
expect(screen.queryByText('Hayao Miyazaki (Director, Writer)')).not.toBeNull();
expect(screen.queryByText('Autumn Durald Arkapaw (Cinematographer)')).not.toBeNull();
// After resolving empty success or failure, all three queries return null.
```
- [ ] Run `npm --prefix client test -- --runInBand`; expect targeted behavioral failures.
- [ ] Implement the controller with a monotonically increasing submission generation and AbortController. Compare generation before **any** completion/finally mutation, including errors. Determine query length via code points (`Array.from(trimmed).length`), not UTF-16 length. Implement views using RN primitives and StyleSheet, matching supplied spacing/hierarchy, visible focus, and at least a 44×44 search target; use busy accessibility state without added empty/error announcements. Use only transient row keys derived from submission/position.
- [ ] Run client tests, typecheck, lint, and `npm --prefix client run export:web`; expect pass. Inspect initial/loading/results and a narrow viewport; fix clipping without redesigning the feature or adding new copy.
- [ ] Commit: `feat: implement people search screen and submission behavior`.

### Task 7: Runtime packaging, safe telemetry, and boundaries

**Files:** Create runtime/CI files from the map, `src/movie_discovery/observability.py`, `scripts/check_boundaries.py`, `tests/unit/test_observability.py`, `tests/unit/test_boundaries.py`; extend composition wiring.

**Interfaces:** `configure_observability(enabled: bool) -> None` is called only by composition. `scripts/check_boundaries.py` exits nonzero with file/import diagnostics when core imports adapters/frameworks. Production starts `movie_discovery.bootstrap.asgi:app`; health routes `/health/live` and `/health/ready` perform no TMDB calls.

- [ ] Write failing `test_telemetry_omits_query_payloads_and_credentials` using a local in-memory exporter and synthetic sentinels: captured spans/logs contain internal failure category, latency, counts, and correlation but none of query text, raw fixture content, cookie/authorization values, or database URL. `test_core_dependency_violations_are_detected` uses temporary Python/TS files to assert framework/provider/generated-adapter imports are rejected in core and allowed in adapters.
- [ ] Run `uv run pytest tests/unit/test_observability.py tests/unit/test_boundaries.py -q`; confirm failures.
- [ ] Configure Logfire with a route/template-only request span and sanitized exception reporting. Disable automatic HTTP/SQL body, query-string, full URL, cookie, authorization, and parameter capture; do not assume default scrubbing removes names. Disable Uvicorn query-bearing access logs and Caddy query-bearing access logging; use explicit safe correlation events. Telemetry defaults off without operator setup and never blocks search.
- [ ] Add multi-stage Docker builds for the Python API and exported Expo web/Caddy image. Caddy serves static web and proxies `/api/*` without rewriting cache headers or adding cookie variation; TLS/HTTP2 is negotiated at ingress with HTTP/1.1 fallback to API. `compose.yaml` has web/API only with operator-supplied Postgres configuration; `compose.test.yaml` provides isolated Postgres and test services. Use `.dockerignore` exclusions for VCS, dependencies, test artifacts, and credential files; never copy an existing `.env` or inspect its values.
- [ ] Add README commands for migrations, bootstrap/search, export/generation, local same-origin run, required configuration **names only**, and explicit admission-policy setup. Document fixed timeouts/byte/pool bounds, UTC counting, five-minute browser freshness, silent failures and server diagnosis, no search persistence, and no hosted deployment. Add CI for the locked installs and all bounded checks; CI has no live TMDB/Neon/Logfire dependency.
- [ ] Run observability/boundary tests, `uv run python scripts/check_boundaries.py`, and build both Docker images. Check `/health/ready` with the isolated database and prove readiness makes zero stub-provider calls.
- [ ] Commit: `build: package search app and enforce safe boundaries`.

### Task 8: Real browser flow, HTTP caching, and final verification

**Files:** Create `tests/support/tmdb_server.py`, `tests/support/run_e2e.py`, `Caddyfile.test`, `client/playwright.config.ts`, `client/e2e/search-people.spec.ts`, `cache.spec.ts`; update `compose.test.yaml`, client scripts, README, and CI.

**Interfaces:** The fixture server implements `/3/search/person` over real local HTTP, records request counts in test-process memory, and selects delay/empty/error fixtures by synthetic test query. `run_e2e.py --suite normal|cache-expiry` launches isolated database/API/stub/ingress, injects the stub base URL through test composition, and runs built-web Playwright checks. There is no public production test-control endpoint. Test-only `Caddyfile.test` retains the real API/cache routing and blocks external image downloads with `Content-Security-Policy: img-src 'self' data:` so fixtures use deterministic fallback images without contacting TMDB's CDN. Adapter tests cover complete image URL construction. Browser telemetry remains local; no real provider credentials are used.

- [ ] Write failing built-app tests: search `Tom`, assert seven fixture names in order, movie/TV titles, no IDs/actions, and initial/loading examples. Exercise icon plus keyboard submission, missing/broken image, empty `200`, failing `500`, malformed response, slow responses, clear-during-load, quota rejection, and a non-BMP name. Assertions use visible rows, input/busy state, and absence of extra messages, not implementation CSS classes.
- [ ] Write `test_real_browser_private_cache_reuse` in a fresh Chromium context with **no** `page.route`, context routing, HAR replay, or service-worker interception. Submit the same completed query twice; observe API/stub counters outside the browser and assert one search/provider dispatch, while normal bootstrap runs once. Assert exact cache header and absent cookie variation on the first network response. Change the guest cookie through normal test bootstrap/expiry setup and repeat in the same browser: successful search data remain identity-independent and can be reused.
- [ ] Add opt-in `test_cache_expires_after_300_seconds`: keep the production header unchanged, wait just over 300 real seconds via asynchronous test timers, repeat, and assert a second search/provider dispatch. Run it as a separately labelled slow check with a bounded per-test timeout, not a fake JS clock (that does not age the browser network cache). During agent execution keep the process asynchronous and give progress updates at least every 60 seconds. Normal CI runs cache reuse; the slow check runs in its own CI job/manual full verification.
- [ ] Run `uv run python tests/support/run_e2e.py --suite normal`; expect meaningful failures until harness/wiring completes. Implement only the test harness and necessary integration fixes; do not change feature behavior or shorten the production cache lifetime to pass tests.
- [ ] Run `uv run python tests/support/run_e2e.py --suite normal` and `uv run python tests/support/run_e2e.py --suite cache-expiry` against the exported app and actual ingress. Confirm errors stop loading and leave blank results, while provider failures remain `500` server-side. Check migrations/state after repeated searches contain session/usage data and no catalog/result/mapping tables or columns holding query content.
- [ ] Run the final bounded verification set: `uv run ruff check .`, `uv run pyrefly check`, `uv run pytest tests/unit tests/http -q`, isolated-Postgres integration tests, `uv run python scripts/check_boundaries.py`, `npm --prefix client run typecheck`, `npm --prefix client run lint`, `npm --prefix client test -- --runInBand`, `npm --prefix client run export:web`. Regenerate schema/client code and require `git diff --exit-code -- contracts/openapi.json client/src/people/adapters/generated`. Run `git diff --check`; inspect the changed-file list for unrelated or credential files.
- [ ] Commit the verified integration deliverable: `test: verify people search and browser caching end to end`. Record exact command results and any environmental limitation in the handoff. Do not claim live provider, hosted deployment, or native testing if only fixture-backed web checks ran.

## Coverage and self-review

Self-review complete: each design requirement is assigned above. Task 1 owns query/order/count and dispatch rules; Task 2 owns provider eligibility/title/image/default translation; Task 3 owns durable guest/admission state; Task 4 owns status/headers/schema/session transport; Task 5 owns generated validation and normal browser fetch semantics; Task 6 owns wireframe interactions and blank presentation; Task 7 owns runtime, telemetry, and dependency boundaries; Task 8 proves the composed web flow and real HTTP cache. All five Review Focus cases have explicit owning tests. Shared signatures/field names above are the integration contracts; generated wire names are translated only in adapters. No independent subsystem or future feature is bundled into F001.

These are **planned commands and acceptance criteria**, not results of implementation. No product code, dependencies, migrations, or runtime artifacts have been created by writing this plan.

## Execution handoff

No execution method has been selected. Ask the owner to review this plan and choose before implementation:

- **Native, recommended for this plan:** the primary agent implements the eight tasks in sequence, followed by an independent whole-branch review. Tasks share the core, admission, API, and client contracts closely, so keeping one implementer avoids repeated context setup while review still checks the final integration.
- **Subagent-driven:** a fresh implementer and reviewer per task, followed by a whole-branch review. More independent task gates, with additional context/review cost.

Use the selected method's required skill at execution. Detect the existing linked worktree and preserve the feature branch rather than creating redundant isolation. A tool/sandbox restriction is not permission to skip checks or publish; report concrete limitations and retain the approved scope.

## Primary references checked during planning

- [Expo project creation](https://docs.expo.dev/more/create-expo/): SDK 58 template; [Expo unit testing](https://docs.expo.dev/develop/unit-testing/): jest-expo setup.
- [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/): overriding request-validation and exception handlers.
- [HTTPX async clients](https://www.python-httpx.org/async/): long-lived async client lifecycle.
- [Postgres locking](https://www.postgresql.org/docs/current/explicit-locking.html): ordered transactional locking for admission.
- [Hey API Zod generation](https://heyapi.dev/docs/openapi/typescript/plugins/zod): generated runtime validators.
- [Playwright request routing](https://playwright.dev/docs/api/class-browsercontext#browser-context-route): routing disables HTTP caching; cache acceptance tests use real local HTTP instead.
