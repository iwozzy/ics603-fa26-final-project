# F003 — Timeline

Date: 2026-11-25

Status: Approved by the project owner on 2026-11-26, including the numeric-ID and `as_of` clarifications. Implementation planning follows this approval.

## Intent and scope

Help a guest discover movies through people they follow by scrolling one combined, distinct, newest-first filmography. Start at the present; scrolling upward explores upcoming movies and scrolling downward explores released movies. Preserve the reading position across navigation within the loaded application.

This is a full feature spanning catalog storage, asynchronous hydration, an authenticated timeline query, and the universal client. Keep the existing ports-and-adapters architecture, existing responsibilities, and OpenAPI contract workflow. This document approves the design; implementation follows a separately reviewed implementation plan.

Inputs:

- [Timeline wireframe](../../samples/wireframes/F003-timeline-screen-wireframe.png).
- [Person details and movie credits fixture](../../samples/api/tmdb/v3/people/details_movie_credits.json).
- [Illustrative hydration SQL](../../samples/queries/movie-hydration-transaction.sql).
- [Generic pagination guide](../../samples/guides/timeline-pagination-high-level-design-guide.md), used selectively.
- [Repository architecture guide](../../samples/guides/architecture-and-repo-structure-guide.md), [application architecture](2026-11-09-application-architecture-design.md), and [implemented Following architecture](../../architecture/follow-people.md).

### Goals

- Persist shared movies and cast/crew credits; hydrate a person's filmography after a valid follow request.
- Keep follow completion independent of hydration, including whether the follow transaction commits.
- Read only locally available catalog data for people the resolved guest currently follows.
- Return each movie once, regardless of how many followed people or credits match.
- Deliver bounded, bidirectional keyset pagination and anchored refresh.
- Keep Timeline navigation permanently visible and retain loaded data and position across route changes.
- Refresh on route entry or full reload. Hydration completion does not automatically update the displayed window.

### Non-goals and anti-goals

No search, filters, ruler/jump controls, movie detail navigation, watched/watch-list actions, totals, numbered pages, refresh button, polling, push updates, automatic hydration scanner, existing-follow backfill, durable job system, TanStack Query, or new list dependency. Native release/polish remains outside this web increment; keep platform-specific behavior in UI adapters.

Avoid blocking follow requests on provider work, retaining database transactions across provider calls, duplicate movie rows, scroll jumps during prepend/refresh, replaying all cached pages on return, and introducing framework dependencies into either core.

## Decisions and approaches

The owner explicitly retained ports, use cases, and persistence adapters, excluded TanStack Query, and selected the first refresh approach below:

1. **Selected: retain pages and refresh around the visible movie.** An app-level Timeline store preserves loaded pages and a date/ID anchor. Route return shows cached data immediately and requests one bounded neighborhood around the anchor. If that movie disappears, land near the same release date. This keeps return work independent of how far the user previously scrolled.
2. **Considered: refetch every loaded page on return.** Updates a larger cached range, but request count grows with browsing history and concurrent changes complicate scroll restoration. Not selected.

The owner also selected a shared hydration dispatch cooldown on provider `429`: at least one minute, extended by a valid longer `Retry-After`. Already dispatched requests may finish.

### Architecture amendments and guide adaptations

These are explicit changes or limits of applicability; other architecture decisions remain in force:

