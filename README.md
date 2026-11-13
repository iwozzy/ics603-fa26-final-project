# Lumiere

Search actors, directors, and other cast and crew by name. This first increment runs locally with an Expo / React Native for Web frontend and async Python backend. Search data stays transient; Movies and Follow are disabled placeholders.

## Repository layout

```text
backend/
  lumiere/                Python API, application logic, and TMDB adapter
  tests/                  API tests and controlled provider server for browser tests
  scripts/                API contract export
  pyproject.toml          Python dependencies and tool configuration
  uv.lock
  .python-version
  .env.example            Server-only configuration template
frontend/
  src/                    Expo entry point, search screen, workflow, and API contract
  tests/e2e/              Playwright browser tests
  scripts/                Live integration smoke check
  package.json            Frontend commands and dependencies
  package-lock.json
  app.json
  tsconfig.json
  playwright.config.ts
  eslint.config.cjs       Expo ESLint rules and complexity limit
  .prettierrc.json         Frontend formatting options
  .prettierignore          Generated files and build output excluded from formatting
docs/                     Shared architecture and design references
.scratch/                 Specs, issues, and verification evidence
```

Each application directory owns its dependency lockfile, tooling configuration, and generated runtime artifacts. Shared project documentation stays at the root. Commands below run from the repository root; within `frontend/`, use ordinary `npm` commands, and within `backend/`, use ordinary `uv` commands.

## Run locally

Prerequisites: Node.js 22.13+, 24.3+, or 26+ (tested with 26.13), npm, Python 3.13, uv, and a TMDB API read access token. Install the locked dependencies:

```sh
npm --prefix frontend ci
uv sync --directory backend --locked
```

Set the server-only token in your shell:

```sh
export TMDB_API_READ_ACCESS_TOKEN='your TMDB read access token'
npm --prefix frontend run build:web
uv run --directory backend uvicorn lumiere.runtime:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Alternatively, copy `backend/.env.example` to `backend/.env`, fill it in, and add `--env-file .env` after `uv run --directory backend` when starting the API. `.env` is ignored by Git. Never use an `EXPO_PUBLIC_` variable for provider credentials.

Open **http://127.0.0.1:8000**. The Python process serves both `frontend/dist/` and `/api/people/search`, so browser requests remain same-origin. Rebuild after frontend edits, then reload. No database, account, or cloud telemetry credentials are needed. Stop with Ctrl+C. Searches reset on reload.

For frontend hot reload, run `npm --prefix frontend run web` and the API separately, with a local same-origin reverse proxy forwarding `/api/` to port 8000. The exported workflow above is the supported reproducible local path and the path exercised by browser verification.

## Verify

Install Chromium once with `(cd frontend && npx playwright install chromium)`, then run:

```sh
npm --prefix frontend run format:check
npm --prefix frontend run lint
npm --prefix frontend run typecheck
uv run --directory backend ty check lumiere scripts tests
uv run --directory backend ruff check lumiere scripts tests
uv run --directory backend pytest tests
npm --prefix frontend test
```

Frontend linting uses the [Expo ESLint preset](https://docs.expo.dev/guides/using-eslint/) with `complexity: ['error', { max: 10 }]`. Run it with `npm --prefix frontend run lint`; source, tests, and scripts are checked, while generated API types and build/test output are excluded.

Frontend formatting uses [Prettier](https://prettier.io/docs/install) with single quotes and its other default options. Run `npm --prefix frontend run format` to format authored frontend files, or `npm --prefix frontend run format:check` to check without writing. Generated API contracts, the dependency lockfile, and build/test output are excluded. ESLint's Prettier compatibility config disables conflicting formatting rules.

The backend command runs the direct API tests. The frontend test command exports the web app and runs Chromium against the real application API using the controlled external TMDB server in `backend/tests/support/`. Browser tests need permission to open loopback listeners and launch Chromium. They do not require a real token or contact TMDB; image-fallback scenarios stub the image host.

Run an individual API file with `uv run --directory backend pytest tests/test_people_api.py`. Within `frontend/`, after exporting, use `npx playwright test tests/e2e/search.spec.ts` or `tests/e2e/presentation.spec.ts`.

Backend coverage is available through pytest-cov:

```sh
uv run --directory backend pytest tests --cov=lumiere --cov-branch --cov-report=term-missing
```

Branch coverage is enabled by default in the pytest configuration.

Regenerate the JSON Schema and TypeScript API types after editing `backend/lumiere/schemas.py`:

```sh
npm --prefix frontend run contract
```

The Python exporter in `backend/scripts/` writes `frontend/src/api.schema.json`; frontend tooling derives `frontend/src/api.generated.ts`. The frontend validates JSON at runtime with that same schema. Contract files are checked in; no generation step is needed to start the app.

With the token configured, this opt-in command performs one real TMDB search through the rendered screen, verifies a portrait decodes at the requested 180×180 transform, confirms browser HTTP-cache reuse, and checks actual runtime output excludes query/content/credentials:

```sh
npm --prefix frontend run build:web
npm --prefix frontend run smoke:live
```

To load the backend `.env` for the live check, use `uv run --directory backend --env-file .env node ../frontend/scripts/smoke-live.mjs`. It binds port 8767 and prints only counts and operational evidence. Deterministic tests use port 8765. See [implementation evidence](.scratch/search-people/implementation.md).

## Boundaries and local settings

`frontend/src/search/workflow.ts` owns draft/submission and request-generation rules independently of React or browser APIs. The HTTP adapter owns cancellation, deadlines, and runtime response validation. The rendered screen owns row reveal state. The API-specific Pydantic boundary is separate from application data and TMDB payloads. The backend capability port hides TMDB adaptation; runtime composition owns HTTP clients and logging. No catalog or identity records are created.

The API accepts `GET /api/people/search?query=...`. Success contains only `results`, with up to seven distinct usable page-one people in provider order. It permits `private, max-age=60` browser caching. Blank/oversized input, admission refusal, and upstream errors return status 500 with an empty body and `no-store`. No automatic retries or application query cache are used.

All numeric settings below are positive and configurable through `LUMIERE_<SETTING>` environment variables. Invalid configuration stops startup. Changing settings requires a restart.

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
