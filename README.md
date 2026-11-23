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

Configure `LUMIERE_TRUSTED_PROXY_CIDRS` as a JSON array of only the actual ingress network CIDRs. Caddy sanitizes forwarded client metadata; the backend ignores forwarding headers from other peers. Keep `LUMIERE_IP_HASH_KEY` stable across restarts. Guest profiles and their opaque cookie credentials have no server expiry. Bootstrap sets an HttpOnly same-site cookie with a one-year `Max-Age` and renews its browser lifetime on every successful bootstrap, preserving the same cookie value and profile for a returning guest. Browsers can delete or limit cookies; losing the cookie creates a new guest identity without automatic recovery. The current request's normalized IP always supplies the quota context.

Validated guest identities are cached in memory per process, keyed by cookie digest and containing only profile identity. The cache has no TTL and defaults to a 10,000-entry LRU bound; hits update recency. Successful bootstrap warms the cache only after commit and transaction exit. Cache hits open no database transaction; misses, eviction and restarts use the authoritative database lookup. Bootstrap enforces an in-memory IP minute limit before accessing identity storage. Database credential deletion or mapping changes do not invalidate an already cached entry: it can remain accepted until eviction or restart, potentially indefinitely for an active guest. Warm validation and local search admission can survive a database outage until the accounting backlog fills. There is no shared invalidation or background cache refresh.

The supplied ingress listens on HTTP locally. For deployment, give Caddy a domain in `LUMIERE_SITE_ADDRESS` (Compose passes it to Caddy as `SITE_ADDRESS`) and expose its HTTPS/HTTP ports in your infrastructure, or put an HTTPS ingress in front. HTTP/2 terminates at ingress and falls back to HTTP/1.1 upstream. Hosting/publishing is an operator step outside this change.

## HTTP contract and storage

`POST /api/v1/guest-session` is retained as the compatible guest-identity bootstrap endpoint. It responds with an empty `200`, `Cache-Control: no-store`, and a persistent cookie on every success: new guests receive a fresh cookie, returning guests have the same cookie renewed with `Max-Age=31536000`. Cross-origin mutations are rejected. Search sends only the required `query` parameter to the provider; no hidden retry, next page, sorting, or deduplication is performed.

`GET /api/v1/people/search?query=...` trims the query and accepts 1–200 Unicode code points. A `200`, including an empty result, has `Cache-Control: private, max-age=<seconds>`, no cookie rotation, and no `Vary: Cookie`. Set `LUMIERE_SEARCH_CACHE_MAX_AGE_SECONDS` to a positive integer to configure the lifetime; the default is 300 seconds, and values above 10,000 seconds are supported. For example, `LUMIERE_SEARCH_CACHE_MAX_AGE_SECONDS=14400` permits four hours of browser caching. Every search failure returns an empty `500` with `Cache-Control: no-store`. The UI silently clears results on failure or empty success. Only the latest submission can update the screen; clearing or unmounting invalidates pending work.

Browser HTTP caching uses the normal transport policy. It may reuse the exact successful GET across guest-cookie changes. There is no application, server, or proxy search cache or service worker. Storage contains guest profiles/credential digests, usage counters, compact accounting retry checkpoints, and app-owned people summaries. Search responses retain `provider: "tmdb"` and safe-integer `provider_id`; `known_for_department` replaces `department`. Database person IDs and internal profile paths are excluded from responses.

Run one backend process/replica. Startup loads persisted daily and cumulative usage before serving searches. Before provider I/O, admission atomically checks and charges all nine global/guest/IP limits in memory and queues the six daily/total increments, with no accounting database call or wait in the request task. Guest counters use the durable profile ID; cookie renewal does not reset their budgets. Existing `LUMIERE_SESSION_*` configuration names still supply per-guest limits. Search and bootstrap minute limits are entirely local fixed UTC windows: they reset on restart, are never written to Postgres, and retain active counters rather than evicting them to admit more traffic. Each minute limiter holds at most 10,000 active keys and rejects new keys when full. Invalid searches and rejected admissions are uncharged; provider failure/cancellation retains an admitted charge.

