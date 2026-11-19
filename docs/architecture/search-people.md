# F001 people-search architecture

Implemented architecture of `feature/brainstorming/F001-search-people` at
`d779554`, compared with `main` at `7a468ca`. This describes the code at that
snapshot, including the later guest-identity and asynchronous-accounting changes.

## Compact component diagram

```mermaid
flowchart TD
    UI["Expo / React UI"] --> HTTP["HTTP adapters + browser cache"]
    HTTP --> Caddy["Caddy"]
    Caddy --> API["FastAPI routes"]

    subgraph Backend["Single backend process"]
        API --> Guests["Guest identity + LRU cache"]
        API --> Search["SearchPeople use case"]
        Search --> Admission["In-memory quota admission"]
        Admission --> Queue["Bounded charge queue"]
        Queue -.-> Writer["Background usage writer"]
        Search --> Adapter["TMDB adapter"]
    end

    Guests -->|"Bootstrap / cache miss"| DB[("PostgreSQL")]
    Writer -.->|"Persist charges + checkpoints"| DB
    DB -.->|"Startup usage snapshot"| Admission
    Adapter --> TMDB["TMDB API"]
```

## Detailed component overview

Arrows show runtime calls or data flow, rather than source-code imports. Dashed
arrows show background persistence, lifecycle work, or build-time generation.

```mermaid
flowchart TB
    subgraph browser["Browser — Expo / React Native Web"]
        UI["SearchPeopleScreen + useSearchPeople<br/>Submit, loading, cancellation, results"]
        FE["SearchPeople use case<br/>Normalize query"]
        HTTP["HTTP repository adapters<br/>Ensure guest identity, fetch, validate and map"]
        CACHE["Private HTTP response cache<br/>Configurable max-age; default 300 seconds"]
        UI --> FE --> HTTP
        HTTP --> CACHE
    end

    EDGE["Caddy<br/>Serves exported web app; proxies /api/* and /health/*"]
    CACHE -->|"Cache miss: same-origin HTTP"| EDGE
    EDGE --> API

    subgraph backend["FastAPI backend — one process / replica"]
        API["HTTP routers + failure boundary<br/>POST /api/v1/guest-session<br/>GET /api/v1/people/search<br/>7-second response deadline"]
        GUEST["GuestIdentityService<br/>Durable profile and cookie resolution"]
        LRU["GuestIdentityCache<br/>10,000-entry LRU; no TTL"]
        SEARCH["SearchPeople use case<br/>Normalize, admit, dispatch, select up to 7 people"]
        ADMIT["UsageAdmissionService<br/>In-memory minute, daily and total limits<br/>Global / guest / IP scopes"]
        QUEUE["Bounded in-process queue<br/>Up to 1,024 outstanding charges"]
        WRITER["One background async task<br/>Batches up to 64; retry with checkpoint"]
        UOW["UnitOfWork port → PostgreSQL adapter<br/>SQLAlchemy + psycopg"]
        CATALOG["PeopleCatalog port → TMDB adapter<br/>HTTPX + DTO validation and mapping"]

        API -->|"Resolve identity before search"| GUEST
        GUEST --> LRU
        GUEST -->|"Bootstrap or cache miss"| UOW
        API --> SEARCH
        SEARCH -->|"Charge before provider I/O"| ADMIT
        ADMIT --> QUEUE
        QUEUE -.-> WRITER
        WRITER -.->|"Flush daily / total charges"| UOW
        UOW -.->|"Startup snapshot and committed counts"| ADMIT
        SEARCH --> CATALOG
    end

    DB[("PostgreSQL<br/>guest_profiles + guest_credentials<br/>usage_counters + usage_flush_checkpoints")]
    TMDB["TMDB API<br/>GET /3/search/person; first page"]
    UOW --> DB
    CATALOG --> TMDB

    CONTRACT["Root openapi.json"]
    CONTRACT -.->|"Generate TypeScript + Zod transport definitions"| HTTP
```

The browser can satisfy a fresh cached search without reaching Caddy or the
backend. A successful backend response sets `Cache-Control: private` with the
configured lifetime, including for empty results. Bootstrap and error responses
use `no-store`. There is no backend search-result cache.

## Search request sequence

The sequence below assumes the browser needs a network response. The writer runs
independently and may flush while TMDB is still responding.

