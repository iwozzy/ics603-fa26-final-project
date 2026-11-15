# Lumiere F001 Search People Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Lumiere's approved people-search feature: up to seven valid people from the provider's default first page, in provider order, through the wireframed Expo interface.

**Architecture:** A monorepo contains independent backend, frontend, and browser-test projects. Both application sides use domain → application → adapters → bootstrap layers with dependencies pointing inward. Root `openapi.json` is the sole backend/frontend contract; only guest/session and usage state is persisted.

**Tech Stack:** Python 3.13+/uv, FastAPI/Pydantic, HTTPX, async SQLAlchemy/psycopg/Alembic, Postgres/Neon, Logfire, import-linter; TypeScript, Expo/React Native/web/Router, npm, Jest/jest-expo/RNTL, Zod/Hey API, eslint-plugin-boundaries; separate Playwright package, Docker/Caddy, Make.

**Spec:** [Approved F001 design](../specs/2026-11-13-F001-search-people-design.md), [amended architecture](../specs/2026-11-09-application-architecture-design.md), and [repository structure guide](../../samples/architecture-and-repo-structure-guide.md). Revised to incorporate the guide at the owner's request. Feature-specific agreed behavior takes precedence over the guide's general examples.

## Global Constraints

- The application is called **Lumiere** (owner revision, 2026-11-15). Use `lumiere` where lowercase naming is conventional: backend distribution/import package `lumiere`, Expo slug `lumiere`, npm packages `lumiere-frontend` and `lumiere-e2e`. Display name, web document title, and API/OpenAPI title are `Lumiere`. Keep framework-required names such as `frontend/src/app/` and the wireframe heading `Cast & Crew`.

- Python 3.13+; preserve `backend/pyproject.toml`, `backend/.python-version`, existing Ruff/Pyrefly/coverage configuration, and uv's `exclude-newer = "3 days"` policy. The owner has already moved Python tooling into `backend/`; do not recreate a root Python project.
- Submit on Enter/Return or clicking/tapping the search icon. Typing does not initiate search.
- Use only the provider's first page; return up to the first seven valid people in provider order. No sorting, deduplication, or additional-page requests.
- A valid person has a usable provider ID and a nonblank name. Optional display omissions never exclude a person.
- Send only TMDB's required `query` parameter; omit optional parameters. Authentication uses the authorization header.
- All search API failures return HTTP `500`; successful empty results return `200`. Both leave a blank results area without an added message.
- Every successful search response has exactly `Cache-Control: private, max-age=300`. Omit `Vary: Cookie`; errors use `Cache-Control: no-store`.
- Preserve initial/loading example-search guidance from the wireframes; add no additional hint messages.
- Display up to three known-for titles in provider order, including TV. Construct image URLs with `https://image.tmdb.org/t/p/w180_and_h180_face/` and `profile_path`, with one joining slash.
- Omit IDs from responses. Retain no people, provider mappings, queries, provider payloads, or result lists. Selection capture and person identity mapping belong to following.
- Domain and application are framework-free. Backend cores import no FastAPI, Pydantic, HTTPX, SQLAlchemy, or Logfire; frontend cores import no React, React Native, Expo, fetch, or generated transport code.
- Application use cases own transaction boundaries through an owned UnitOfWork protocol. Repositories flush/query but never commit; no database transaction spans a provider call.
- Separate npm packages in `frontend/` and `e2e/`, without npm workspaces or a root package.json. Browser tests never import frontend or backend internals.
- Enforce durable global/session/IP admission and provider budgets; conservatively count dispatched failures. No hidden provider retries.
- Follow AGENTS.md: never inspect, write, print, or commit operator secrets. Runtime access is operator-supplied; test values are synthetic and isolated. Never load existing credential files.
- No future-feature scaffolding, search cache port, workers, AI, registration, native release, SSE, or job framework in F001.

## Review Focus

1. Non-BMP names, accents, apostrophes, and length boundaries: preserve/encode input once and count Unicode code points consistently (Tasks 1, 5, 6).
2. Heterogeneous provider records and malformed optional values: exclude only invalid IDs/names while preserving valid people and mixed title order (Task 2).
3. Clear/edit/submit races, old failures, and unmount: only the current UI submission may change results/loading (Task 6).
4. Concurrent admission, rollback, crashes, and UTC rollover: application-owned transactions enforce durable caps without resetting cumulative usage (Tasks 1, 3).
5. Browser caching obscured by test mocks or cookie changes: prove real HTTP-cache reuse without browser request routing and preserve production headers (Tasks 5, 8).

## How the general guide is adapted

