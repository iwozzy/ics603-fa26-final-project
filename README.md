# Lumiere

Minimal local foundation for [F001](docs/features/F001-search-people/F001-search-people.md),
following the approved [architecture](docs/ARCHITECTURE.md). The API exposes liveness
and OpenAPI; Expo Router serves a neutral startup screen at `/`. People search is not implemented.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Node.js 26
with npm 11, and Make. `frontend/.node-version` records the Node.js version;
select it with your version manager from `frontend/` before running setup.
Python 3.13 is selected by `backend/.python-version`; uv can install it
automatically. From the repository root:

```sh
make setup
cd frontend
npx --no-install playwright install chromium
cd ..
```

On Linux, Playwright may also need system packages: use
`npx --no-install playwright install --with-deps chromium` from `frontend`.
Both dependency lockfiles are tracked. Keep the existing uv dependency-age policy;
use `uv --directory backend add` for Python dependencies and `npm install` inside
`frontend` for JavaScript. Python dependencies and the virtual environment live in
`backend/`; JavaScript dependencies live in `frontend/`.
Use `EXPO_NO_DOTENV=1 npx expo install <package>` for SDK-managed dependencies.

## Run locally

In separate terminals, from the repository root:

```sh
make api
```

```sh
make web
```

Open <http://localhost:8081>. The API runs at <http://127.0.0.1:8000>:

```sh
curl --fail http://127.0.0.1:8000/health
# {"status":"ok"}
```

API documentation is at <http://127.0.0.1:8000/docs> and its schema is at
<http://127.0.0.1:8000/openapi.json>. Health checks only process liveness.
Stop each process with Ctrl-C. No external account or service is needed.

## Configuration and logging

Set configuration through process environment variables. Settings never load a
configuration file; Expo scripts explicitly disable automatic environment-file
loading. Nothing needs to be copied or created before startup.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_LOG_LEVEL` | `INFO` | Standard Python log level. |
| `APP_CORS_ORIGINS` | `["http://localhost:8081","http://127.0.0.1:8081"]` | JSON array of allowed browser origins. |
| `APP_TELEMETRY_ENABLED` | `false` | Explicit opt-in to Logfire export using an already configured process environment. |

For example:

```sh
APP_LOG_LEVEL=DEBUG make api
```

The composition root configures standard logging and local Logfire request spans.
Request logs record method, status, and duration. Unexpected failures return HTTP
500 with `INTERNAL_ERROR` and a generic message; logs record the exception type.
Raw URLs, queries, payloads, and exception messages are excluded. Uvicorn access
logging is disabled. Export is off in ordinary development, tests, and CI.
Expo CLI telemetry and network lookups are disabled in the project scripts; its
SDK check uses the installed SDK's bundled compatibility matrix.
An exported-tracing smoke check requires separate external setup and is deferred
to F001, when provider spans exist.

## Checks

With ports 8000 and 8081 free, run everything:

```sh
make check
```

This checks the Python lockfile and installed dependencies, Ruff lint/formatting
(including complexity ≤10), Pyrefly, import boundaries, pytest coverage, Expo SDK
compatibility, ESLint, Prettier, TypeScript, jest-expo/React Native Testing Library,
generated API type drift, the production web build, and Playwright startup.
Playwright starts and stops both servers and verifies health, browser rendering,
and narrow viewport overflow. It needs no provider or telemetry export.
GitHub Actions runs the same checks on pushes and pull requests.

The lockfile installation currently reports 29 npm audit findings (1 low,
28 moderate), inherited through the Expo/Jest toolchain. Compatible audit fixes
have been applied. npm's remaining proposed fix forces older major versions of
Expo and Jest, so it has not been applied. The configured checks pass; npm audit
is not clean. Recheck upstream fixes before updating dependencies.

Run subsets or formatting directly:

```sh
make check-backend
make check-frontend
make test-e2e
uv --directory backend run --locked ruff format .
npm --prefix frontend run format
```

Regenerate frontend wire types after changing an HTTP contract:

```sh
make api-types
npm --prefix frontend run api:check
```

Generation creates an application instance without starting its lifespan, exporting
telemetry, or making network requests. Generated types remain inside the HTTP adapter.

## Source layout and scope

```text
backend/
  pyproject.toml        Python dependencies and tool configuration
  uv.lock               Python dependency lockfile
  .python-version       Python version selection
  src/lumiere/
    bootstrap.py        API composition root and observability
    config.py           Process environment settings
    domain/             Domain types as features introduce them
    application/        Operations and ports as features introduce them
    adapters/http/      FastAPI routes and Pydantic HTTP models
  tests/                Backend tests
  scripts/              Offline OpenAPI export
frontend/
  .node-version         Node.js version selection
  src/app/_layout.tsx   Expo Router root layout, global styles, and navigation
  src/app/index.tsx     Startup route at /
  src/application/      Framework-independent feature code will live here
  src/adapters/ui/      React Native UI
  src/adapters/http/generated/  OpenAPI wire types
  tests/                Component tests
  e2e/                  Browser startup check
Makefile                Root commands coordinating backend and frontend
```

Python import contracts and frontend restricted-import rules protect core modules
from framework and adapter dependencies. The core has no feature implementation yet.
Expo Router discovers routes in `frontend/src/app/`; keep route modules thin and
compose screen components from `src/adapters/ui/`. The root layout is the frontend
composition root for shared providers and navigation. Tests live outside the route
directory. Typed route declarations are generated under the ignored `.expo/` directory.
UniWind/Tailwind provide the startup styling. gluestack packages are installed;
copy only the UI components required when F001 is implemented into the UI adapter.
No provider adapters, search endpoints, controllers, database, migrations, identity,
queues, workers, AI integrations, or deployment resources are introduced. The
architecture remains unchanged; F001's narrower foundation scope governs deferrals.
