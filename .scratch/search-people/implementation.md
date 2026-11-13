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