| Guide direction | F001 plan decision |
| --- | --- |
| Separate toolchain roots | Existing `backend/` uv project, new `frontend/` npm project, new `e2e/` npm project; root Makefile orchestrates them. |
| Product/package naming | Adapt the guide's generic Python `app` package to `lumiere`; retain Expo Router's conventional `src/app/` route directory. |
| Domain/application/adapters/bootstrap | Use `backend/src/lumiere/` and `frontend/src/` layers with capability-named ports. One compact application initially; do not create bounded contexts or empty future modules. |
| Application-owned transactions | Application `UsageAdmissionService` and `GuestSessionsService` use a UnitOfWork factory; Postgres repositories never commit automatically. |
| UI hooks own interaction state | Replace the earlier application controller proposal with a stateless search use case and an inbound `useSearchPeople` hook owning loading, cancellation, generations, and stale-result protection. No debounce for explicit submission. |
| Root OpenAPI + generated client boundary | Commit root `openapi.json`; generate and commit frontend types/Zod schemas, which is an explicitly permitted alternative to the guide's gitignored default. Generate no request SDK so the adapter controls normal HTTP caching. |
| Architecture enforcement | Use import-linter and eslint-plugin-boundaries instead of a custom import-scanning script; test the actual configured tools with forbidden imports. |
| Two Neon connections | App uses `DATABASE_URL` (pooled); migrations use `MIGRATION_DATABASE_URL` (direct); both use `postgresql+psycopg://`. Do not inspect actual values. |
| Same-origin deployment | One combined static-web/Caddy image plus backend; local Postgres is an optional local Compose profile, with Neon externally supplied for deployment. No separate static web service is needed. |
| General errors/cache/retry examples | Keep F001's `500`-only failures, browser-only cache policy, and one provider attempt. Do not introduce the guide's 429/502/503/504 responses or SearchCache abstraction. |
| Trace framework integrations | Configure instrumentation outside the core, but apply the approved telemetry exclusions; do not enable raw URLs, bodies, queries, or credentials by default. No Tracer port is needed for this small use case. |
| Recommendations/open questions | Defer per-PR Neon branches, EAS/native builds, shared TS packages, workspaces, and team-specific deployment choices. Local isolated Postgres is sufficient for CI. |

Paths below are repository-root-relative; add Python `__init__.py` files only for implemented packages. Commands are launched from the repo root using `uv --directory backend run …`, `npm --prefix frontend …`, and `npm --prefix e2e …`.

## File map

| Responsibility | Planned files |
| --- | --- |
| Backend domain | `backend/src/lumiere/domain/people.py`, `access.py`, `errors.py`: frozen display/access values, policy values, owned failures. |
| Backend application | `backend/src/lumiere/application/ports/catalog.py`, `usage.py`, `sessions.py`, `unit_of_work.py`, `clock.py`; `use_cases/search_people.py`, `usage_admission.py`, `guest_sessions.py`: orchestration and explicit commits. |
| TMDB outbound adapter | `backend/src/lumiere/adapters/outbound/clients/tmdb_people/client.py`, `dto.py`, `mapper.py`: HTTP, boundary validation, translation. |
| Persistence outbound adapter | `backend/src/lumiere/adapters/outbound/persistence/models.py`, `repositories.py`, `unit_of_work.py`, `session.py`; `backend/alembic.ini`, `migrations/env.py`, `migrations/versions/0001_guest_usage.py`. |
| HTTP inbound adapter | `backend/src/lumiere/adapters/inbound/http/routers/v1/people.py`, `guest_session.py`, `schemas/people.py`, `deps.py`, `errors.py`, `context.py`. |
| Backend composition | `backend/src/lumiere/bootstrap.py`, `config.py`, `observability.py`, `main.py`: settings, concrete wiring, factory and lifespan. Treat all four as composition-layer modules for lint contracts. |
| Backend tests | `backend/tests/unit/domain/`, `unit/application/`, `fakes/`, `integration/persistence/`, `integration/clients/`, `api/`. Provider tests use MockTransport; API tests use ASGITransport. |
| Frontend domain/application | `frontend/src/domain/people.ts`, `errors.ts`; `application/ports/people-search-repository.ts`, `guest-session-repository.ts`; `application/use-cases/search-people.ts`; colocated tests. |
| Frontend outbound API | `frontend/src/adapters/outbound/api/people-search-repository.ts`, `guest-session-repository.ts`, `mappers.ts`, `generated/`; colocated tests. Only files within this API adapter subtree import generated artifacts. |
| Frontend inbound UI | `frontend/src/adapters/inbound/ui/SearchPeopleScreen.tsx`, `PersonRow.tsx`, `useSearchPeople.ts`, `PeopleSearchContext.tsx`; colocated tests. |
| Frontend composition/routes | `frontend/src/bootstrap/container.ts`, `Providers.tsx`; `frontend/src/app/_layout.tsx`, `index.tsx`; `frontend/src/test-utils/fakes/`, `renderWithPorts.tsx`. |
| Contracts/enforcement | Root `openapi.json`; `backend/scripts/export_openapi.py`; import-linter contracts in `backend/pyproject.toml`; `frontend/openapi-ts.config.ts`, `eslint.config.mjs`; architecture checks in each project's tests. |
| Browser testing | `e2e/package.json`, `package-lock.json`, `tsconfig.json`, `playwright.config.ts`, `tests/search-people.spec.ts`, `tests/cache.spec.ts`, `support/tmdb-server.ts`, `support/stack.ts`, `Dockerfile`. |
| Delivery/tooling | `backend/Dockerfile`, `frontend/Dockerfile`, `deploy/caddy/Caddyfile`, `deploy/caddy/Caddyfile.test`, root `compose.yaml`, `compose.test.yaml`, `.dockerignore`, placeholder-only `.env.example`, `Makefile`, `README.md`, `.github/workflows/ci.yml`. |

Resolve compatible dependency versions at execution and commit each project's own lockfile. Retain existing backend tooling; add Hatchling src-package configuration, required runtime libraries, and pytest-asyncio/ASGI lifespan support/import-linter as dev tools. Initialize an Expo Router app using the currently documented SDK 58 template, rechecking compatibility at execution. Use npm, StyleSheet, jest-expo/RNTL, Zod v4 and Hey API; keep Playwright exclusively in `e2e/`.