| Source direction | F003 treatment |
| --- | --- |
| Generic thin backend with SQLAlchemy query logic near the route | Inapplicable. Routes validate/map; application use cases orchestrate through ports; PostgreSQL queries remain in persistence adapters. Core records are framework-free dataclasses. |
| Generic timestamp ordering | Use PostgreSQL `date` and `(release_date, id)`. Define the initial boundary from one database clock read in UTC; all releases dated today belong to the past side. UTC is a design call for review. |
| Generic `(scope_id, timestamp, id)` index | Movies are shared rather than profile-owned. Use a movie ordering index plus follow/credit eligibility indexes. One movie ordering index serves both scan directions; membership filtering has additional cost. Do not promise constant query cost across every guest's catalog density. |
| Generic asyncpg guidance | Keep the repository's async SQLAlchemy/psycopg stack. |
| Generic TanStack Query cache | Use a framework-free app-level store, consistent with Following. No dependency addition. |
| Generic HMAC-signed cursors and `400` errors | Design call: strictly validated, versioned, URL-safe base64 JSON cursors without signing; all queries independently enforce guest scope. Cursor edits can only change navigation within the caller's own timeline. Use the established empty `500`, `no-store` failure convention. No automatic error-recovery request loop. |
| Generic automatic refresh, optimistic timeline patches, freshness timer | Refresh the visible window on route entry only. Follow/unfollow does not patch an open timeline; its next entry reads committed membership. No focus/foreground polling. |
| Generic Now divider | Keep server `as_of` for the initial boundary, but add no visible divider absent from the supplied wireframe. |
| Older architecture: separately deployed hydration worker and durable execution bookkeeping | For F003 use a bounded, best-effort asyncio pipeline inside the existing backend process, following PeopleWriter. No durable work records or scanner yet. |
| Older architecture: commit follow and hydration intent together | Superseded for F003: enqueue independently before following storage work, after request validation and guest resolution. |
| Older architecture: expose incomplete hydration separately from empty results | F003 shows the currently available movies; initial loading/failure/empty can remain blank. |

## Data model

Use a new reversible Alembic migration. Preserve existing `people.id` generation and all existing people/follows data. New movie/credit IDs use `bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY` as requested.

### `movies`

| Field | PostgreSQL type and constraints |
| --- | --- |
| `id` | `bigint`, identity primary key |
| `tmdb_id` | `bigint NOT NULL UNIQUE`, positive |
| `title` | `text NOT NULL`, nonblank |
| `overview` | `text NULL` |
| `tmdb_poster_path` | `text NULL` |
| `release_date` | `date NOT NULL` |
| `tmdb_last_credits_hydration` | `timestamptz NULL DEFAULT NULL` |

Nullable poster paths are a design call: the supplied fixture contains missing posters, including for dated movies. Preserve those movies and render a fixed-size placeholder. Blank overviews normalize to null. Person-filmography hydration does not establish a movie's complete cast/crew; therefore it never advances `tmdb_last_credits_hydration`. A later movie-credits feature owns that timestamp.

### `credits`

| Field | PostgreSQL type and constraints |
| --- | --- |
| `id` | `bigint`, identity primary key |
| `tmdb_id` | `text NOT NULL UNIQUE`, nonblank provider credit ID |
| `movie_id` | `bigint NOT NULL REFERENCES movies(id)` |
| `person_id` | `bigint NOT NULL REFERENCES people(id)` |
| `credit_type` | `text NOT NULL CHECK (credit_type IN ('cast', 'crew'))` |
| `credit_character` | `text NULL` |
| `credit_order` | `integer NULL` |
| `credit_department` | `text NULL` |
| `credit_job` | `text NULL` |

Keep separate provider credits for multiple jobs/characters. There is no uniqueness constraint on `(movie_id, person_id)`; timeline deduplication operates on movies. Use default restrictive foreign keys; deletion/cascade policy is outside this feature.

### `people`

Add `tmdb_last_movies_hydration timestamptz NULL DEFAULT NULL`. Existing rows remain null. Advance it only in the transaction that successfully stores the complete accepted hydration result, including a successful empty filmography.

### Indexes

- `movies (release_date DESC, id DESC)` for the ordered scan in either direction.
- `credits (person_id, movie_id)` for followed-person membership lookup.
- `credits (movie_id, person_id)` for correlated eligibility probes.
- Existing `follows (profile_id, person_id)` primary key for profile scope.
- Unique provider-ID indexes created by the table constraints.

Validate eligibility/query plans with realistic sparse and overlapping filmographies; the index direction does not by itself eliminate membership-query cost.

## Hydration boundaries and lifecycle

