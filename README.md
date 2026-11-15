# Lumiere

Search for actors, directors, and creative contributors. Submit with Enter or the search icon; typing never sends a request. Search returns up to seven valid people from the provider’s first page in provider order, with up to three movie/TV recognition titles.

## Local setup

Use Python 3.13+, uv 0.13.7+, Node 24+, npm, Docker Compose with named build contexts, and a running Docker engine. The three projects have independent lockfiles; there is no root npm workspace.

```sh
uv --directory backend sync --frozen
npm --prefix frontend ci
npm --prefix e2e ci
make test
make lint
make generate
git diff --exit-code -- openapi.json frontend/src/adapters/outbound/api/generated
```

`make test` needs no containers or external services. `make test-integration` starts and removes an isolated loopback Postgres 18 instance; it uses a fixed disposable test database, never the application connection. `make test-e2e` builds the real backend/web-Caddy stack with isolated Postgres and a fixture HTTP provider. `make test-cache-expiry` runs a separate browser check with a 10-second cache lifetime, confirms immediate reuse, then waits 12 real seconds to check expiry. Its test-only override does not change the normal browser suite's 300-second lifetime. These checks do not verify native releases, hosted deployment, or live provider behavior.

For application runtime, supply the variable names documented by the placeholder-only `.env.example` through your process environment. Application-owned names use the `LUMIERE_` prefix; unprefixed application names are no longer accepted. Tool-defined `OTEL_*`, `POSTGRES_*`, and `EXPO_*` names retain their standard spelling. Commands do not load an existing environment file. Set every positive request/daily/cumulative cap before live provider dispatch. Use a pooled `postgresql+psycopg://` application connection in `LUMIERE_DATABASE_URL` and a direct connection in `LUMIERE_MIGRATION_DATABASE_URL`. Run `make migrate` explicitly before starting the application. Startup does not migrate.

`make dev` builds and starts the backend plus one combined static-web/Caddy service at `http://localhost:8080`. Neon is the deployment database. For a local database, start `docker compose --env-file /dev/null --profile local-db up -d postgres`, then supply the appropriate local connection through the environment. Local database authentication is isolated to the development network and loopback port. Local profile data persists until the operator removes its volume.

Configure `LUMIERE_TRUSTED_PROXY_CIDRS` as a JSON array of only the actual ingress network CIDRs. Caddy sanitizes forwarded client metadata; the backend ignores forwarding headers from other peers. Keep `LUMIERE_IP_HASH_KEY` stable across restarts. Guest sessions have a 24-hour server expiry, opaque HttpOnly same-site cookies, and no persistent browser-cookie expiry. The current request’s normalized IP always supplies the quota context.

The supplied ingress listens on HTTP locally. For deployment, give Caddy a domain in `LUMIERE_SITE_ADDRESS` (Compose passes it to Caddy as `SITE_ADDRESS`) and expose its HTTPS/HTTP ports in your infrastructure, or put an HTTPS ingress in front. HTTP/2 terminates at ingress and falls back to HTTP/1.1 upstream. Hosting/publishing is an operator step outside this change.

## HTTP contract and storage

`POST /api/v1/guest-session` bootstraps or reuses a guest session and responds with an empty `200`, `Cache-Control: no-store`, and a cookie only when needed. Cross-origin mutations are rejected. Search sends only the required `query` parameter to the provider; no hidden retry, next page, sorting, or deduplication is performed.

`GET /api/v1/people/search?query=...` trims the query and accepts 1–200 Unicode code points. A `200`, including an empty result, has `Cache-Control: private, max-age=<seconds>`, no cookie rotation, and no `Vary: Cookie`. Set `LUMIERE_SEARCH_CACHE_MAX_AGE_SECONDS` to a positive integer to configure the lifetime; the default is 300 seconds, and values above 10,000 seconds are supported. For example, `LUMIERE_SEARCH_CACHE_MAX_AGE_SECONDS=14400` permits four hours of browser caching. Every search failure returns an empty `500` with `Cache-Control: no-store`. The UI silently clears results on failure or empty success. Only the latest submission can update the screen; clearing or unmounting invalidates pending work.

Browser HTTP caching uses the normal transport policy. It may reuse the exact successful GET across guest-cookie changes. There is no application, server, or proxy search cache, result persistence, or service worker. Only guest profiles/session digests, usage counters, and reservations are stored. Provider attempts are reserved atomically before I/O; dispatched failures and uncertain/crashed reservations stay charged. Cumulative caps survive UTC daily rollover and restarts. No database transaction spans provider I/O. The HTTP response has a seven-second deadline even while a dependency cleans up cancellation. Cancellation settlement runs separately with a two-second bound; uncertain terminal markers keep the durable charge. Cancelled database units of work discard their connection so Postgres rolls back uncommitted changes without a network rollback acknowledgement.

## Architecture and diagnostics

The backend and frontend use domain → application → adapters → bootstrap dependency direction. Use cases own transaction boundaries through the UnitOfWork port. UI hooks own draft/loading/cancellation state. Only the API adapter subtree imports generated transport definitions. Root `openapi.json` is the contract; `make generate` exports it without runtime configuration and regenerates committed TypeScript/Zod definitions. The linters and mutation probes enforce the boundaries, including `_layout.tsx` as the sole route composition exception.

Telemetry is off by default and never authorizes usage. To enable it, set `LUMIERE_TELEMETRY_ENABLED=true` and supply `OTEL_EXPORTER_OTLP_ENDPOINT` and optional `OTEL_EXPORTER_OTLP_HEADERS` for your Logfire-compatible OTLP setup. Set `OTEL_RESOURCE_ATTRIBUTES="deployment.environment.name=local"` for local development or `"deployment.environment.name=prod"` for production. This labels exported telemetry for filtering; the endpoint and authorization select the destination/project. Compose passes these standard `OTEL_*` settings to the backend, where the SDK reads them directly. Explicit Logfire spans record correlation, latency, selected/invalid counts, quota outcomes, and finite failure categories at HTTP, SQLAlchemy, and HTTPX boundaries. They omit full queries, payloads, raw exceptions, headers/cookies, connection strings, SQL text, and parameters. FastAPI’s native telemetry is explicitly disabled so it cannot restore raw capture. No automatic framework/client instrumentation should be enabled over these exclusions. Export outages cannot block search.

Uvicorn access logging is disabled. Caddy access logging is off and its error-log filter removes request URIs and headers. Diagnose silent UI failures through `http.search`, `people.search`, `catalog.http`, `catalog.page`, and `database.query` spans and their status/category fields, never by turning on query-bearing access logs. `/health/live` and `/health/ready` make no provider calls; readiness checks the database only.