**Layer enforcement:** allow inward and same-layer dependencies, with two explicit composition details. Backend `main/config/observability/bootstrap` form the outer composition layer. Frontend `_layout.tsx` is the sole route composition entrypoint allowed to install bootstrap `Providers`; other routes remain thin inbound adapters. Declare `PeopleSearchContext` in the inbound UI adapter: bootstrap imports/provides that context, and UI hooks import the sibling context, never bootstrap. Generated artifacts stay private to the outbound API adapter even from bootstrap and UI.

Tasks remain sequential. Each task has a behavior-first test cycle and an explicit-file commit; setup/configuration belongs to its owning deliverable. Do not create product files while reviewing this plan.

### Task 1: Backend core, transaction ports, and layer contracts

**Files:** Modify `backend/pyproject.toml`; create `backend/uv.lock`, domain/application files from the map, `backend/tests/fakes/search.py`, `unit/application/test_search_people.py`, `unit/domain/test_people.py`.

**Interfaces:** Frozen `PersonSummary(name: str, department: str | None, profile_image_url: str | None, known_for: tuple[str, ...])`, `SearchPeopleResult(query: str, people: tuple[PersonSummary, ...])`, `GuestContext(profile_id: UUID, session_id: UUID, ip_key: str)`, `Reservation(id: UUID)`, `GuestSession(context: GuestContext, proof: str, is_new: bool)`, and `AttemptOutcome` (`SUCCESS`, `FAILED`, `CANCELLED`) live in domain modules. `SearchFailed(category: str)` carries no HTTP type.

Application protocols: async `PeopleCatalog.search_first_page(query: str) -> tuple[PersonSummary, ...]`; async `UsageAdmission.admit(context: GuestContext, now: datetime) -> Reservation`, `mark_dispatched(reservation: Reservation) -> None`, `finish(reservation: Reservation, outcome: AttemptOutcome) -> None`, `release_undispatched(reservation: Reservation) -> None`; `Clock.now() -> datetime`. `SearchPeople(catalog: PeopleCatalog, admission: UsageAdmission, clock: Clock).execute(raw_query: str, context: GuestContext) -> SearchPeopleResult` is async.

Declare async `AccessUnitOfWork` with `usage: UsageRepository`, `sessions: GuestSessionRepository`, `commit() -> None`, `rollback() -> None`, and async context entry/exit. `UnitOfWorkFactory.__call__() -> AccessUnitOfWork` returns a fresh transaction scope. UoW context exit rolls back uncommitted changes; it never commits automatically.

Define the shared transaction types/ports in this task so imports and fakes are complete before Task 3. Domain/access owns immutable `CounterKey(scope: str, subject: str, feature: str, window: str)`, `ReservationRecord(id: UUID, provider_keys: tuple[CounterKey, ...], state: str)`, `StoredGuestSession(profile_id: UUID, session_id: UUID, expires_at: datetime)`, and `UsagePolicy`. Its required positive-integer fields are `global_requests_per_minute`, `session_requests_per_minute`, `ip_requests_per_minute`, `bootstrap_requests_per_ip_per_minute`, `global_provider_daily`, `session_provider_daily`, `ip_provider_daily`, `global_provider_total`, `session_provider_total`, `ip_provider_total`. Windows are UTC minute/day identifiers or a cumulative identifier; reservation states are `reserved`, `dispatched`, `success`, `failed`, `cancelled`, `released`.

Application transaction-scoped protocols: async `UsageRepository.lock_counters(keys: tuple[CounterKey, ...]) -> dict[CounterKey, int]`, `add_counts(deltas: Mapping[CounterKey, int]) -> None`, `add_reservation(record: ReservationRecord) -> None`, `get_reservation_for_update(reservation: Reservation) -> ReservationRecord`, `save_reservation(record: ReservationRecord) -> None`; async `GuestSessionRepository.find(token_digest: bytes, now: datetime) -> StoredGuestSession | None`, `create(context: GuestContext, token_digest: bytes, expires_at: datetime) -> None`. The owned `GuestSessions` protocol exposes async `bootstrap(proof: str | None, ip_key: str, now: datetime) -> GuestSession` and `resolve(proof: str | None, ip_key: str, now: datetime) -> GuestContext`. Implement declarations and recording fakes here; concrete persistence and services arrive in Task 3. Use standard-library types and typing.Protocol only.

- [ ] Set `backend/pyproject.toml` project name to `lumiere` and configure Hatchling to package `src/lumiere`. Add necessary package/dependencies, pytest paths, `asyncio_mode = "auto"`, and import-linter contracts. Use import-linter root package `lumiere` and enforce composition → adapters → application → domain, and forbid core imports of all framework/provider/persistence libraries with external-package inspection enabled.
- [ ] Write failing use-case tests with recording fake catalog/admission/clock implementations. Primary assertions in `test_preserves_provider_order_and_limits_to_seven`:

```python
result = await search.execute(" Tom ", context)
assert result.query == "Tom"
assert [p.name for p in result.people] == [str(i) for i in range(7)]
assert catalog.queries == ["Tom"]
assert admission.dispatch_count == 1
assert admission.outcomes == [AttemptOutcome.SUCCESS]
```