### Enqueue

Extend `FollowPerson` with a nonblocking hydration-queue port. After identity validation and the existing HTTP origin/session checks, enqueue `(provider person identity, originating GuestContext)` before entering following storage work. Enqueue performs no provider or database I/O and cannot fail the follow request. Preserve existing following locking, cap, snapshot, commit, and empty failure semantics.

Consequences are intentional: a valid request can hydrate even if storage later fails, the person is missing locally, or the follow is rejected at the cap. Hydration does not repair/retry the failed follow; the user must retry it explicitly. Repeated idempotent follows also enqueue; freshness is checked by the worker. Invalid identity, origin, or guest requests do not enqueue. Unfollow never enqueues and does not cancel an already accepted hydration.

### Worker and ports

Use application queue/orchestration code analogous to PeopleWriter, a provider-neutral filmography gateway port, a hydration unit-of-work port, and a PostgreSQL adapter. Vendor DTO validation, response limits, `Retry-After` parsing, and mapping stay in the TMDB adapter. HTTP/SQLAlchemy/Pydantic types do not cross into the core. Add a named `movie_hydration` pool with **5 connections plus 5 overflow**, through the existing pool registry. Reads and writes for hydration use this pool; timeline reads use `application`.

Approved design defaults:

- At most 1,024 outstanding distinct people, including queued, active, delayed, and persistence-retry work. Queue entries are data; do not create an unbounded task per request.
- Coalesce queued/running work by provider/person identity; retain the first accepted requester's guest/IP context for charging. Later requests neither duplicate provider calls nor change the charge owner.
- At most ten active person jobs and ten provider requests in flight. Database operations and provider operations are async with fresh UoWs per transaction/attempt.
- Read the current timestamp before dispatch. Skip if it is within the preceding 24 hours; exactly 24 hours old is eligible. A missing row or null timestamp is eligible. A timestamp in the future is treated as fresh until that time plus 24 hours. Close the read transaction before provider I/O. Recheck freshness before any provider retry.
- Three provider attempts maximum per job. Transport timeouts, network errors, `5xx`, and `429` are retryable. Other `4xx`, identity mismatch, and invalid response structure are terminal. Ordinary retry delay is one second. Cooldown/rate/concurrency waiting is outside the provider attempt timeout.
- Provider request timeout: five seconds per attempt, matching the current client pattern. Design call: cap the decompressed filmography response at 10 MiB rather than reusing the search adapter's 1 MiB cap.
- Retain a successfully normalized payload across database retries: three persistence attempts, five-second timeout per attempt, one-second delay. A database retry does not repeat or recharge the provider request.
- Queue saturation, terminal errors, exhausted retries, accounting rejection, process loss, or shutdown expiry can discard work. Preserve existing catalog rows and leave the hydration timestamp unchanged. A later follow can retry; no scheduler automatically recovers it in F003.

The single-backend-process deployment assumption remains. Coalescing, provider rate/concurrency control, cooldown, and current quota admission are process-local; adding replicas requires separate coordination work.

### Accounting and dispatch gate

Use the **same existing UsageAdmissionService instance** as search. Every actual provider attempt is charged against its originating guest/IP and global daily/total allowances and the current minute limits; retries are separate attempts. Keep existing accounting keys and durable batching. Freshness skips, coalesced followers, local reads, timeline requests, database retries, and pre-dispatch rejections consume no provider allowance.

At dispatch, after the freshness read and outside any database transaction:

1. Await shared hydration cooldown, available in-flight capacity, and rate capacity.
2. Recheck those gates and shutdown state together immediately before dispatch.
3. Admit/charge through the shared accounting service and start the HTTP attempt without an intervening await that could permit another dispatch decision to overtake the gates.

The dispatcher must provide an atomic start/admission boundary using the existing service's non-yielding admission behavior; it must not charge a request merely parked behind a gate. An admitted request cancelled at the dispatch boundary retains its charge conservatively, consistent with existing accounting. Accounting rejection drops the hydration job without affecting follow completion or marking the person fresh.