One background async task wakes after each charge and writes queued daily/total increments in batches of up to 64, returning database counts. Reconciliation adds remaining pending local charges to the confirmed counts, preserving requests admitted during a flush. A compact checkpoint per process run makes retries after uncertain commits idempotent, without per-search history. At most 1,024 searches may await persistence, including the active batch; a full backlog rejects new searches as storage unavailable. Writes have a five-second timeout and retry after one second. Shutdown stops admission and allows five seconds to drain before cancelling the writer and disposing connections. These are constructor defaults, with no new environment settings.

Flushed cumulative counts survive restarts and daily rollover. A crash or timed-out shutdown can lose unflushed charges; this is an accepted tradeoff. Multiple processes/replicas can overspend shared allowances, so they are unsupported for strict quota enforcement. New searches may continue during a database outage until the bounded backlog fills. Day keys are captured at admission so delayed writes retain their original date; historical minute rows are no longer used. No request-owned transaction spans provider I/O; the independent writer may persist while a provider request is running.

Stop application writers and run `make migrate` through `0005_async_usage` before starting this backend version with one process/replica. The migrations rename sessions to credentials, remove the former 24-hour expiry, aggregate mapped session counters by profile, and add accounting retry checkpoints. Existing profiles, cookie mappings and usage counters are preserved, including credentials past their former expiry. Drain and stop the new writer before downgrading 0005, which drops only checkpoints. Earlier admission functions remain for migration compatibility and are not used by the running application.

Migration `0004_counter_only_admission` drops `usage_reservations` and its existing per-attempt history, preserving all usage counters. There is no provider-outcome accounting; outcomes remain available in diagnostic telemetry. Downgrading 0004 recreates the former table empty and restores its admission function, but cannot recover dropped history. Downgrading 0003 restores the older per-session policy with fresh 24-hour expiry, assigning each profile's aggregate usage to one deterministic credential to preserve recorded totals. The HTTP response retains its seven-second deadline even while a dependency cleans up cancellation. Cancelled database units of work discard their connection so Postgres rolls back uncommitted changes without a network rollback acknowledgement.

## Architecture and diagnostics

The backend and frontend use domain → application → adapters → bootstrap dependency direction. Use cases own transaction boundaries through the UnitOfWork port. UI hooks own draft/loading/cancellation state. Only the API adapter subtree imports generated transport definitions. Root `openapi.json` is the contract; `make generate` exports it without runtime configuration and regenerates committed TypeScript/Zod definitions. The linters and mutation probes enforce the boundaries, including `_layout.tsx` as the sole route composition exception.

Telemetry is off by default and never authorizes usage. To enable it, set `LUMIERE_TELEMETRY_ENABLED=true` and supply `OTEL_EXPORTER_OTLP_ENDPOINT` and optional `OTEL_EXPORTER_OTLP_HEADERS` for your Logfire-compatible OTLP setup. Set `OTEL_RESOURCE_ATTRIBUTES="deployment.environment.name=local"` for local development or `"deployment.environment.name=prod"` for production. This labels exported telemetry for filtering; the endpoint and authorization select the destination/project. Compose passes these standard `OTEL_*` settings to the backend, where the SDK reads them directly. Explicit Logfire spans record correlation, latency, selected/invalid counts, quota outcomes, and finite failure categories at HTTP, SQLAlchemy, and HTTPX boundaries. Database spans also record the executed SQL statement as `db.query.text`, retaining parameter placeholders without bound values. Use parameterized SQL so values stay out of statement text. Spans omit full request queries, payloads, raw exceptions, headers/cookies, connection strings, and SQL parameter values. FastAPI’s native telemetry is explicitly disabled so it cannot restore raw capture. No automatic framework/client instrumentation should be enabled over these exclusions. Export outages cannot block search.

