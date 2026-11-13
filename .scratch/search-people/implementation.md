# Search people implementation

Status: resolved
Baseline: 00ab21a0a3ba6230ea0b97faa22aa895ddd052f8

## Prerequisites selected before implementation

- One npm package: Expo SDK 58, React Native for Web, TypeScript strict mode, Metro web bundling. Expo selects compatible React/React Native versions. No router or app query cache.
- Python 3.13, uv lockfile, FastAPI/Pydantic API, HTTPX async provider adapter, Uvicorn bound to loopback with access logging disabled. Same-origin static web served by Python after Expo export.
- Pydantic JSON Schema is the API contract source. Generate TypeScript with json-schema-to-typescript; Ajv validates responses using the same checked-in schema. No provider types in the client.
- Playwright Chromium tests exercise exported web through the real API and a controlled external TMDB HTTP server. pytest direct public-API tests substitute the external HTTP transport, preserving actual translation and operation code. No extra module test seams.
- Provider timeout: 5 seconds total (including response read); backend operation deadline: 6 seconds; browser deadline: 8 seconds. Configuration must keep provider < operation ≤ 7 seconds, leaving at least one second before the browser deadline. No retries. Immediate admission refusal, no concurrency wait queue.
- Maximum input: 200 Unicode code points after trimming; maximum raw request target: 4096 bytes; request bodies rejected on search. Provider JSON limited to 1 MiB. Provider IDs are positive integers (booleans and strings are rejected); profile paths are slash-prefixed filenames with no URL/query/fragment/path traversal.
- Local process bounds: 8 incoming searches and 4 outgoing calls in flight; each direction 60 admissions/minute and 1000 cumulative admissions until process restart. Single-process, in-memory settings only; durable/global accounting remains the separate public-release gate. Validation precedes provider admission. Settings configurable by environment, validated at startup.
- Instrumentation: allowlisted JSON events containing operation, outcome, elapsed time, admission/attempt counts only. No query strings, input/result content, exception text, credentials, HTTPX INFO logs, or automatic request instrumentation. No Logfire content export for this local increment.

## Agreed verification

The spec's Testing Decisions already confirm the web/public API seams. Use red → green vertical slices; run individual test files and typechecks as slices land, then the full suite. Verify real TMDB, the requested portrait transform, and actual browser HTTP caching separately. Record evidence below. Review against the pinned baseline and spec before committing to the existing branch.

## Evidence

- Initial public-API tracer was red (API module absent), then green. Initial browser tracer was red (search controls absent), then green.
- Direct API slices: 25 passing cases, covering malformed rows/envelopes, optional metadata, ranking/deduplication, response headers, bounds, concurrency/rate/cumulative admission, total provider timeout, and safe operation logging.
- Browser slices: submission/drafts/races/cache passed. Presentation checks exposed touch focus retaining the reveal; switching the keyboard rule to `:focus-visible` fixed toggle/move/reset while preserving keyboard reveal.
- Real TMDB smoke (2026-11-12, Pacific/Honolulu): one provider attempt through the rendered screen, HTTP 200, one normalized result, portrait decoded at exactly 180×180 using the required base, success cache header exact, browser transfer bytes `[594, 0]`, actual runtime logs excluded query/result/credential content.
- Installed Expo 58.0.23 with its matched React 19.3 / React Native 0.88 / TypeScript 6 packages, respecting npm's configured dependency-age cutoff. SDK 58 removed the high-severity findings from the initial SDK 55 tooling. Four moderate build-tool dependency advisories (`glob`/`minimatch` and dependents) remain; `npm audit fix` cannot select fixes within the configured age cutoff. They concern local tooling; review again before public delivery. No age-policy bypass or arbitrary dependency overrides were added.
- Final full suite on SDK 58: `npm test` passed 25 API + 23 Chromium cases (including actual HTTP-cache reuse and the eight-second client deadline). `npm run typecheck` and `npm run check:python` passed.
- Repeated live smoke on the final SDK 58 build passed with the same evidence: one attempt, one result, 180×180 portrait, cache transfer bytes `[594, 0]`, content excluded from runtime logs.
- [Two-axis review](review.md) complete: Standards 0 findings; Spec 1 P2 deadline-configuration finding, corrected and independently rechecked. Startup now rejects backend deadlines exceeding the browser budget. The final full regression run passed all 25 API + 23 browser cases again after the correction; both typechecks/lint also passed. Contract regeneration produced no diff.