`test_short_or_empty_page_never_fetches_more` checks unchanged 0/3-entry pages. `test_query_codepoint_boundaries` accepts 1/200 Unicode code points, rejects 201/blank without dispatch, and preserves accents/non-BMP text. `test_admission_failure_never_dispatches` and `test_failure_or_cancellation_keeps_spent_allowance` assert no retry and conservative cleanup.
- [ ] Run `uv --directory backend run pytest tests/unit -q`; confirm failures on missing behavior, not missing dependencies.
- [ ] Implement validation, admission/dispatch orchestration, ordered `candidates[:7]`, and cancellation-safe completion. Search calls the admission port outside provider I/O; Task 3's application service will own its individual transactions. No result persistence or SQL/framework imports.
- [ ] Re-run unit tests, `uv --directory backend run lint-imports`, `uv --directory backend run ruff check src tests`, and `uv --directory backend run pyrefly check`; expect pass.
- [ ] Commit: `feat: add people search core and transaction contracts`.

### Task 2: TMDB integration adapter

**Files:** Create the three `tmdb_people/` files and `backend/tests/integration/clients/test_tmdb_people.py`; reuse `docs/samples/api/tmdb/v3/search/person.json` unchanged, locating it from the repository path rather than the process working directory.

**Interfaces:** `TMDBPeopleCatalog(client: httpx.AsyncClient, max_bytes: int = 1048576)` implements `PeopleCatalog`; bootstrap supplies a long-lived configured client. Vendor Pydantic DTOs live in `dto.py`; `mapper.py` returns frozen domain summaries, not vendor DTOs.

- [ ] Write failing MockTransport tests. `test_fixture_order_titles_and_images` asserts:

```python
assert request.url.path == "/3/search/person"
assert dict(request.url.params) == {"query": "Tom"}
assert [p.name for p in people[:7]] == ["Tom Skerritt", "Tom Holland", "Tom Hanks", "Tom Cruise", "Tom Hopper", "Tom Hardy", "Tom Welling"]
assert people[4].known_for == ("The Umbrella Academy", "Resident Evil: Welcome to Raccoon City", "I Feel Pretty")
assert people[6].known_for == ("Smallville", "Lucifer", "The Fog")
assert people[0].profile_image_url == "https://image.tmdb.org/t/p/w180_and_h180_face/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg"
```

`test_strict_required_tolerant_optional_fields` skips boolean/string/zero/negative/missing IDs and blank/nonstring names, but retains malformed optional fields as fallbacks. Mixed movie/TV titles preserve up to three nonblank titles. `test_duplicates_preserve_sequence`, `test_bad_envelope_is_failure_not_empty`, and `test_timeout_throttle_bad_json_oversize_have_one_attempt` assert no retries or page/detail/configuration lookup.
- [ ] Run `uv --directory backend run pytest tests/integration/clients -q`; confirm behavioral failures without containers or real provider access.
- [ ] Implement bounded streaming/decoding, per-record validation and translation. Discard source IDs after validity checks. Optional data is tolerant; one bad record does not invalidate the page. Join the fixed image base with a usable relative path, stripping joining slashes; absolute/unusable paths become `None`. Raise owned errors rather than HTTPX/Pydantic exceptions across the port.
- [ ] Re-run core and provider tests and `lint-imports`; expect pass. Verify no search response is retained on the adapter.
- [ ] Commit: `feat: add TMDB people adapter and contract fixtures`.

### Task 3: Application-owned guest/admission transactions and Postgres repositories

**Files:** Create `backend/src/lumiere/application/use_cases/usage_admission.py`, `guest_sessions.py`, persistence adapter/migration files, root `compose.test.yaml`, and `backend/tests/unit/application/test_access.py`, `integration/persistence/conftest.py`, `test_sessions.py`, `test_admission.py`, `test_unit_of_work.py`. Consume the complete shared declarations from Task 1.

**Interfaces:** `UsageAdmissionService(uow_factory: UnitOfWorkFactory, policy: UsagePolicy)` implements the Task 1 admission port. `GuestSessionsService(uow_factory, policy)` implements application `GuestSessions.bootstrap(proof: str | None, ip_key: str, now: datetime) -> GuestSession` and `resolve(proof: str | None, ip_key: str, now: datetime) -> GuestContext` (async). HTTP depends on those protocols, not Postgres classes. The core handles opaque proofs; cookie extraction/creation belongs to the HTTP adapter.

`PostgresAccessUnitOfWork` implements Task 1's UoW contract and binds repositories implementing those exact signatures. A stored session contains identity/expiry, not a chosen current-IP quota context: bootstrap/resolve combine stored identity with the server-resolved `ip_key` from the current request.

`UsagePolicy` requires positive global/session/IP request-per-minute, IP bootstrap-per-minute, and global/session/IP provider daily/cumulative caps. No live admission without explicit configuration. Isolated tests use daily caps of two and sufficiently high request caps to test concurrent budget admission.