Uvicorn access logging is disabled. Caddy access logging is off and its error-log filter removes request URIs and headers. Diagnose silent UI failures through `http.search`, `people.search`, `catalog.http`, `catalog.page`, and `database.query` spans and their status/category fields, never by turning on query-bearing access logs. `/health/live` and `/health/ready` make no provider calls; readiness checks the database only.

### Person persistence (2026-11-20)

Search offers only its selected nonempty batch of up to seven normalized summaries
to an in-memory best-effort queue and returns without waiting for storage. Response
order and duplicates are preserved. Persistence keeps the first occurrence of each
TMDB ID and sorts IDs for one atomic bulk upsert; repeat writes preserve app-owned
IDs and replace all summary fields, including clearing optional values. Migration
`0007_people` adds `people` with the approved UUID-derived 40-bit bigint default.

The adapter-owned pool registry assigns guest identity, accounting, readiness, and following
to `application`, and people writes to `people_writer`. Each pool has five retained
connections plus five overflow, for at most twenty checkouts per backend process.
This isolates checkout capacity; both pools still share database resources.

The people dispatcher bounds queued plus in-flight work to 1,024 batches, with at
most ten incomplete batch tasks and fresh transactions for every attempt. Each
attempt times out after five seconds, retries at most three times with one-second
async delays, and retains its slot during retries. Full, stopped or unavailable
queues drop incoming batches without failing search. A five-second shutdown drain
runs alongside accounting cleanup; remaining work is cancelled and awaited before
both pools are disposed. Crashes, shutdown timeout and exhausted retries can lose
summaries. People writer health does not gate readiness or admission. Browser-cache
hits enqueue nothing. F002 follows require an existing stored person; a missing row returns an empty `500` and restores the client action.

Before stable V1, coordinated breaking contract changes are acceptable. Search URLs
contain only `query`; response compatibility and cache versioning are deferred.
After a breaking change, users may need to clear their browser cache and reload
the app to discard an old cached response. Revisit compatibility and cache
transition handling before publishing stable V1.

Sanitized `people.persistence` spans expose event kind, outstanding/in-flight
counts, attempt and integer duration milliseconds without person content. See the
[approved design](docs/superpowers/specs/2026-11-20-search-people-persistence-design.md).

### Following people (2026-11-23)

The persistent navigation offers Search (`/`) and Following (`/following`) even when empty. Hover or focus a search row to reveal `Follow +`; touch reveals on the first completed tap and saves on the next visible-button tap. Outside touch dismisses the action without blocking controls. Keyboard actions have a focus border and support Enter/Space. `Following` is status only; Unfollow and Movies are not offered. Leaving Search clears its query/results and cancels search work while pending follows continue above navigation.

`GET /api/v1/following` returns `{"people":[],"limit":3}` for an empty profile. `POST /api/v1/following` accepts only `{"provider":"tmdb","provider_id":4139}` and returns the full snapshot using search's six summary fields. Both have `Cache-Control: no-store`, empty `500` failures, and no provider usage. Bootstrap now also returns `X-Lumiere-Guest-Created: true|false`; a newly created guest clears obsolete client follows and queued work.

Migration `0008_follows` adds `follows` with guest/person foreign keys and a composite primary key. Async transactions use the `application` pool, lock the guest profile before membership/count checks, and commit before success. The named guest policy caps unique follows at three, including simultaneous requests; repeating a follow succeeds at the cap without changing its timestamp. Lists join current stored summaries in `followed_at DESC, person_id DESC` order. No person is created or updated by following.

The shared client store counts unique pending plus saved identities toward three and hides remaining actions immediately. Save failure rolls back optimism without an automatic retry or list read, even after an ambiguous commit; the user can retry manually. Ordinary route/foreground reads refresh stored state and retain confirmed rows on refresh failure. Initial Following loading, failure, and empty success leave its content blank without an activity indicator. Search responses remain independently browser-cacheable with following status overlaid locally.

Follow-time hydration, details/credits, timeline, authentication, and account prompts remain deferred. See [following architecture](docs/architecture/follow-people.md) and the [approved F002 design](docs/superpowers/specs/2026-11-23-F002-follow-people-design.md).
