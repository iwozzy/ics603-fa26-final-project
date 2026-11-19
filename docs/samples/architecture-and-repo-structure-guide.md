# architecture-and-repo-structure-guide

Machine-readable guide to repository structure and architectural rules.
Conventions: paths are repo-root-relative. Fenced `yaml` blocks are normative. Keywords MUST / MUST NOT / SHOULD follow RFC 2119.

## 1. Overview

```yaml
architecture: ports-and-adapters   # applies to backend and frontend
repo_type: monorepo
toolchains:
  backend: uv
  frontend: npm
  e2e: npm
npm_workspaces: false              # frontend/ and e2e/ are separate packages
contract: openapi.json             # sole coupling between backend and frontend
```

## 2. Stack

```yaml
backend:
  language: python>=3.13
  package_manager: uv
  web: [fastapi, pydantic]
  http_client: httpx
  db: [sqlalchemy-async, psycopg, alembic]
  database: postgres (neon)
  observability: logfire
  testing: [pytest, httpx.ASGITransport, httpx.MockTransport]
  architecture_enforcement: import-linter
frontend:
  language: typescript
  framework: [expo, react-native, react-native-web, expo-router]
  package_manager: npm
  validation: zod
  codegen: hey-api
  testing: [jest, jest-expo, react-native-testing-library]
  architecture_enforcement: [eslint-plugin-boundaries | dependency-cruiser]
e2e:
  tool: playwright
infra:
  containers: docker
  proxy: caddy
  orchestration_local: compose.yaml
```

## 3. Top-Level Layout

```
.
├── backend/                 # Python service (uv project)
├── frontend/                # Expo app: native + web (npm package)
├── e2e/                     # Playwright (own package.json)
├── deploy/caddy/Caddyfile   # cross-cutting deploy config
├── openapi.json             # committed API contract
├── compose.yaml             # postgres (local), backend, web, caddy
├── Makefile | justfile      # targets: dev, test, generate, lint, migrate
├── .env.example
├── .github/workflows/
└── README.md
```

Optional: `docs/` (ADRs), `AGENTS.md` / `CLAUDE.md` (agent instructions).

## 4. Dependency Rule (both sides)

```yaml
layers:            # inner -> outer
  - domain
  - application
  - adapters
  - bootstrap      # composition root; may import everything
allowed_imports:
  domain: []                              # nothing from project
  application: [domain]
  adapters: [application, domain]
  bootstrap: [domain, application, adapters]
forbidden_in_core:                        # applies to domain and application
  backend: [sqlalchemy, fastapi, httpx, pydantic, logfire]
  frontend: [react, react-native, expo-*, "**/generated/**"]
ports:
  backend: typing.Protocol
  frontend: typescript interface
adapters_inbound: [http routers, ui screens/hooks, expo-router routes, background workers]
adapters_outbound: [persistence, external API clients, storage]
```

## 5. Backend Structure

```
backend/
├── pyproject.toml
├── uv.lock
├── .python-version
├── Dockerfile                       # multi-stage; uv sync --frozen --no-dev
├── alembic.ini
├── migrations/                      # env.py imports metadata from persistence adapter
├── scripts/export_openapi.py        # writes ../openapi.json; builds app without real adapters
├── src/app/
│   ├── domain/                      # entities, value objects, domain errors (pure Python)
│   ├── application/
│   │   ├── ports/                   # repositories, unit_of_work, gateways
│   │   └── use_cases/
│   ├── adapters/
│   │   ├── inbound/http/
│   │   │   ├── routers/v1/
│   │   │   ├── schemas/             # Pydantic DTOs (source of OpenAPI)
│   │   │   ├── deps.py
│   │   │   └── errors.py            # domain/app errors -> HTTP status
│   │   └── outbound/
│   │       ├── persistence/         # models.py, repositories.py, unit_of_work.py, session.py
│   │       └── clients/<vendor>_<capability>/   # client.py, dto.py, mapper.py
│   ├── bootstrap.py                 # composition root
│   ├── config.py                    # pydantic-settings
│   ├── observability.py             # logfire setup (outside core)
│   └── main.py                      # FastAPI factory + lifespan
└── tests/
    ├── unit/domain/
    ├── unit/application/            # use cases against fakes
    ├── fakes/                       # in-memory repos and gateways
    ├── integration/persistence/     # real Postgres
    ├── integration/clients/         # httpx.MockTransport
    └── api/                         # ASGITransport, full app
```

Backend rules:

```yaml
- Domain entities are frozen dataclasses or plain classes, not Pydantic or SQLAlchemy models.
- Pydantic DTOs live only in adapters/inbound/http/schemas and vendor dto.py files.
- SQLAlchemy models live only in adapters/outbound/persistence.
- Use cases own transaction boundaries via a UnitOfWork port; adapters never commit on their own.
- Do not hold a DB transaction open across an external API call.
- One long-lived httpx.AsyncClient per base URL, created in bootstrap, closed in lifespan.
- Logfire instruments FastAPI, SQLAlchemy and HTTPX from observability.py; use cases may use a Tracer port.
- Neon: app uses pooled connection string; Alembic uses direct connection string (two env vars).
- SQLAlchemy URL scheme: postgresql+psycopg://
- With multiple bounded contexts, nest as app/<context>/{domain,application,adapters}.
```

## 6. Frontend Structure

