# Project architecture and development foundation

## Summary

Build the full product described in the proposal and wireframes through small, independently developed feature increments.

Use one repository containing an Expo frontend and an async Python backend. Apply ports and adapters to both. Begin with personal use and one seeded user, while keeping all user-owned data and application operations ready for multiple users.

| Area | Technology |
|---|---|
| Frontend | TypeScript, Expo, React Native Web; web first |
| Backend HTTP | FastAPI |
| Boundary validation | Pydantic |
| Persistence | Async SQLAlchemy, Postgres hosted on Neon |
| Schema migrations | Alembic |
| AI integration | Pydantic AI through the LLM gateway |
| Observability | Pydantic Logfire |
| Background work | Durable Postgres-backed queues |
| Semantic search | Implementation selected through a later investigation |

Clients initially require an internet connection. Mobile builds, authentication, hosting selection, and detailed feature behavior remain separate increments.

## Application boundaries and interfaces

**Backend**

- Keep domain types and application operations independent of FastAPI, SQLAlchemy, TMDB, and model SDKs.
- Define ports around capabilities: catalog persistence and metadata, user-owned records, identity, background work, and—when introduced—AI extraction and discovery.
- Implement TMDB as the first metadata adapter. Core interfaces and public contracts use application terminology and identities.
- Use Pydantic to validate HTTP payloads, external-provider responses, job payloads, and structured AI outputs. Keep persistence models inside database adapters.
- Use async I/O throughout application operations and adapters. Give each request or concurrent job its own database session, with short transactions around database work.
- Run the API and workers as separate entry points into the same application codebase. Assemble dependencies and configure Logfire at the composition roots.

**Frontend**

- Keep application behavior and ports in TypeScript modules independent of React, Expo, and browser APIs.
- Implement the UI, backend communication, and device capabilities as adapters.
- Share cross-platform components where useful; allow web/native variants for navigation, layout, and interactions.
- Use REST/JSON and OpenAPI for backend communication. Generate frontend wire types from the API schema; keep generated transport code outside the frontend core.
- Add abstractions as features need them, rather than scaffolding unused services or mobile implementations.

## Data ownership and catalog design

Maintain application UUIDs for entities. Store external identities separately, allowing one entity to have references from multiple sources.

| Record | Responsibility |
|---|---|
| **User** | Application identity, independent of the authentication mechanism. |
| **Person** | Shared name, portrait, and descriptive metadata. |
| **Movie** | Shared title, original title, release date, overview, poster, genres, runtime, and tagline as available. |
| **Credit** | Person/movie relationship, preserving acting characters and crew jobs, including multiple credits for one person. |
| **Source reference** | Maps an application entity to a source and external ID; records resource completeness and freshness. |
| **Follow** | Unique user/person relationship covering all that person’s movie roles. |
| **Watchlist** | Unique user/movie relationship with independent `seen` and `in_watchlist` choices. |

- Treat catalog metadata as shared, refreshable data. Follows and Watchlist entries are durable user-owned data.
- Fetching a search result must not automatically trigger a full metadata crawl.
- Support partial catalog records: movie summaries can be usable before details or additional credits arrive. Track completeness separately from individual missing field values.
- Derive the timeline from followed people’s credits and explicitly tracked movies. Deduplicate movies and retain the credits explaining their inclusion.
- Keep source identity and provenance separate from canonical catalog fields. Define reconciliation policies when another source is introduced.
- Treat imported titles as candidates until resolved against catalog records and reviewed. DVD ownership is not tracked.
- Initially resolve identity through a seeded-user adapter. User-scoped operations receive that identity rather than hardcoding a user or trusting a client-supplied user ID.

## Catalog processing and incremental development

Use local catalog data first for known entities. Use the metadata provider for discovery and missing resources, with queued enrichment and refresh.

- Execute interactive search promptly.
- Process person-filmography work, movie-detail work, and refresh work through independent queue lanes that can progress concurrently.
- Give person credits precedence over movie enrichment, and enrichment precedence over background refreshes. Coordinate shared provider request limits across lanes.
- Deduplicate outstanding work across users and recheck catalog completeness before fetching. Reuse existing movie data across overlapping filmographies.
- Make jobs recoverable after restarts and application operations safe to repeat. Record background failures in Logfire while preserving usable cached data.
- Introduce refresh scheduling behind the same boundaries; select cadence and retry tuning during catalog development.

Begin implementation with the repository structure, dependency wiring, migrations, identity adapter, and observability needed for the first feature. Develop an initial search-and-follow path through frontend, API, persistence, metadata, and background work.

Use the following as a flexible development order:

1. Search for and follow cast and crew.
2. Display their movies on the timeline.
3. Display and manage followed people.
4. Display the Watchlist.
5. Search movies and update seen/watchlist choices.
6. Extract movie candidates from pasted notes.

Authentication, photo extraction, semantic search, suggestions, and refinements can enter the sequence as appropriate. Define each feature’s detailed contracts, interaction behavior, and acceptance criteria when planning that feature.

Record the architecture decisions in repository documentation and align the proposal with them, including removing the fixed note-extraction-first sequence and treating model selection as an investigation outcome.

## Validation and deliberate deferrals

Validate the foundation with:

- Dependency checks showing that core modules do not import infrastructure or UI frameworks.
- Application tests using fake metadata, persistence, identity, and AI adapters where relevant.
- Postgres integration checks for migrations, source mappings, user isolation, uniqueness, and shared catalog reuse.
- Queue checks for deduplication, independent lane progress, and restart recovery.
- Contract checks between Pydantic/OpenAPI and generated frontend types.
- An end-to-end check of the first completed feature, plus Logfire verification across its API and background work.

Defer decisions that remain replaceable behind these boundaries: queue library, hosting provider, refresh intervals, pagination and live-update mechanics, import retention, frontend component library, AI models, embedding provider, and semantic-search implementation. Investigate pgvector in Neon as a candidate without committing to it now.

Detailed loading presentation, matching ambiguities, and error interactions belong to feature planning and prototypes. They do not block this architecture.