- [ ] Write failing fake-UoW application tests proving policy checks and explicit commits; `test_admission_commits_before_provider_and_rolls_back_failure` asserts `commit_count == 1` on admission, rollback/no capacity on failure, and no active UoW during a provider call. Test idempotent mark/finish/release and no refund for a dispatched/unknown reservation.
- [ ] Write real-Postgres tests. `test_concurrent_cap_and_restart` starts 20 admissions with cap two and asserts exactly two admitted, durable counter two, and another rejection through a newly constructed service/UoW. `test_utc_rollover_keeps_total_cap`, `test_repository_does_not_commit`, `test_uncommitted_exit_rolls_back`, `test_sessions_reuse_expire_and_store_only_digests`, `test_existing_session_uses_current_server_ip_key`, and `test_storage_outage_blocks_dispatch` pin the boundary rules. Inspecting catalog absence belongs in persistence tests, not browser tests.
- [ ] Start the isolated loopback-bound Postgres 18 service with `docker compose --env-file /dev/null -f compose.test.yaml up -d --wait`. Run backend access unit and persistence tests; expect failures before implementation. The test launcher supplies an isolated test database URL and guards against non-test databases, without loading credential files.
- [ ] Implement **only** guest profiles/sessions, usage counters, and reservations. `PostgresAccessUnitOfWork` opens a fresh AsyncSession/transaction and binds repositories; explicit application `uow.commit()` is the only commit path. Repositories use SQL/flush and deterministic row-lock order, safely creating missing counter rows before locking. `__aexit__` rolls back uncommitted work, including failures/cancellation.
- [ ] Implement application services using short separate UoW scopes for admission, marking dispatch, and settling/releasing. Policy checks all scopes before updating counts. Count requests and reserve one provider attempt on admission; only release a proven-undispatched reservation once. Unknown/crashed reservations stay charged. Bootstrap atomically applies its IP admission and creates/reuses a guest session with runtime-generated proof, digest storage, 24-hour server expiry, and no persistent browser-cookie expiry. Persist no person/search data.
- [ ] Configure pooled `DATABASE_URL` for application sessions and direct `MIGRATION_DATABASE_URL` in Alembic, both `postgresql+psycopg://`. Tests can point both at the same disposable Postgres. Migrations run explicitly, outside request/startup races. Re-run tests plus `lint-imports`; verify no open transaction during external I/O, then tear down isolated test resources.
- [ ] Commit: `feat: add application-owned guest and usage transactions`.

### Task 4: Inbound HTTP, composition, and root OpenAPI

**Files:** Create HTTP/composition files from the map, `backend/scripts/export_openapi.py`, root `openapi.json`, and `backend/tests/api/conftest.py`, `test_people.py`, `test_sessions.py`, `test_openapi.py`.

**Interfaces:** `HttpServices` in inbound `deps.py` holds owned search/session services. `create_app(services: HttpServices) -> FastAPI` in `lumiere/main.py` is importable without runtime settings or network/database access. `build_container(settings: Settings) -> AppContainer` in bootstrap constructs concrete adapters and exposes services and async startup/close; `create_runtime_app() -> FastAPI` wires lifespan. Start production with `uvicorn lumiere.main:create_runtime_app --factory`. Routers do not import bootstrap/config/observability.

`POST /api/v1/guest-session` returns `200`, empty body, no-store, and a new cookie only when required. `GET /api/v1/people/search?query=...` uses Pydantic schemas only in inbound `schemas/people.py`: `PersonResponse` has name, nullable department/profile_image_url, known_for (max three strings); `SearchPeopleResponse` has query and people (max seven), no IDs.

- [ ] Write failing ASGITransport tests with fake application ports and lifespan. `test_success_and_empty_success_headers` asserts:

```python
assert response.status_code == 200
assert response.headers["cache-control"] == "private, max-age=300"
assert "cookie" not in response.headers.get("vary", "").lower()
assert "set-cookie" not in response.headers
assert set(response.json()) == {"query", "people"}
assert set(response.json()["people"][0]) == {"name", "department", "profile_image_url", "known_for"}
```

Also test `people: []`. `test_every_failure_is_empty_500` covers validation, session, all throttle/budget scopes, upstream response, timeout, unavailable storage, invalid output, and unhandled exception: status 500, empty body, no-store, and no dispatch if rejected first. `test_openapi_search_only_has_200_and_500` pins response keys; assert OpenAPI `info.title == "Lumiere"`. Session tests cover HttpOnly/same-site lax/Path=/, Secure on HTTPS, no persistent cookie expiry, bootstrap no-store/origin protection, forged forwarding headers, and IPv6 normalization.
- [ ] Run `uv --directory backend run pytest tests/api -q`; confirm missing-behavior failures.
- [ ] Implement routers/dependency parsing and route-aware failure handlers. Set FastAPI title to `Lumiere`. Override FastAPI's default validation statuses and automatic OpenAPI 422 entry for search, without dictating unrelated future operations. Resolve peer IP only through configured trusted proxy rules and derive the keyed quota identity outside core.
- [ ] Wire one HTTPX AsyncClient per provider base URL at bootstrap; close in lifespan. Use HTTP/2 fallback, zero transport retries, connect timeout two seconds, overall provider deadline five seconds, max 1 MiB response, pool 20 connections/10 keepalive. Use a database pool of five plus five overflow and an app deadline of seven seconds. Pydantic Settings stays outside core, loads no dotenv file, hides inputs in validation errors, and emits no supplied values on startup failure.
- [ ] Export deterministic sorted root OpenAPI with inert services and no runtime settings/adapters. Run `uv --directory backend run python scripts/export_openapi.py`, API/core/provider tests, and import-linter. No exporter import may initialize a real session/client or load configuration. Compare a second export with the first for determinism before initial commit.
- [ ] Commit: `feat: expose people search API and root OpenAPI contract`.

### Task 5: Frontend application and outbound API boundary

**Files:** Create `frontend/package.json`, lockfile, app/TypeScript/Jest/Hey API/ESLint configuration, frontend domain/application/outbound API files and colocated tests from the map. Update `.gitignore` for dependencies/build/test outputs.