Enforce **at most ten request starts in any rolling one-second window**, including retries, and **at most ten concurrent provider requests**. This limit applies to hydration; search retains its current request controls and shares the same allowance counters. Sleeping jobs do not occupy a checked-out database connection or an HTTP in-flight slot.

### Provider throttle cooldown

Any hydration `429` immediately extends a single monotonic dispatch deadline to the latest of its current value, receipt time plus 60 seconds, and receipt time plus any valid longer `Retry-After` delay. All hydration dispatch, including retries, waits for this deadline. Requests already in flight may finish and successful payloads may still persist. A later `429` can extend but never shorten the deadline, even when that response exhausts the job's attempt budget.

Accept nonnegative integer seconds and HTTP-date forms of `Retry-After`, as defined by [RFC 9110, section 10.2.3](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after). Convert HTTP dates relative to receipt-time UTC, then wait with a monotonic clock. Missing, malformed, negative, or past values add no delay beyond the one-minute minimum. Do not truncate a valid longer delay to an attempt timeout or an arbitrary short cap. Rate limiting still applies after cooldown, preventing a release burst.

This cooldown covers hydration dispatch; changing search's provider-response policy is outside F003.

### Startup and shutdown

Start accounting before accepting hydration. At shutdown stop accepting new hydration and allow up to five seconds for accepted work to dispatch and drain while honoring every gate. Then stop dispatch, cancel, and await remaining hydration tasks. Keep accounting and the shared HTTP client available until hydration has stopped; then drain accounting/PeopleWriter and close clients and every pool. Change the current concurrent shutdown ordering where necessary so hydration cannot charge after accounting closes. Cancellation rolls back open transactions; never publish freshness after a failed commit.

## Provider mapping and persistence

Request `GET /3/person/{tmdb_id}?append_to_response=movie_credits` through the long-lived TMDB-base-URL HTTP client. No hidden HTTP retry layer; the hydration pipeline owns retries. Verify the top-level returned person ID equals the requested provider ID before accepting data.

Normalize `movie_credits.cast` followed by `movie_credits.crew` into one array. Each entry retains the movie provider `id` and credit fields, plus `credit_type = 'cast' | 'crew'` and `person_id = response.id`. This JSON `person_id` is a **provider ID**, resolved to `people.id` in persistence; it is not inserted directly into `credits.person_id`.

Top-level `id`, `name`, and `known_for_department` map to the existing person. Movie `id`, `title`, `overview`, `poster_path`, and `release_date` map to the movie fields. Credit `credit_id`, `character`, `order`, `department`, and `job` map to the credit fields.

Drop entries with absent, blank, or invalid release dates before both movie and credit upserts. Validate required positive movie/person IDs, nonblank credit IDs/titles, and cast/crew shape. Reject structurally invalid responses rather than advancing freshness after losing arbitrary malformed credits. Optional strings normalize blank to null; absent/null order remains null, with non-integer supplied orders rejected. Normalize poster paths using the existing safe-path conventions. A successful response whose credits are all undated still advances person freshness.

Deduplicate movie rows by provider movie ID, deterministically retaining the first normalized occurrence (cast before crew). Deduplicate repeated identical credit IDs; conflicting identities for one credit ID fail the hydration. Distinct credit IDs for one movie/person remain distinct. Sort writes by provider IDs to keep lock acquisition consistent across concurrent people.

Deduplication applies separately to the two target tables; never deduplicate the combined credit array by movie ID. If one movie appears in both cast and crew, persist one movie and both credits, each with its own provider credit ID and `credit_type`. For example, an acting credit and a directing credit for the same person/movie share the local `movie_id` and `person_id` but remain separate credit rows. The timeline still returns that movie once.

One transaction, **one statement per table upserted**:

1. Upsert `people` by `tmdb_id`, including `name`, `known_for_department`, and `tmdb_last_movies_hydration = transaction time`. Preserve existing `known_for` and profile path on conflict; when inserting a previously missing person, use the existing empty known-for default and nullable profile path.
2. Bulk upsert deduplicated `movies` by `tmdb_id` from the normalized JSONB recordset. Update the mapped summary fields only; leave the complete-movie-credit timestamp untouched.
3. Bulk upsert `credits` by text `tmdb_id`, joining recordset movie/person provider IDs to the app-owned movie/person IDs. Update both FK identities and all five credit-detail/type fields, including department/job and transitions to null.

The application use case owns commit. Updating person freshness in statement 1 is safe because it becomes visible only with the entire successful commit. An empty accepted array still runs the person upsert; the movie/credit statements may be omitted as no-ops. No writes are committed per movie or credit.

The illustrative SQL is a pattern, not executable authority: qualify ambiguous person columns; include department/job; deduplicate conflict keys; and resolve provider IDs to local FKs. Folding the person timestamp into its upsert removes the sample's fourth statement.

Persistence is **upsert-only** in F003. Do not delete older credits absent from a later response or remove existing catalog movies whose release dates are now missing. Full reconciliation/removal is deferred; a removed provider credit may therefore continue qualifying a movie until that later feature.

## Timeline API and backend query

### Boundaries and contract

Add `GET /api/v1/timeline`, resolved through the existing guest session. It never calls the provider or schedules hydration. Use `Cache-Control: no-store` for success/failure, the existing seven-second server/eight-second transport deadlines, and empty `500` errors including validation and invalid cursors. These failure choices are design calls consistent with F001/F002, rather than importing the generic guide's `400` behavior.

Route → `ListTimeline` use case → timeline query/UoW port → PostgreSQL persistence adapter. The query returns a domain read model; the HTTP adapter maps it to Pydantic. A bounded cursor codec belongs behind an adapter-facing port; raw SQL and wire DTOs stay out of the core.

Parameters:

| Parameter | Contract |
| --- | --- |
| `limit` | Integer 1–100; default 20. Out-of-range values fail validation. |
| `cursor`, `direction` | Both required for paging; direction is `older` or `newer`. |
| `anchor_date`, `anchor_id` | Both required for anchored refresh; date is ISO `YYYY-MM-DD`, ID is a positive JavaScript-safe integer. Query parameters are text on the wire and validated as these types by the backend. |

Exactly one mode: no cursor/anchor/direction (initial); cursor plus direction (paging); or complete anchor pair (refresh). Reject combinations, incomplete pairs, and unknown parameters. Future date-only ruler anchoring is deferred.

Response example (tokens shown schematically):

```json
{
  "items": [
    {
      "id": 123,
      "title": "Bullet Train",
      "overview": "Movie overview",
      "poster_image_url": "https://image.tmdb.org/t/p/w500/example.jpg",
      "release_date": "2022-08-03"
    }
  ],
  "older_cursor": "opaque-token-or-null",
  "newer_cursor": "opaque-token-or-null",
  "as_of": "2026-11-25",
  "anchor_index": null
}
```

`id` is an app-owned movie ID serialized as a JSON integer and represented as a JavaScript number. The owner selected numeric IDs on the expectation that app-generated sequential IDs will remain JavaScript-safe. PostgreSQL bigint alone does not guarantee that property: require positive safe integers (`1..9007199254740991`) at the API and client validation boundaries to prevent silent rounding if that expectation ever fails. Keep the requested bigint identity column. `overview` and `poster_image_url` are nullable. `anchor_index` is null except on anchored refresh when an at-or-older item exists. All returned items use display order `(release_date DESC, id DESC)`.

`as_of` is the UTC calendar date establishing the current window's present boundary. Return it on initial and anchored responses; return null on cursor-paging responses, which do not establish a new boundary. On initial load, movies dated at or before `as_of` form the past side and those dated after it form the future side. The initial future-boundary cursor carries this same date. An anchored refresh establishes a new boundary date but centers the result on the saved movie, not on that date.

