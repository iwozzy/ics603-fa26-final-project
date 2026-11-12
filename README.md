# Lumiere

People search for movie enthusiasts, implemented as the read-only
[F001 slice](docs/features/F001-search-people/F001-search-people.md) of the approved
[architecture](docs/ARCHITECTURE.md). Expo Router serves the web screen; an async
FastAPI backend searches the first TMDB people page and returns up to seven display
summaries. There is no database, following behavior, identity, history, or background work.
Submitting an empty or whitespace-only draft restores the initial examples without a
request; overlong drafts preserve the current display. Typing alone does not submit.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Node.js 26
with npm 11, and Make. `frontend/.node-version` records the Node.js version;
select it with your version manager from `frontend/`. Python 3.13 is selected by
`backend/.python-version`; uv can install it automatically.

```sh
make setup
cd frontend
npx --no-install playwright install chromium
cd ..
```

On Linux, Playwright may also need system packages: use
`npx --no-install playwright install --with-deps chromium` from `frontend`.
Both dependency lockfiles are tracked. Preserve the uv dependency-age policy;
use `uv --directory backend add` for Python dependencies and `npm install` inside
`frontend` for JavaScript. Use `EXPO_NO_DOTENV=1 npx expo install <package>` for
SDK-managed dependencies.

## Run locally

For live searches, supply the TMDB API Read Access Token as `LUMIERE_TMDB_TOKEN` in
the backend process environment through your existing secure configuration.
From the repository root, run these in separate terminals:

```sh
make api
```

```sh
make web
```

Open <http://localhost:8081>. The API runs at <http://127.0.0.1:8000>.
The API starts without provider configuration; searches then use the generic
failure contract. Stop each process with Ctrl-C.

For a complete local workflow without provider access, replace `make api` with:

```sh
make fixture-api
```

This uses a test-only composition root, separate from the production entry point.
Most names return the repository's canned Tom-search results. `Empty` returns no
people, `Failure` simulates an upstream failure, `Unusable` returns only malformed
records, `Long` supplies long strings, and `Latest` returns a distinct result.
`Slow success` and `Slow failure` wait until released explicitly. Telemetry export
is always off in this fixture server. See the
[manual verification workflow](docs/features/F001-search-people/IMPLEMENTATION.md#manual-verification).

## API

```sh
curl --fail http://127.0.0.1:8000/health
curl --get --data-urlencode 'query=Tom' http://127.0.0.1:8000/api/people/search
```

`GET /api/people/search` requires `query`, trimmed to 1–100 Unicode code points.
Internal spaces, punctuation, case, and accents are preserved. Successful responses
are `{"results": [...]}` with zero to seven summaries, each containing `name`,
`portrait_url`, `department`, and `known_for`. Summaries have no identifiers,
following state, or pagination metadata. Successful responses use
`Cache-Control: private, max-age=60`.

As explicitly specified for F001, invalid input and search failures both return
HTTP 500, `Cache-Control: no-store`, and:

```json
{"code":"SEARCH_FAILED","message":"Unable to complete search."}
```

Invalid input makes no provider call. Each valid request makes one first-page
provider search with a ten-second total deadline, without retries, detail calls,
or enrichment. The frontend operation has a twelve-second deadline covering both
fetching and response-body decoding. API documentation is at
<http://127.0.0.1:8000/docs>; its schema is at
<http://127.0.0.1:8000/openapi.json>.

## Configuration and observability

Set configuration through process environment variables. Settings never load a
configuration file. Expo scripts disable automatic environment-file loading,
CLI telemetry, and network lookups; its SDK check uses the installed SDK's
bundled compatibility matrix.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LUMIERE_TMDB_TOKEN` | Unset | Backend-only TMDB API Read Access Token for live searches. |
| `LUMIERE_LOG_LEVEL` | `INFO` | Standard Python log level. |
| `LUMIERE_CORS_ORIGINS` | `["http://localhost:8081","http://127.0.0.1:8081"]` | JSON array of allowed browser origins. |
| `LUMIERE_TELEMETRY_ENABLED` | `false` | Opt in to Logfire export using existing process configuration. |
| `EXPO_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Public backend base URL; restart/rebuild Expo after changing it. |

The composition root owns a shared async HTTP client, configures standard logging,
and creates Logfire request spans. Provider spans are their children and record
outcomes, durations, result counts, and skipped records. Raw queries, payloads,
URLs, and exception messages are excluded from application logs and spans.
HTTPX's routine URL logs and Uvicorn access logs are disabled. Browser failures use
`console.info` so Expo development mode does not show a LogBox notification.

Export is off in ordinary tests and CI. Local exporter tests verify correlation
and privacy without a network. The explicit remote smoke check is:

```sh
make smoke-logfire
```

It requires existing Logfire export configuration in the process environment and
uses a mocked provider, so it needs no live TMDB access. It submits a trace and
prints its ID. Verify that `HTTP request` and `TMDB people search` appear in that
trace under service `lumiere-api` in Logfire. A successful flush alone does not
prove remote receipt. This session could not verify export because process export
configuration was unavailable.

## Checks

With ports 8000 and 8081 free:

```sh
make check
```

This checks lockfiles and installed dependencies, Ruff lint/formatting (including
complexity ≤10), Pyrefly, Python import boundaries, pytest coverage, Expo SDK
compatibility, ESLint, negative dependency-boundary probes, Prettier, TypeScript,
jest-expo/React Native Testing Library, generated-type drift, the production web
build, and Playwright. Browser tests start real Expo/FastAPI servers with a
fixture-backed metadata adapter and stub external images. No ordinary check needs
provider access or telemetry export. GitHub Actions runs the same command on pushes
and pull requests.

```sh
make check-backend
make check-frontend
make test-e2e
uv --directory backend run --locked ruff format .
npm --prefix frontend run format
make api-types
npm --prefix frontend run api:check
```

Type generation creates an application instance without starting its lifespan,
exporting telemetry, or contacting the provider. Generated wire types remain in
the HTTP adapter. See [implementation evidence and acceptance review](docs/features/F001-search-people/IMPLEMENTATION.md)
for the incremental RED/GREEN record, limitations, and manual verification.

The existing dependency lockfile reports npm audit findings inherited through
the Expo/Jest toolchain. Compatible audit fixes were applied in the foundation;
the remaining proposed fix forces older major Expo/Jest versions and was deferred.
This feature adds no npm dependencies.

## Source layout

```text
backend/
  src/lumiere/
    bootstrap.py            Composition, client lifetime, request tracing
    config.py               Process environment configuration
    domain/people.py        Plain display summary
    application/search_people.py  Operation and metadata port
    adapters/http/          Health/search routes and Pydantic wire models
    adapters/tmdb.py        Provider validation, normalization, deadline, tracing
  tests/                    Application, adapter, HTTP, boundary, tracing tests
    fixture_app.py          Browser/manual fixture composition root
  scripts/                  Offline OpenAPI export and opt-in tracing smoke check
frontend/
  src/app/                  Thin Expo routes and root layout
  src/application/          Framework-independent controller, summaries, search port
  src/adapters/http/        Fetch/deadline adapter and generated OpenAPI types
  src/adapters/ui/          gluestack components, theme provider, search screen
  tests/                    Controller, HTTP adapter, component, route tests
  e2e/                      Fixture-backed browser workflows
Makefile                    Setup, runtime, checks, fixtures, type generation
```