```
frontend/
├── package.json
├── package-lock.json
├── app.json
├── tsconfig.json
├── jest.config.js                   # jest-expo preset
├── openapi-ts.config.ts             # Hey API config; input ../openapi.json
├── Dockerfile                       # optional: expo export -p web
└── src/
    ├── app/                         # Expo Router routes only; thin, import screens from adapters/inbound/ui
    ├── domain/                      # pure TS types and rules
    ├── application/
    │   ├── ports/                   # interfaces (repositories, storage, clock)
    │   └── use-cases/               # plain functions/factories taking ports
    ├── adapters/
    │   ├── inbound/ui/              # screens, components, hooks
    │   └── outbound/
    │       ├── api/
    │       │   ├── generated/       # Hey API output; only importable from this folder's siblings
    │       │   ├── mappers.ts       # DTO -> domain
    │       │   └── *-repository.ts  # implements ports
    │       └── storage/             # secure-store / async-storage adapters
    ├── bootstrap/
    │   ├── container.ts             # builds adapters, binds use cases
    │   └── Providers.tsx            # context exposing use cases to UI
    └── test-utils/
        ├── fakes/
        └── renderWithPorts.tsx
```

Frontend rules:

```yaml
- src/app/ contains only routes; every non-route file lives elsewhere.
- Generated Hey API code is imported only by adapters/outbound/api.
- API adapters Zod-validate responses, then map DTO -> domain.
- Use cases contain no React; UI reaches them through Providers context.
- Debounce, loading state and stale-result handling belong to inbound UI hooks, not use cases.
- Ports that perform I/O accept an AbortSignal for cancellation.
- Tests are colocated as *.test.ts(x) next to the code they cover.
- The frontend never references external vendors; it only calls this repo's backend.
```

## 7. Contract Flow

```yaml
pipeline:
  - FastAPI app (adapters/inbound/http/schemas + routers)
  - backend/scripts/export_openapi.py
  - openapi.json                      # committed; API changes visible in PR diffs
  - Hey API (frontend/openapi-ts.config.ts)
  - frontend/src/adapters/outbound/api/generated/   # types, SDK, Zod schemas
ci_checks:
  - regenerate openapi.json and fail on git diff (spec drift)
  - regenerate client and fail on diff if generated code is committed
generated_code_policy: gitignore and generate in prebuild/CI   # committing is an acceptable alternative
```

## 8. External API Integration Pattern

```yaml
rule: if a capability can be described without naming the vendor, it is a port
backend:
  port: application/ports/<capability>.py       # defined in domain language
  adapter: adapters/outbound/clients/<vendor>_<capability>/
  adapter_responsibilities: [auth, timeouts, retries, backoff, vendor DTO validation, vendor DTO -> domain mapping, exception translation]
  use_case_responsibilities: [orchestration, caching, fan-out, fallback policy, quotas, history persistence]
  errors: adapters raise application-level errors; inbound http/errors.py maps to 429/502/503/504
  caching: SearchCache-style port, or decorator implementing the same gateway port
frontend:
  port: <Capability>Repository                  # talks to own backend only
  swap_vendor_requires_client_release: false
variants:
  fast_request_response: plain endpoint
  progressive_results: port returns AsyncIterator; HTTP adapter exposes SSE
  long_running: job resource (POST creates, GET polls) + worker as inbound adapter + job repository port
```

## 9. Deployment Topology

```yaml
origin: same-origin
caddy:
  serves: static Expo web export (frontend dist/)
  proxies: /api/* -> backend
cors_config_required: false
compose_stack: [postgres (local only), backend, web/caddy]
e2e_target: compose stack (same topology as production)
docker:
  backend: multi-stage, uv sync --frozen --no-dev
  web: node stage runs expo export; copy dist/ into caddy image
```

## 10. Testing Matrix

```yaml
backend:
  unit_domain: {location: tests/unit/domain, needs: nothing}
  unit_application: {location: tests/unit/application, needs: fakes}
  integration_persistence: {location: tests/integration/persistence, needs: postgres}
  integration_clients: {location: tests/integration/clients, needs: httpx.MockTransport + fixtures}
  api: {location: tests/api, needs: ASGITransport, gateways overridden with fakes}
frontend:
  unit: {targets: [domain, use-cases], needs: fakes}
  component: {tool: RNTL, helper: renderWithPorts, needs: fake ports}
  adapter: {targets: adapters/outbound/api, needs: stubbed fetch}
e2e:
  tool: playwright
  location: e2e/tests
  external_vendors: stubbed; never hit real vendor APIs
  scope: browser flows only; API-level tests stay in backend/tests/api
optional_smoke: periodic real-vendor smoke test outside the main CI path
```

## 11. CI and Tooling

```yaml
orchestration: Makefile|justfile with targets [dev, test, generate, lint, migrate]
ci:
  path_filtered_jobs: [backend, frontend, e2e]
  required_jobs:
    - import-linter (backend layer contracts)
    - boundaries lint (frontend layer rules)
    - openapi spec-drift check
    - backend unit tiers (no containers)
    - backend integration tiers (postgres service or Neon branch)
neon_branch_per_pr: recommended
```

## 12. Known Trade-offs and Escape Hatches

```yaml
- Two mappings per entity (backend entity <-> DTO, frontend DTO <-> domain) is the accepted cost of the architecture.
- Pragmatic exception: read-only queries MAY return DTO-shaped read models straight from a port; writes and rule-bearing logic keep full mapping.
- Revisit npm workspaces only if shared TS packages are introduced.
```

## 13. Open Questions (unresolved)

```yaml
- team_size: unknown   # affects CI and deploy layout
- native_builds_eas: unknown   # affects frontend Dockerfile and CI
- generated_client_committed: undecided   # default is gitignored
```