Obtain `as_of` within the same SQL statement that fetches the window, for example with a parameter CTE selecting `(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date`. Reuse that value for the initial predicates, availability probes, cursor construction, and returned metadata, including when no movies match. There is no separate clock query or database round trip. It is boundary metadata, not a snapshot timestamp or a freshness guarantee: later cursor requests continue from encoded sort keys, even after midnight, and do not use a new server date to move the boundary. No visible Now divider is introduced in F003.

The backend constructs poster URLs from the validated stored path and `https://image.tmdb.org/t/p/w500/`, with exactly one slash at the join. The frontend sees only the application's URL field and never constructs vendor URLs.

### Eligibility and pagination

Start from `movies` and use an `EXISTS` condition joining `credits` to `follows`, restricted to the resolved `profile_id`. This tests whether any followed person has any credit for the movie and cannot multiply movie rows. Never fetch a provider filmography during this query. Cast and crew qualify equally.

| Mode | Predicate and scan |
| --- | --- |
| Initial | `release_date <= today`, ordered descending, fetch `limit + 1`. |
| Older | `(release_date, id) < cursor pair`, ordered descending, fetch `limit + 1`. |
| Newer from row | `(release_date, id) > cursor pair`, ordered ascending, fetch `limit + 1`, then reverse kept rows. |
| Initial newer boundary | `release_date > initial as_of`, ordered ascending, fetch `limit + 1`, then reverse kept rows. This excludes all of today's movies without an artificial bigint sentinel. |
| Anchored | Inclusive older side `(release_date, id) <= anchor`, descending; exclusive newer side `> anchor`, ascending. Each fetches `limit + 1`; reverse kept newer rows and put them above the kept older rows. |

Anchored refresh returns up to `2 * limit` items, deliberately one page per side. `anchor_index` is the number of newer-side items when the older side is nonempty; otherwise null. If the anchor movie disappeared, this naturally identifies the nearest surviving at-or-older movie by sort key. The anchor is values, so deleting its original row is harmless.

Derive directional availability from the extra row in the scanned direction and a cheap `EXISTS` probe for any unscanned opposite side. Use one SQL statement/CTE snapshot per response, including initial/anchored `as_of` and availability probes. Null cursors mean no matching rows were available beyond that edge at query time. There are no separate clock queries, count queries, or long-lived snapshots across requests.

On the initial response, return a special future-boundary cursor when future movies exist, even if the past page is empty. Other nonempty pages carry row cursors from their first/last returned items only when more matching rows exist beyond that edge. The client takes only the newest cursor of its first page and oldest cursor of its last page. A paging response emptied by concurrent changes marks the requested direction exhausted without discarding existing pages or overwriting their opposite edge.

### Cursor handling and changing data

Design call: versioned base64url JSON containing kind (`row` or initial `future_boundary`), date, integer ID for row cursors, and a scope fingerprint for the resolved profile and this query version. Limit encoded input size (1 KiB), decoded shape, exact fields, version, canonical dates, and IDs to the positive JavaScript-safe integer range. The initial boundary kind is accepted only with `newer`. Treat tokens as opaque in the client; do not parse their dates through JavaScript `Date`.

Scope fingerprints catch accidental cross-guest reuse; unsigned tokens provide no authenticity guarantee. They are safe navigation input because the server independently supplies authenticated profile scope to every query. A forged token never broadens eligibility. Signing can be added independently later if authenticity becomes a requirement.

Provider updates can move a release date or insert movies inside an already loaded range. This is a live keyset view, not a frozen catalog snapshot. Merge repeated movie IDs defensively, updating/moving an already cached row to its returned sort position. Records newly inserted into an already traversed gap need not appear until route return/reload; normal edge paging may see records beyond its cursor. Passing midnight does not automatically reload the window.

## Client state, navigation, and presentation

### State and I/O boundaries

Add a pure TypeScript `TimelineStore`, timeline read use case and repository interface. Compose the HTTP adapter with the existing guest-session repository. Validate generated DTOs with Zod and map into domain values; generated API imports remain confined to outbound API adapters. UI contexts/providers and hooks subscribe to the store above routes, as Following does.