**Interfaces:** Domain `PersonSummary` uses `name: string`, `department: string | null`, `profileImageUrl: string | null`, `knownFor: readonly string[]`; `SearchResult` holds `query: string` and `people: readonly PersonSummary[]`, without IDs. `normalizeQuery(raw: string): string` trims/checks 1–200 Unicode code points and throws an owned invalid-query error. Application `PeopleSearchRepository.search(query: string, signal: AbortSignal): Promise<SearchResult>` and `GuestSessionRepository.ensure(signal: AbortSignal): Promise<void>`, `invalidate(): void` are interfaces. Stateless `SearchPeople(repository: PeopleSearchRepository).execute(rawQuery: string, signal: AbortSignal): Promise<SearchResult>` validates then delegates; it owns no view state, timers, generation, or React lifecycle.

`HttpPeopleSearchRepository(fetchImpl, sessions)` and `HttpGuestSessionRepository(fetchImpl)` implement the ports. DTO-to-domain translation is in API `mappers.ts`; generated transport names stay private to the adapter subtree.

- [ ] Initialize Expo Router in `frontend/` with the currently documented SDK 58 template, remove demo content, and retain one `src/app/` route root. Install compatible jest-expo/Jest/RNTL, Zod v4, Hey API, and eslint-plugin-boundaries. Set npm package name to `lumiere-frontend`, Expo display name to `Lumiere`, slug to `lumiere`, and web document title to `Lumiere`. Do not install Playwright here. Provide test/typecheck/lint/generate:api/export:web scripts and commit `frontend/package-lock.json`.
- [ ] Configure Hey API input `../openapi.json`, output `src/adapters/outbound/api/generated`, TypeScript and Zod definition plugins. Commit generated definitions/validators; generate no request SDK. Configure boundaries including external/framework imports, generated isolation, UI/bootstrap direction, and the single `_layout` composition exception.
- [ ] Write failing domain/application tests for 1/200/201/blank and non-BMP queries; invalid input makes zero repository calls. Write outbound adapter tests whose captured requests assert:

```typescript
expect(searchUrl).toBe('/api/v1/people/search?query=' + encodeURIComponent("Timothée O'Neil & 李😀"));
expect(searchOptions.credentials).toBe('same-origin');
expect(searchOptions.cache).toBeUndefined();
expect(searchOptions.headers?.['Cache-Control']).toBeUndefined();
expect(result.people[0]).not.toHaveProperty('id');
```

`test_repeated_calls_use_transport_without_result_cache` observes two fetch calls for two completed searches. `test_500_bad_json_bad_schema_abort_reject_without_retry` asserts rejection and invalidates readiness after a non-cancellation failure. `test_bootstrap_is_coalesced_and_reused` asserts one bootstrap for concurrent/subsequent calls; next manual attempt after invalidation bootstraps once. Bootstrap failure never dispatches search.
- [ ] Run `npm --prefix frontend test -- --runInBand`; confirm failures before implementation.
- [ ] Implement stateless use case, repositories, generated Zod validation, and mappers. Use relative same-origin URLs, cookie credentials, default browser cache behavior, and caller cancellation combined with an eight-second adapter deadline. Bootstrap caches only in-memory readiness, never cookies or result lists; recover on the next explicit submission, without replaying search. No frontend source references TMDB or another catalog vendor.
- [ ] Re-run tests/typecheck/lint/export. Regenerate twice and compare outputs; after initial generated commit, require `git diff --exit-code -- openapi.json frontend/src/adapters/outbound/api/generated`. No imports from generated code may escape the API adapter subtree.
- [ ] Commit: `feat: add frontend search use case and API adapters`.

### Task 6: Inbound UI hooks, composition, and wireframes

**Files:** Create inbound UI/bootstrap/test-utils files from the map and their colocated tests; replace generated routes with `frontend/src/app/_layout.tsx` and `index.tsx` only. No non-route files in `src/app/`.

**Interfaces:** UI-owned `SearchState` contains draft, submitted query, phase (`initial`, `loading`, `results`, `blank`), and people. `useSearchPeople()` returns state plus `setDraft(value: string): void` and `submit(): Promise<void>`. `PeopleSearchContext` exposes `{ searchPeople: SearchPeople }`; bootstrap `createContainer(fetchImpl)` builds API adapters/use case and `Providers` installs the UI-owned context. `renderWithPorts` wraps components/hooks with fakes, without importing the production container. Hook imports sibling context, domain/application types; it never constructs an HTTP repository or imports bootstrap.

- [ ] Write failing hook/component tests with RNTL `renderHook`/`act` and deferred fake repository promises. `test_latest_submission_wins_even_after_old_failure` submits A/B, resolves B, rejects A, and asserts phase results/submitted B/people B. `test_clear_or_unmount_invalidates_pending_completion` proves no repopulation or late state update. `test_duplicate_pending_query_is_ignored` asserts one repository call. Empty success and errors both assert blank people and loading false; invalid submissions invalidate old work before validating.
- [ ] Write screen tests for keyboard/pointer submission, no typing dispatch, IME composition protection, editable/focused input, changed-draft submission while loading, and retaining completed results during edits. Pin exact wireframe copy:

```typescript
expect(screen.queryByText('Cast & Crew')).not.toBeNull();
expect(screen.queryByText('Example searches:')).not.toBeNull();
expect(screen.queryByText('Timothée Chalamet (Actor)')).not.toBeNull();
expect(screen.queryByText('Hayao Miyazaki (Director, Writer)')).not.toBeNull();
expect(screen.queryByText('Autumn Durald Arkapaw (Cinematographer)')).not.toBeNull();
```

Placeholder is `Search for actors, directors, or creative team to follow`. Examples appear in initial/loading states and disappear after a completed empty/failing search. Assert no additional hints/messages/Follow/Movies actions, three mixed titles maximum, and silhouette fallback without dangling separators.
- [ ] Run frontend tests; confirm behavior failures.
- [ ] Implement submission generation, AbortController lifetime, duplicate suppression, draft/submitted state, and stale-success/failure/finally guards **inside the inbound UI hook**, not the application use case. All completion paths check current generation. Clearing/unmount aborts/invalidate pending work; no debounce or automatic submission. Use RN primitives/StyleSheet, busy accessibility state without extra announcements, visible focus, and a 44×44 minimum search target. Keys are transient submission/position keys, not new IDs.
- [ ] Wire production Providers only at `_layout`; other routes import screens. Run tests/typecheck/lint/export and inspect initial/loading/results/narrow viewport against the supplied wireframes. Fix clipping without adding copy or future controls.
- [ ] Commit: `feat: add people search UI and composition`.

### Task 7: Same-origin packaging, instrumentation, and monorepo commands

**Files:** Create backend/frontend Dockerfiles, deploy Caddyfile, root Compose/Makefile/placeholder `.env.example`/README/CI files, `backend/src/lumiere/observability.py`, `backend/tests/unit/test_observability.py`, `test_architecture_contracts.py`, `frontend/src/test-utils/architecture.test.ts`; extend composition wiring. Use tool configs already introduced in Tasks 1 and 5 rather than a bespoke scanner.

**Interfaces:** `configure_observability(enabled: bool) -> None` is composition-only. `/health/live` and `/health/ready` make no catalog calls. Root Makefile targets: `dev`, `test`, `generate`, `lint`, `migrate`, `test-integration`, `test-e2e`, `test-cache-expiry`. The first five orchestrate the guide's independent projects without making them workspaces; `test` is container-free, and `test-integration` explicitly launches isolated persistence checks.

- [ ] Write failing telemetry tests with an in-memory exporter and synthetic sentinels: preserve correlation, latency, failure categories, selected/invalid counts and quota outcomes, while omitting full query, payload, cookie/auth values and connection strings. Write architecture-tool checks that run configured import-linter/ESLint against temporary forbidden imports: core→framework, core→adapter, UI→generated, UI→bootstrap, and non-layout route→bootstrap must fail; the actual tree and `_layout` wiring pass. Do not test a homemade approximation of the real linter.
- [ ] Run the targeted backend/frontend checks; confirm failures before wiring instrumentation/contracts.
- [ ] Configure Logfire at FastAPI/SQLAlchemy/HTTPX adapter/composition boundaries with sanitized spans. Disable raw URLs/query strings, bodies, SQL parameters, cookies/auth values and unsanitized exception payloads; default instrumentation must not override privacy exclusions. Disable Uvicorn/Caddy query-bearing access logs. Telemetry defaults off without operator setup and cannot block search.
- [ ] Package backend with a multi-stage uv build and `uv sync --frozen --no-dev`; package frontend via npm/export then copy `dist/` to a Caddy stage. Caddy serves static assets and proxies `/api/*` to backend without altering cache headers or adding cookie variation. TLS/HTTP2 is ingress-owned with HTTP/1.1 upstream fallback. Root Compose has backend and combined web/Caddy plus an optional local Postgres profile; deployed database remains Neon. No separate static web service, workers, Redis, or CORS middleware.
- [ ] Add named settings for pooled/direct database connections and required caps. Placeholder-only `.env.example` documents variable names without actual values; scripts/builds must not read or copy an existing environment file. Local/test Compose commands explicitly use `--env-file /dev/null` unless an operator runs their own configuration. Use root `.dockerignore` and narrow build contexts to exclude VCS, credentials, dependencies and artifacts. Run migrations as a separate operator/Make target through the direct connection.
- [ ] Add README setup/run/generate/test instructions, exact response/cache behavior and telemetry diagnosis, no search persistence, and no hosted publishing. CI has independently locked/path-filtered backend/frontend/e2e jobs; changes to root OpenAPI, shared fixture/guide/spec docs, Compose, or Makefile trigger all affected jobs. Browser tests run for backend, frontend, or e2e runtime changes. Contract-drift and import/boundary checks are mandatory. Use isolated Postgres, never a required live TMDB/Neon/Logfire service; per-PR Neon branches remain optional future work.
- [ ] Run import-linter, frontend boundaries lint, telemetry tests, both image builds, and readiness checks with isolated Postgres; assert readiness calls no provider. Verify `make generate` exports root OpenAPI then generates frontend validators without secrets or live services; `make lint` invokes both projects' lint/type/boundary checks.
- [ ] Commit: `build: add monorepo runtime and architecture enforcement`.

### Task 8: Independent Playwright package and real browser caching

**Files:** Create all `e2e/` files from the map and `deploy/caddy/Caddyfile.test`; update test Compose, Makefile, README and CI. Playwright tests stay under `e2e/tests`; API-level assertions stay under `backend/tests/api`, and persistence assertions stay under backend integration tests.

