# Wayfinder

Search actors, directors, and other cast and crew by name. This first increment runs locally with an Expo / React Native for Web client and async Python API. Search data stays transient; Movies and Follow are disabled placeholders.

## Run locally

Prerequisites: Node.js 22.13+, 24.3+, or 26+ (tested with 26.13), npm, Python 3.13, uv, and a TMDB API read access token. Install the locked dependencies:

```sh
npm ci
uv sync --locked
```

Set the token in your shell. You can also copy `.env.example` to `.env`, fill it in, and start with `uv run --env-file .env uvicorn wayfinder.runtime:create_app --factory --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log`. `.env` is ignored by Git. Never use an `EXPO_PUBLIC_` variable for provider credentials.

```sh
export TMDB_API_READ_ACCESS_TOKEN='your TMDB read access token'
npm run build:web
npm run api
```

Open **http://127.0.0.1:8000**. The Python process serves both the exported web app and `/api/people/search`, so browser requests remain same-origin. Rebuild after client edits, then reload. No database, account, or cloud telemetry credentials are needed. Stop with Ctrl+C. Searches reset on reload.

For client hot reload, run `npm run web` and the API separately, with a local same-origin reverse proxy forwarding `/api/` to port 8000. The exported workflow above is the supported reproducible local path and the path exercised by browser verification.

## Verify

```sh
npx playwright install chromium
npm run typecheck
npm run check:python
npm test
```

`npm test` runs direct API tests, exports the web client, and runs Chromium against the real application API with a controlled external TMDB transport. Browser tests need permission to open loopback listeners and launch Chromium. They do not require a real token or contact TMDB; image-fallback scenarios stub the image host.

Run an individual slice with `uv run pytest backend/tests/test_people_api.py` or, after exporting, `npx playwright test tests/e2e/search.spec.ts` / `tests/e2e/presentation.spec.ts`.

Regenerate the JSON Schema and TypeScript API types after editing the API-specific Pydantic schemas:

```sh
npm run contract
```

The client validates JSON at runtime with the same generated schema. Regenerate twice and compare with Git to check reproducibility. Contract files are checked in; no generation step is needed to start the app.

With the token configured, this opt-in command performs one real TMDB search through the rendered screen, verifies a portrait decodes at the requested 180×180 transform, confirms browser HTTP-cache reuse, and checks actual runtime output excludes query/content/credentials:

```sh
npm run build:web
npm run smoke:live
```

The live check requires the token in the environment (or run `uv run --env-file .env node scripts/smoke-live.mjs`). It binds port 8767 and prints only counts and operational evidence. Deterministic tests use port 8765. See [implementation evidence](.scratch/search-people/implementation.md).

## Boundaries and local settings

`client/search/workflow.ts` owns draft/submission and request-generation rules independently of React or browser APIs. The HTTP adapter owns cancellation, deadlines, and runtime response validation. The rendered screen owns row reveal state. The API-specific Pydantic boundary is separate from application data and TMDB payloads. The backend capability port hides TMDB adaptation; runtime composition owns HTTP clients and logging. No catalog or identity records are created.

The API accepts `GET /api/people/search?query=...`. Success contains only `results`, with up to seven distinct usable page-one people in provider order. It permits `private, max-age=60` browser caching. Blank/oversized input, admission refusal, and upstream errors return status 500 with an empty body and `no-store`. No automatic retries or application query cache are used.

All numeric settings below are positive and configurable through `WAYFINDER_<SETTING>` environment variables. Invalid configuration stops startup. Changing settings requires a restart.

| Setting | Default | Meaning |
| --- | --- | --- |
| `PROVIDER_TIMEOUT` | 5 seconds | Total upstream deadline, including reading the response |
| `OPERATION_TIMEOUT` | 6 seconds | Backend operation deadline; must exceed provider deadline and be at most 7 seconds |
| `MAX_QUERY_CHARS` | 200 | Trimmed Unicode code points |
| `MAX_TARGET_BYTES` | 4096 | Encoded raw path and query string |
| `MAX_PROVIDER_BYTES` | 1048576 | Decoded upstream response bytes |
| `INCOMING_CONCURRENCY` | 8 | Searches admitted at once |
| `OUTGOING_CONCURRENCY` | 4 | Upstream calls admitted at once |
| `ADMISSIONS_PER_MINUTE` | 60 | Rolling minute admissions in each direction |
| `ADMISSION_TOTAL` | 1000 | Cumulative admissions in each direction until process restart |

The browser waits at most eight seconds. Admission refusals are immediate. Incoming and outgoing budgets are independent; denied calls make no upstream attempt. Local accounting is single-process and intentionally resets on restart. Run one Uvicorn worker, on loopback. Never expose this local configuration publicly without the separate release work below.

Only allowlisted JSON operation events are logged: outcome, elapsed milliseconds, incoming admissions, and provider-attempt totals. HTTP client logging and Uvicorn access logging are disabled to prevent query-string capture. No automatic telemetry export or request-content instrumentation is enabled.

## Public delivery remains separate

Public hosting and native releases are outside this increment. Before public exposure, resolve and verify durable global accounting across processes/restarts, operator quota controls and approximation tolerances, HTTPS/HTTP/2, telemetry access/retention, TMDB attribution/terms and operating cost feasibility. The local in-memory allowance and successful smoke check do not establish release readiness.

Implementation references: [feature spec](.scratch/search-people/spec.md), [architecture](docs/adr/0001-app-architecture.md), [Expo web setup](https://docs.expo.dev/workflow/web/), [Expo SDK 58](https://docs.expo.dev/versions/latest/).