Keep pages, edge cursors, established `as_of`, request state, and the visible `(release_date, id, pixel offset)` in app memory. Preserve movie IDs as JavaScript-safe numbers and dates as ISO calendar-date strings. Cursor-paging responses leave the established `as_of` unchanged; initial and successful anchored responses replace it. Layout measurements, user gestures, and scrolling live in inbound UI adapters, which pass plain anchor values to the store. Do not persist in local/async storage. New guest creation clears cached data/anchor, aborts old requests, and rejects obsolete responses using existing guest identity-generation events. A full app reload starts at the present.

At most one request per direction is active. Paging may run concurrently in opposite directions; refresh supersedes both. Tag requests with guest generation, route-entry/window revision, and edge cursor so late responses cannot append to a replaced window. Stop hidden-route paging and abort obsolete reads on departure without discarding cached pages or the saved anchor. Background hydration remains independent.

### Route entry and anchored refresh

1. First entry: fetch the initial past-only window once. Never eagerly load future movies from a mount-triggered top-edge callback.
2. Route departure: save the first visible movie's date/ID and its position relative to the viewport. Retain data in the app-level store whether Expo keeps the screen mounted or remounts it.
3. Return: render retained data at the saved position immediately and refresh that anchor's neighborhood. If the previous window was empty, request the initial window. Empty retained state still refreshes on every entry.
4. On successful anchored refresh, replace retained pages with the new bounded window. Keep the saved movie at the same offset if it survives. If it vanished, align `anchor_index` to the top; if no at-or-older item remains, align the last returned movie. If the result is empty, show blank content and clear the movie anchor.
5. If the user scrolls during refresh, preserve their newer position. Cancel/ignore the old result; after scrolling settles, issue one replacement anchored request for the current visible movie. Coalesce repeated movement, allow at most one replacement attempt per entry, and defer further refresh to the next entry to avoid an automatic request loop.
6. Refresh failure retains the previous data and position. Initial failure stays blank. No refresh button, error copy, spinner, or automatic retry is required. Paging failure retains its cursor and may retry after the user moves away from and back toward that edge, rather than looping while a sentinel remains visible.

No completion signal from hydration, follow-store mutation, browser focus, timer, or foreground event changes the window. Timeline entry is the refresh boundary. Server paging always consults currently committed follows, so an active concurrent follow/unfollow elsewhere can affect later pages; there is no cross-tab synchronization promise.

### List and scroll stability

Use existing React Native/React Native Web list primitives behind the UI adapter, with virtualized rendering and rows keyed by movie ID. Reserve poster dimensions/aspect ratio before images load. Variable overview heights require measuring the visible anchor; a raw scroll offset or fixed `getItemLayout` is insufficient.

The installed web VirtualizedList has start/end callbacks but can fire the start callback at mount. Gate newer loading on a deliberate gesture toward newer content at the top. The web UI adapter must detect upward wheel/trackpad intent, keyboard navigation toward the start, and touch drag intent even when scroll offset is zero or the initial past list is empty/too short to scroll. Support the future-only case without adding a button. Once newer rows are loaded, regular near-edge triggers continue paging. Disable each trigger when its edge cursor is null.

Prepending keeps the visible movie stationary. Use visible-anchor row measurements and offset correction after layout, with bounded index/measurement recovery for virtualized variable-height rows. Do not assume React Native's `maintainVisibleContentPosition` works on web; the installed web ScrollView does not expose that implementation. Avoid double correction from browser scroll anchoring. Treat stable prepend, return restoration, and future-only gesture access as required browser acceptance checks before this list implementation is considered viable.

Retain all fetched page data in memory for F003 while virtualizing rendered rows. Memory can grow with unusually long sessions; page eviction is deferred rather than introducing trim/restore behavior in this increment.

### Presentation