## Repository organization follow-up

The application files now live in `backend/` and `frontend/`. Python configuration, lockfile, runtime, API tests, contract exporter, and controlled provider server belong to `backend/`. Expo source is in `frontend/src/`, with npm configuration/lockfile, browser tests, and the live smoke script under `frontend/`. Each directory owns its tool artifacts and ignore rules; shared project documentation remains at the root.

Current commands are documented in [README](../../README.md). From the repository root, use `uv run --directory backend pytest tests` for API tests and `npm --prefix frontend test` for the frontend build/browser tests. Generate contracts with `npm --prefix frontend run contract`.

Verification after relocation: all 25 API + 23 browser tests passed; TypeScript/Python typechecks, Ruff lint, and formatting checks passed. Both dependency lockfiles and generated API contract files retained identical contents. The relocated live smoke check passed: one provider attempt, one result, 180×180 portrait, browser cache reuse (`[594, 0]` transfer bytes), and content-free runtime logs. Paths and commands quoted in the original implementation review describe the pre-reorganization commit.

## Application name correction

The product is **Lumiere**. App display metadata and the frontend npm package now use `Lumiere` / `lumiere`. The backend Python package is `backend/lumiere/`, its project metadata is `lumiere-backend`, and logging uses `lumiere.operations`. Numeric configuration keys now use `LUMIERE_<SETTING>`; README commands and the server configuration template match. Existing planning-skill identifiers and quoted historical review details retain their original names.

Verification: all 25 API + 23 browser cases, typechecks, lint, and formatting checks passed. The generated web document title is `Lumiere`, configuration reads the new environment prefix, and contract generation is unchanged. The renamed runtime passed the live search/portrait/cache/log smoke check. Dependency versions and artifacts are unchanged.

## Ports and adapters refinement

Approved scope: centralize concrete adapter selection in startup, move provider-independent selection into the backend application operation, give the client workflow its own recognition model, and inject the frontend search port from startup. Starting commit: `48af2ab056c3cb3c1df44f17fe97ebbb81a1e9da`.

- `runtime.compose_api` selects TMDB and local admission adapters, binds the application search operation, and supplies operational counters. The FastAPI factory receives capabilities and uses the application-owned name validator before incoming admission. The operation also validates when called independently.
- `search.search_people` owns qualified-reference deduplication, provider-order retention, the seven-person limit, and the three-title limit. TMDB translation supplies all usable page-one candidates.
- Frontend `index.ts` supplies the HTTP adapter through `PeopleSearch`. Workflow and presentation use `search/model.ts`; the HTTP adapter alone validates and maps generated wire responses into that model.
- Public API tests first failed for injected composition and replacement-provider selection, then passed after the corresponding changes. Existing integration tests continue using the real TMDB adapter over a controlled external transport through shared startup composition.
- Full verification: 27 API + 27 browser tests passed; backend branch coverage is enabled and combined coverage is 85%. The search application module reports 100% coverage with branch tracking. Both typechecks, Ruff lint/format, ESLint, and Prettier checks passed. Contract regeneration produced no diff.
- Real-TMDB smoke passed through the new composition: one provider attempt and one result, the requested 180×180 portrait, browser cache reuse, and content-free runtime output. Public API fields, headers, and UI behavior remain as specified.
- [Two-axis review](architecture-review.md) complete: Standards 0 findings; Spec 0 findings. No unresolved issues.