```mermaid
sequenceDiagram
    actor User
    participant Web as Browser UI + HTTP adapters
    participant API as Caddy / FastAPI
    participant Guest as GuestIdentityService + LRU
    participant Search as SearchPeople
    participant Usage as UsageAdmissionService
    participant Writer as Background writer
    participant DB as PostgreSQL
    participant TMDB as TMDB adapter / API

    Note over Usage,DB: At startup: load current UTC day and total counters before serving
    User->>Web: Submit a name
    Web->>Web: Normalize query#59; cancel superseded search
    opt Guest bootstrap needed by HTTP adapter
        Web->>API: POST /api/v1/guest-session
        API->>Guest: Bootstrap existing or new identity
        Guest->>Guest: Check per-IP bootstrap minute limit
        Guest->>DB: Find or create durable profile / credential#59; commit
        Guest->>Guest: Populate LRU after successful transaction
        API-->>Web: Set / renew HttpOnly cookie#59; no-store
    end
    Web->>API: GET /api/v1/people/search?query=...
    API->>Guest: Resolve cookie to profile + current IP key
    alt Valid identity in LRU
        Guest-->>API: GuestContext
    else LRU miss
        Guest->>DB: Look up credential digest
        DB-->>Guest: Stored identity, if valid
        Guest->>Guest: Cache valid identity
        Guest-->>API: GuestContext, or fail request
    end
    API->>Search: Execute normalized query with GuestContext
    Search->>Usage: Admit and charge
    Usage->>Usage: Check readiness and all caps#59; charge locally#59; enqueue
    Usage-->>Search: Admitted without database I/O
    par Provider request
        Search->>TMDB: Search first page
        TMDB-->>Search: Valid mapped people in provider order
        Search-->>API: Up to seven people
        API-->>Web: JSON + private cache header
        Web-->>User: Results, or blank state for empty result / failure
    and Asynchronous accounting
        Writer->>Usage: Consume queued charges in batches
        Writer->>DB: Add daily / total deltas + batch checkpoint#59; commit
        DB-->>Writer: Committed counter values
        Writer->>Usage: Reconcile confirmed counts#59; retain newer pending charges
    end
```

## Boundaries and operating constraints

- Both frontend and backend use ports and adapters. Application code imports
  domain types and defines ports; adapters implement those ports. The composition
  roots wire concrete adapters to use cases. React, FastAPI, HTTPX, SQLAlchemy and
  generated transport types stay outside the cores.
- The committed OpenAPI document is the frontend/backend contract. Generated
  TypeScript and Zod definitions are consumed only inside frontend API adapters.
- Guest credentials map to durable profile IDs. The cookie has a renewable
  365-day browser lifetime; server-side credentials have no expiry. Cached
  identities remain until LRU eviction or process restart.
- Search admission checks all nine global/guest/IP minute, daily and total caps
  in one event-loop turn. Daily and total usage equals confirmed database counts
  plus pending local charges. Minute counters stay in memory and reset on restart.
- Admission queues the charge before calling TMDB. Provider errors and cancelled
  searches retain that charge. No request-owned database transaction spans the
  provider call. A warm identity cache removes database reads from this path too.
- The writer retries the same writer ID and batch sequence after persistence
  failures. Counter updates and checkpoints commit together, making retries
  idempotent. A full backlog or unavailable writer rejects new admission.
- Strict quotas require one backend process/replica. A crash or a shutdown that
  exceeds the five-second drain can lose unflushed charges. The queue and minute
  limits are process-local.
- The browser adapter has an eight-second deadline; the HTTP response boundary
  has seven seconds; the TMDB adapter has five seconds. Bootstrap shares one
  in-flight operation across callers.
- Optional Logfire-compatible telemetry wraps services, HTTP and database
  boundaries. It is disabled by default and does not participate in quota
  decisions. Liveness and readiness routes make no TMDB calls; readiness checks
  writer capacity and database connectivity.

## Code map

| Responsibility | Source |
| --- | --- |
| Browser state and cancellation | [useSearchPeople.ts](../../frontend/src/adapters/inbound/ui/useSearchPeople.ts) |
| Frontend composition | [container.ts](../../frontend/src/bootstrap/container.ts) |
| API requests and guest bootstrap | [API adapters](../../frontend/src/adapters/outbound/api/) |
| Backend composition and lifecycle | [bootstrap.py](../../backend/src/lumiere/bootstrap.py) |
| HTTP endpoints and cache headers | [v1 routers](../../backend/src/lumiere/adapters/inbound/http/routers/v1/) |
| Search orchestration | [search_people.py](../../backend/src/lumiere/application/use_cases/search_people.py) |
| Durable identity and cache | [guest_identity.py](../../backend/src/lumiere/application/use_cases/guest_identity.py), [guest_cache.py](../../backend/src/lumiere/application/guest_cache.py) |
| Admission, queue and background writer | [usage_admission.py](../../backend/src/lumiere/application/use_cases/usage_admission.py) |
| Provider integration | [TMDB client](../../backend/src/lumiere/adapters/outbound/clients/tmdb_people/client.py) |
| Durable counters and batch checkpoints | [repositories.py](../../backend/src/lumiere/adapters/outbound/persistence/repositories.py), [models.py](../../backend/src/lumiere/adapters/outbound/persistence/models.py) |
| Same-origin serving and proxy | [Caddyfile](../../deploy/caddy/Caddyfile) |
| API contract | [openapi.json](../../openapi.json) |