Follow the supplied wireframe and existing responsive shell. Sidebar order is Search, Timeline, Following; Timeline is always visible and selected on `/timeline`. Keep Search and Following behaviors unchanged. Movie rows display poster/placeholder, title, formatted release date, and overview when present. Design call: display English month and year, for example `August, 2022`, matching the wireframe, while preserving the full date for ordering. Format the calendar date without local-timezone shifting. Do not show credit lists or followed-person explanations in this increment.

```text
Search       [poster]  Newer / upcoming movie       ↑ newer
Timeline ✓             Month, Year
Following              Overview

             [poster]  Movie near the saved date
                       Month, Year
                       Overview

             [poster]  Older movie                 ↓ older
```

This sketches row content and direction only. A fresh initial viewport contains past/today movies; upcoming rows appear only after upward navigation. Blank initial/empty content keeps the sidebar available. Give the scroll region a keyboard focus target and accessible label; expose movie titles as headings and avoid redundant poster descriptions when the title is adjacent.

## Verification required by the implementation plan

No product tests run for this design-only change. The implementation plan must cover:

- **Migration/persistence:** identity generation, unique/FK/check constraints, preservation of existing people/follows, reversible migration, nullable optional fields, multi-role cast/crew credits, duplicate IDs, provider/local-ID mapping, all-or-nothing commit, empty filmography, rollback freshness, and database-only retry without another provider call.
- **Hydration:** nonblocking enqueue before unsuccessful/slow follow commits, missing-person behavior, validation exclusions, 24-hour edge, coalescing/first-owner attribution, bounds and saturation, rolling rate/in-flight limits, retry charging, shared accounting exhaustion, freshness skip without charge, response size/identity validation, malformed records, shared `429` cooldown with integer/date/malformed/shorter/longer headers, extension by multiple in-flight responses, cooldown release without a burst, cancellation, and shutdown ordering.
- **API/query:** ownership isolation, no provider calls, distinct movies across overlapping follows and roles, same-day ID ties, date/today boundaries, both scan directions, future-only/past-only/empty catalogs, edge exhaustion, deleted cursor/anchor rows, disappeared anchor neighborhood, numeric IDs and safe-integer limits, strict request/cursor validation, initial/anchored `as_of` without a separate clock query, null paging `as_of` with a stable client boundary across midnight, no-store/empty failures, and representative query plans on real PostgreSQL.
- **Client:** DTO validation and mapping, store merge/dedup, request race protection, guest reset, bounded anchored return refresh, failure retention, empty-window reentry, departure without cache loss, no hydration polling/mutation refresh, and correct date rendering.
- **Browser acceptance:** wireframe row/sidebar behavior, direct/history navigation, no eager future request on first paint, mouse/trackpad/keyboard/touch access to future rows from the top and from an empty past side, stable variable-height prepend, poster loading, repeated route return at the same movie/offset, anchor disappearance after unfollow, moving during refresh, and reload at the present. Stub provider traffic; never call the live provider in the ordinary suite.
- **Repository checks:** existing unit/integration/E2E suites appropriate to affected areas, framework-boundary lint/import checks, type checks, deterministic OpenAPI regeneration and generated-client compatibility.

## Builder discretion and review calls

The builder may choose exact file/module names, small port decomposition, bounded helper structures, telemetry event names, CTE construction, and UI measurement mechanics while preserving the specified behavior and layer rules. Sanitized outcomes/counts/latencies are sufficient for telemetry; avoid raw provider bodies, guest identities, and request input.

The following calls were proposed by the author and accepted with design approval on 2026-11-26: UTC today; nullable poster path and untouched movie-complete-credit timestamp; best-effort queue/retry/timeout/size defaults; shared accounting minute limits and first-requester attribution; upsert-only catalog reconciliation; unsigned validated cursors; empty `500` failures; month/year display; no visible Now divider; and data retention without page eviction. The owner selected numeric movie IDs during draft review on 2026-11-26 and approved safe-integer validation and the explicit initial/anchored-only `as_of` contract with this document.
