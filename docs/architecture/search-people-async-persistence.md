# People search: asynchronous persistence

Architecture of `feature/brainstorming/F002-follow-people` at `1bfb5ac`, compared
with `brainstorming` at `89f2a01`. Nodes marked **NEW** or **CHANGED** show the main
differences. Arrows show runtime calls or data flow; dashed arrows show background
persistence.

```mermaid
flowchart TB
    subgraph Browser["Browser · Expo / React"]
        UI["Search UI"]
        HTTP["CHANGED: API adapter + generated validation<br/>Retains provider identity"]
        Cache["Private browser HTTP cache"]
        UI --> HTTP --> Cache
    end

    Cache -->|"Cache miss"| Edge["Caddy"]

    subgraph Backend["FastAPI · single backend process"]
        API["GET /api/v1/people/search"]
        Guest["Guest identity + LRU cache"]
        Search["CHANGED: SearchPeople<br/>Select up to seven valid results"]
        Admission["In-memory quota admission"]
        Catalog["CHANGED: TMDB adapter<br/>Validate identity + normalize summaries"]
        Usage["Existing charge queue + usage writer"]

        subgraph Persistence["NEW: Best-effort people persistence"]
            Queue["Nonblocking enqueue<br/>1,024 queued + in-flight batches"]
            Writer["PeopleWriter dispatcher<br/>Up to ten concurrent batch tasks"]
            Repo["Fresh unit of work per attempt<br/>Deduplicate + sort by TMDB ID<br/>One bulk upsert + commit"]
            Queue -.-> Writer -.-> Repo
        end

        Edge --> API
        API --> Guest
        API --> Search
        Search -->|"Admit before provider call"| Admission
        Admission -.-> Usage
        Search --> Catalog
        Search -.->|"Offer selected summaries"| Queue
    end

    Catalog <-->|"First-page search"| TMDB["TMDB API"]

    subgraph Pools["NEW: Named pools · same database destination"]
        AppPool["application<br/>5 connections + 5 overflow"]
        PeoplePool["people_writer<br/>5 connections + 5 overflow"]
    end

    Guest --> AppPool
    Usage -.-> AppPool
    Repo -.-> PeoplePool

    subgraph Database["PostgreSQL"]
        Guests[("Existing guest tables")]
        Flush["NEW: lumiere_flush_charges<br/>One function call per usage batch"]
        Counters[("Existing usage counters + checkpoints")]
        People[("NEW: people<br/>App-owned ID · unique tmdb_id<br/>Normalized person summaries")]
        Flush --> Counters
    end

    AppPool --> Guests
    AppPool --> Flush
    PeoplePool --> People
```

Search returns without waiting for person writes. Saturation, exhausted retries,
crashes, or shutdown expiry can lose a batch without failing search. Fresh browser
cache hits bypass the backend and enqueue nothing. Search continues to use TMDB;
the people table is not a search source.

Each persistence attempt has a five-second timeout, with at most three attempts
and a one-second delay between failures. Shutdown allows a five-second drain
before cancelling and awaiting remaining work. Separate pools isolate connection
checkout capacity, while sharing database CPU, locks, and server resources.

The API now carries `provider`, `provider_id`, and `known_for_department`; the
frontend maps the latter two to `providerId` and `knownForDepartment`. Search does
not expose the app-owned person ID. Following remains future work.

Source: [search orchestration](../../backend/src/lumiere/application/use_cases/search_people.py),
[PeopleWriter](../../backend/src/lumiere/application/people_writer.py),
[people repository](../../backend/src/lumiere/adapters/outbound/persistence/people_repository.py),
and [composition wiring](../../backend/src/lumiere/bootstrap.py).
See the [approved design](../superpowers/specs/2026-11-20-search-people-persistence-design.md)
and [full search architecture](search-people.md) for additional context.