**Interfaces:** `npm --prefix e2e test` runs normal built-app tests; `npm --prefix e2e run test:cache-expiry` runs the labelled slow suite. `support/stack.ts` manages the isolated Compose topology and cleanup. `support/tmdb-server.ts` serves the fixture over real HTTP, with delay/empty/error scenarios and test-only request counters; it is a test service, not production functionality. The fixture server has its own Dockerfile in `e2e/` and never imports backend/frontend source. Test Caddy blocks external image downloads with `Content-Security-Policy: img-src 'self' data:` while preserving real API/cache routing, so browsers use fallback images without contacting the vendor CDN.

- [ ] Initialize separate `e2e/package.json`/lock/TypeScript/Playwright configuration with package name `lumiere-e2e`, with no frontend/backend code dependencies and no root workspaces. Stub vendor HTTP outside the browser; expose test control/counts only in the isolated test service, never production API. Read shared fixture data from docs; API schema coupling is only root `openapi.json` when needed.
- [ ] Write failing browser-flow tests for seven fixture names/order/mixed titles, initial/loading examples, web document title `Lumiere`, icon/keyboard submission, empty/failure blank results, slow/overlapping requests, clear-during-load, quota rejection, Unicode input, and image fallback. Observe HTTP status/header behavior through browser network events; do not duplicate ASGI schema-unit tests here.
- [ ] Write `test_real_browser_private_cache_reuse` in a fresh Chromium context with **no** page/context routing, HAR replay, or service-worker interception. Submit the same completed query twice and assert one provider dispatch using the stub counter. Observe exact cache-control/absent cookie variation on the first network response; normal bootstrap runs once. Replace the guest cookie through normal noncacheable bootstrap in that browser, repeat the same search, and assert identity-independent cached data can still be reused.
- [ ] Write opt-in `test_cache_expires_after_300_seconds`: keep the production header unchanged, wait just over 300 real seconds asynchronously, then assert another dispatch. A mocked JS clock does not age the browser network cache. Give the slow test its own bounded timeout/job; report progress at least every 60 seconds during agent execution. Normal CI proves reuse; a separate slow job/manual full check proves expiry.
- [ ] Run the normal package test command; expect failures until test-stack wiring is implemented. Implement only the harness and required integration fixes, preserving production semantics. Test topology is local Postgres/backend/combined web-Caddy plus the stub; no live provider, operator credentials or browser request interception.
- [ ] Run both normal and cache-expiry packages against the built app/real ingress. Run backend domain/application/API/provider tests, isolated persistence tests, import-linter, frontend unit/component/adapter/type/lint/export checks, and e2e typecheck. `make test` runs container-free backend/frontend checks; `make test-integration`, `make test-e2e`, and `make test-cache-expiry` are explicit. `make generate` followed by `git diff --exit-code -- openapi.json frontend/src/adapters/outbound/api/generated` must show no drift. Run `git diff --check` and inspect changed filenames for unrelated/sensitive artifacts.
- [ ] Commit: `test: verify composed search and private browser caching`. Record actual commands/results and any environment limitation; do not claim native/live-provider/hosted verification from fixture-backed web checks.

## Coverage and self-review

The eight tasks retain the approved search behavior while applying the guide. Tasks 1–3 own pure rules, provider translation and application-owned durable transactions; Task 4 owns HTTP/schema/composition; Tasks 5–6 separate client application behavior from inbound UI lifecycle; Task 7 owns enforceable layers, privacy, commands and delivery; Task 8 owns browser-only acceptance. All five Review Focus cases have named checks. Signatures, root contract location, generated-code boundary, unit-of-work ownership, and per-package paths/commands are consistent across the tasks.

This document contains planned commands and acceptance criteria, **not implementation results**. Updating it creates no application scaffolding, dependencies, migrations or running services. The guide itself and existing backend files are inputs, not files to rewrite during planning.

## Execution handoff

No execution method has been selected. Ask the owner to review this revised plan and choose before implementation:

- **Native, recommended:** one implementer works through the eight dependent tasks, followed by independent whole-branch review. Keeping shared transaction/API/UI contracts in one context reduces repeated setup.
- **Subagent-driven:** fresh implementer and reviewer per task, plus whole-branch review, with more task gates and context cost.

Use the selected method's skill at execution and preserve the existing linked worktree/feature branch. Do not infer authorization to publish or skip blocked checks.

## Primary references checked during planning

- [Expo creation](https://docs.expo.dev/more/create-expo/) and [unit testing](https://docs.expo.dev/develop/unit-testing/).
- [FastAPI error handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/) and [HTTPX async lifecycle](https://www.python-httpx.org/async/).
- [Postgres locking](https://www.postgresql.org/docs/current/explicit-locking.html) and [Hey API Zod generation](https://heyapi.dev/docs/openapi/typescript/plugins/zod).
- [Import Linter layers](https://import-linter.readthedocs.io/en/stable/contract_types/layers/) and [forbidden imports](https://import-linter.readthedocs.io/en/stable/contract_types/forbidden/): include external dependencies in core prohibitions.
- [JS Boundaries dependency policies](https://www.jsboundaries.dev/docs/rules/dependencies/): use current local/external dependency policies, including unknown-file coverage, rather than deprecated rule names.
- [Playwright routing](https://playwright.dev/docs/api/class-browsercontext#browser-context-route): request routing disables HTTP caching; test caching through real local HTTP instead.
