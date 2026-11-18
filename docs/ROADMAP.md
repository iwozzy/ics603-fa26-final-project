# Core discovery implementation roadmap

## 1. Summary

Preserve the architecture in [ARCHITECTURE.md](ARCHITECTURE.md). Its main choices—ports and adapters, shared catalog data, application UUIDs, user-scoped operations, and durable background work—fit the product.

The repository currently contains design artifacts and Python development tooling, with no application implementation. Begin with **people search**, then saved follows, a compact timeline, and following management.

People search is the smallest useful feature. It validates frontend/backend boundaries, TMDB integration, and generated API types. The later timeline milestone completes the architecture validation by introducing durable workers.

The detailed roadmap ends at the core discovery loop. AI features, movie tracking, and richer presentation remain subsequent increments.


## 2. Incremental milestones and acceptance criteria

Each feature milestone includes its UI, API, application operation, adapters, and relevant tests. Introduce infrastructure within the milestone that first needs it.

| Milestone | Deliverable | Acceptance criterion |
|---|---|---|
| **M0 — Align the implementation brief** | Write the 001-people-search specification; establish development instructions and repository conventions. | Identify people search as the first increment, record its interaction and error behavior. No application implementation is required for this milestone. |
| **M1 — Search for people** | An Expo web screen submits a name through FastAPI to TMDB. Show names, portraits or fallbacks, department hints, and available known-for hints. | A user can submit a query or example search, inspect results, and perform additional searches. Fixture-backed tests cover no matches, missing portraits, mixed movie/TV hints, provider failure, and an older response arriving after a newer query. Search creates no follows or enrichment jobs. |
| **M2 — Save follows from search** | Add follow controls and persisted followed state. Introduce the seeded identity adapter and user-scoped operations. | Following a person survives reload and backend restart. Repeating or concurrently submitting the operation creates one relationship. A failed save preserves the previous confirmed state and permits retry. Tests with two injected identities demonstrate independent follows over shared person records. |
| **M3 — Show followed people’s movies** | Add the durable worker, person-filmography processing, and a compact timeline. Include existing follows created during M2. | Follow two people with overlapping movie credits: their movies appear in the chosen chronological order, each movie appears once, and its inclusion retains all relevant followed-person roles. Restart the API and worker during processing: committed follows remain and unfinished work recovers without duplicate movies or credits. Provider failure preserves cached movies and remains distinguishable from a successfully empty filmography. |
| **M4 — Manage followed people** | Add a Following screen with persisted state, processing status, and unfollow controls. Recompute timeline membership from current follows. | Unfollowing removes the Watchlist record and not the Movie records. Shared catalog records and other users’ follows remain intact. Unfollowing during an active job does not recreate the relationship or restore its movies to that user’s timeline. Changes survive restart. |

**M1 is the first useful feature. M3 is the first complete demonstration of the core architecture.**

Before implementing M3, complete plan the queue implementation and get sign off.

Defaults for the compact timeline:

- Newest release date first, matching the wireframe; undated movies are not shown.
- Stable ordering for equal dates.
- Title, release date, available poster/overview, and followed-person credit explanations.
- Simple pagination and explicit reload initially.
- Full cast, runtime, genres, year navigation, and live updates arrive later.

Retain every returned person regardless of whether their known-for credits are movies or TV. Mixed known-for titles serve as identification hints; they do not create TV catalog records or timeline entries.

## 3. Infrastructure and interface timing

| When needed | Foundation to introduce |
|---|---|
| **M1: people search** | Minimal Python and Expo structure; composition roots; configuration validation; HTTP adapters; OpenAPI type generation; basic Logfire request/provider tracing; CI. |
| **M2: saved follows** | User and Follow persistence, Person and source-reference persistence, async database and Alembic, seeded identity resolution, user-scoped repository operations, isolation tests, and a reproducible Postgres test database. |
| **M3: timeline** | Movie/Credit persistence, resource completeness, durable queue and worker entry point, atomic scheduling, shared provider throttling, retry/recovery behavior, and API-to-job trace correlation. |
| **Later increments** | Independent movie-detail and refresh lanes when those jobs exist; scheduled refreshes; Watchlist/seen state; AI extraction and gateway budgets; photo storage; embeddings; suggestions; authentication; mobile builds; hosting selection; richer UI and push updates. |

Create ports only as these capabilities appear. Give each API request and background job its own database session. Use short transactions for database work, and end them before calling TMDB or other external services.

Public contracts should expose:

- Normalized display summaries.
- Idempotent follow/unfollow operations and current-user following queries.
- Timeline movies with inclusion explanations and understandable processing status.
- A consistent distinction between invalid input, provider failure, and persistence failure.

Clients never choose the acting user through a submitted user ID. Generate TypeScript wire types from OpenAPI and translate them at the frontend boundary.

## 4. Repository conventions, AGENTS.md, and validation

Keep the root Python project and add a separate frontend directory. Use a Python `src` layout, dedicated tests and migrations, and feature specifications alongside the existing F001 artifacts. Avoid additional monorepo tooling initially.

Use small feature branches and reviewable changes. Each feature brief should record user behavior, exclusions, contracts, failure behavior, and acceptance examples. Record architectural departures in short decision records and update affected documents in the same change.

Expand [AGENTS.md](../AGENTS.md) with these instructions:

- Preserve the existing Security & Configuration section verbatim.
- Read the architecture and relevant feature specification before implementation; report material conflicts.
- Implement the requested increment and introduce abstractions when its behavior requires them.
- Keep domain/application modules independent of frameworks, provider SDKs, database models, and UI code.
- Use application identities; resolve user identity through the identity port.
- Keep transactions short and sessions private to requests/jobs.
- Add migrations for schema changes; preserve already-applied migrations.
- Regenerate API types when contracts change; never manually edit generated output.
- Keep ordinary tests independent of live providers; make live smoke checks explicit.
- Report changes, validation results, and remaining limitations.

Retain `uv`, Ruff, Pyrefly, pytest, the existing complexity limit, and the dependency-age policy. Use npm with a committed lockfile for the frontend. Document exact setup, migration, API, frontend, and worker commands when those entry points exist.

The shared completion checks are:

- Python lint, formatting checks, type checks, and relevant pytest suites pass.
- Frontend lint, type checks, and relevant tests pass.
- OpenAPI generation produces no unexplained contract drift.
- Postgres integration tests verify migrations, uniqueness, concurrency, and user isolation as applicable.
- Dependency checks enforce the architectural boundaries.
- A browser test covers each milestone’s primary user journey and a meaningful failure.
- Logfire visibility is verified when each runtime path is introduced; routine tests remain independent of telemetry export.

No fixed deadline or early AI demonstration is assumed. After M4, plan movie search/tracking and reviewed note import separately; retain photo extraction, suggestions, and semantic search as investigation-gated work.
