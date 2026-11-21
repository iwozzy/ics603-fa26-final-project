# Asynchronous person persistence during search

Status: draft for user approval. The user selected best-effort queued persistence,
a dedicated people-writer pool of five connections plus five overflow connections,
and asynchronous dispatch with at most ten batch writes in flight. Remaining
design choices below are proposals, rather than previously approved requirements.

## Intent and scope

Establish app-owned person records as a stepping stone toward following people,
while keeping search responses independent of database write latency. Search
returns provider identifiers; a future follow operation will resolve the app-owned
person ID by matching the TMDB provider ID to the stored `tmdb_id`.

Persist only the selected results returned by a backend search: up to seven valid
people from TMDB's first page, in provider order. Save the same recognition-title
strings currently served to the client. Do not retain richer TMDB known-for
objects, query strings, ranked search snapshots, or additional provider results.

Following, follow-time handling of missing people, filmography hydration,
cross-provider identity reconciliation, durable job delivery, and searching the
local people table are outside this change. A person may be absent when following
starts because its write is pending, failed, or was dropped. The following feature
must define that behavior; search makes no persistence guarantee.

This design supersedes the previous F001 identity-deferral and no-person-content-
persistence policies. Existing search selection, quota charging, browser caching,
deadlines, and presentation behavior continue to apply.

## Approaches

1. Synchronous bulk upsert: one transaction per selected search batch, but search
   waits for the database. Rejected because fast responses are the priority.
2. One background task per response: avoids awaiting the write in search, but
   requires additional bounds and lifecycle handling to control concurrent work.
3. Bounded in-memory queue with async dispatch: enqueue selected data immediately
   and process it independently, controlling pending work and database concurrency.
   Selected by the user with best-effort delivery. The user further chose an
   independent pool of five connections plus five overflow and accepted a
   dispatcher concurrency limit of ten.

## API and data translation

Each returned person gains `provider` and `provider_id`. Rename `department` to
`known_for_department` throughout the backend contract and adapt the frontend's
domain property to `knownForDepartment`. Keep the current name, complete profile
image URL, and zero-to-three nonblank recognition titles.

Proposed numeric-ID contract: `provider_id` is a positive JSON integer no greater
than `9,007,199,254,740,991` (`2^53 - 1`), so the TypeScript client can retain it
exactly as a number. Validate that bound at the provider boundary and in generated
transport schemas. Skip records outside that range rather than silently rounding
their identity. This is the design author's boundary-validation choice; supporting
larger identifiers would require a later string-ID contract change.

Proposed provider representation: a stable app-defined string identifier `tmdb`,
declared in an application-owned provider vocabulary. This is not a provider ID
lookup from the database. There is currently no providers table. This proposal is
subject to user approval; numeric provider identities would change the design.

Example person response:

```json
{
  "provider": "tmdb",
  "provider_id": 4139,
  "name": "Tom Skerritt",
  "known_for_department": "Acting",
  "profile_image_url": "https://image.tmdb.org/t/p/w180_and_h180_face/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg",
  "known_for": ["Alien", "Top Gun", "Contact"]
}
```

Do not expose the database person ID in search results. Frontend mappings retain
the provider and provider ID for future interactions. Update the root OpenAPI
contract and regenerate its TypeScript and Zod definitions together with the
frontend mapper, domain types, fixtures, and affected tests. The department rename
is a coordinated contract change; no deprecated alias is proposed.

The TMDB boundary retains the valid provider ID and a validated relative profile
path, in addition to the existing normalized display fields. The complete image
URL remains available to the response; the relative path is internal persistence
data and is not added to the public response. Preserve existing tolerant handling
of optional fields. An invalid/missing image path becomes null in both stored path
and display URL. A usable person ID must fit the positive safe-integer API range
above, which also fits PostgreSQL bigint; unusable IDs are skipped like other
invalid provider records.

## Person storage

Add a forward Alembic migration after `0006_usage_flush_function`. Proposed SQL
table name: `people`, matching the repository's lowercase plural convention; it
represents the app-owned Person entity.

| Column | Storage and rules |
| --- | --- |
| `id` | bigint primary key; generated by the requested UUID-derived 40-bit expression |
| `tmdb_id` | bigint, not null, positive, unique; the upsert conflict key |
| `known_for_department` | nullable text |
| `name` | non-null normalized nonblank text |
| `known_for` | non-null JSONB array of zero to three normalized title strings |
| `tmdb_profile_path` | nullable text containing the validated relative TMDB path |

Use the user's ID generation expression:

```sql
"id" bigint PRIMARY KEY DEFAULT ((('x'::text || substr(replace((gen_random_uuid())::text, '-'::text, ''::text), 1, 10)))::bit(40))
```

Validate that default against disposable PostgreSQL during implementation. If the
bit-string result needs an explicit outer bigint cast for a bigint column, preserve
the exact generation algorithm and add only that type conversion. This is an
implementation typing decision, not a change to the requested ID space.

Each attempt executes one multi-row `INSERT ... ON CONFLICT (tmdb_id) DO UPDATE`
statement for the batch, then commits once. No preliminary SELECT, per-person
queries, or ID retrieval is needed. Transaction control and pool health checks may
involve driver operations; the one-statement guarantee applies to the person-data
write, rather than promising one total network message including commit.

Updates replace all supplied summary fields, including clearing optional values
when the new normalized result is null or empty. Existing app-owned IDs are never
updated on conflict. A transaction either persists its whole batch or rolls back.
Concurrent batches may overlap; the last applied write supplies the summary. No
search-time ordering or freshness guarantee is introduced.

Preserve duplicates and order in the response, as today. For persistence only,
deduplicate repeated `tmdb_id` values within a batch, retaining the first occurrence,
and sort by `tmdb_id` before the bulk statement. This prevents updating one conflict
row twice in a statement and gives concurrent overlapping batches a consistent
lock order. Repeat writes converge on one row per TMDB person. If an insert hits a
primary-key collision, a bounded whole-batch retry gets newly generated defaults.

## Pool registry and queue ownership

Introduce a small persistence-adapter pool registry, owned by the composition root.
It supplies named async session factories and disposes each engine on shutdown.
Keep SQLAlchemy engines, sessions, URLs, and pool checkout mechanics outside the
application and domain layers. Queue processors receive a persistence port or
unit-of-work factory bound to their assigned pool.

Configure two named pools against the existing database destination:

| Pool | Assignment | Pool size | Overflow | Maximum checked out |
| --- | --- | --- | --- | --- |
| `application` | Existing guest identity, usage accounting, and readiness operations | 5 | 5 | 10 |
| `people_writer` | People queue persistence only | 5 | 5 | 10 |

Both pools open connections as needed and retain the existing pre-ping and hidden-
parameter behavior. People writes cannot check out an application-pool connection,
and other operations cannot check out a people-writer connection. This isolates
application-side checkout capacity, not database CPU, locks, or server resources.
The backend process can check out at most twenty database connections in total.

This registry assigns resources to queues; it is not a general job framework.
The existing usage queue continues its current writer and admission policies using
the application pool. Do not redesign accounting batching or quota semantics.

## Async scheduling and backpressure

After normalization, admission, provider mapping, and selection of at most seven
results, search offers an immutable persistence batch to a non-awaiting enqueue
operation, then returns its response. Empty results enqueue nothing. Enqueue does
no connection checkout, database operation, wait for queue space, or task-per-person
creation. Browser-cache hits do not reach the backend and enqueue nothing.

One dispatcher owns the queue. It starts an asynchronous task for a batch when
there is an available dispatch slot, up to ten incomplete batch tasks. Each task
uses its own unit of work, session, and transaction from the assigned people pool.
No session is shared between tasks. At capacity, the dispatcher waits for a task
to finish before dispatching another batch. Queued entries remain data, rather
than becoming an unbounded collection of tasks waiting for connections. Database
waits yield to the event loop; no synchronous driver calls or worker threads are
introduced by this change.

Proposed operational defaults, chosen here for review:

- At most 1,024 outstanding search batches, counting queued and in-flight work.
  Track that combined count so taking an entry out of the queue does not open a
  second allowance for work that is still running.
- At most ten in-flight tasks, derived from the dedicated pool's maximum capacity.
- Five-second timeout per persistence attempt, including checkout and transaction
  completion; at most three attempts per batch, with a one-second async delay
  between failures. A retry retains its dispatch slot and outstanding allowance.
- Five-second total shutdown drain, followed by cancellation and awaiting of all
  remaining dispatcher/write tasks before disposal.

These are named constructor defaults, consistent with the existing accounting
service; no new environment configuration is required. The builder may adjust
internal factoring, but changes to delivery guarantees or these bounds require an
explicit design update.

When full, stopped, or unavailable, enqueue drops the incoming batch immediately.
It does not evict older work or fail the search. Completed or permanently failed
batches release their outstanding allowance exactly once. A failed write rolls
back and returns/discards its connection correctly; bounded retries use fresh
transactions. Retrying after an ambiguous commit may replace summary fields again
but cannot create duplicate TMDB rows or alter an existing person ID.

Catch and report task failures so the dispatcher continues scheduling other work.
Writer health is observable but does not become a new search-admission or readiness
gate. Existing readiness checks retain their behavior. Retain the existing rule
that no request-owned database transaction spans the TMDB call.

## Lifecycle and observability

Start the people dispatcher before accepting search requests. Startup creates its
pool and task without requiring initial person-data reads. Shutdown stops new
enqueues, attempts the bounded drain, cancels and awaits remaining work, and then
disposes the named pools. Cleanup also works after partial startup failure.

A crash, shutdown timeout, saturated queue, or exhausted retries may lose a batch.
That is accepted best-effort behavior and never changes an already returned search
response. Client cancellation after enqueue does not cancel the independent write;
cancellation before enqueue creates no batch. Successful enqueue does not imply
the response was delivered to the browser.

Record queue acceptance/drop counts, outstanding and in-flight counts, persistence
success/failure/retry counts, and latency through the existing observability
boundary. Do not log person names, raw payloads, queries, or connection parameters.
Do not read or write secrets or application database contents during development.

## Verification and documentation

Use controlled fakes to prove search returns while database work is blocked,
enqueues only its selected results, preserves response order and duplicates, skips
empty batches, and remains successful when enqueue drops work. Verify the renamed
department and provider fields through the TMDB boundary, API contract, frontend
validation, and presentation tests.

Exercise queue capacity including in-flight tasks, ten-task concurrency, immediate
rescheduling when a task completes, independent sessions, bounded retries, failed
task recovery, cancellation, shutdown drain/timeout, and partial-startup cleanup.
Verify pool registration, actual separation from application operations, assignment
to the people writer, and resource disposal. Block writes on one connection and
prove another batch can execute concurrently through the assigned pool.

With the existing disposable PostgreSQL harness, verify the generated primary-key
default, mapped summary values, one bulk data statement per attempt plus commit,
stable IDs across updates/retries, duplicate-input handling, concurrent overlapping
batches, transaction rollback, and migration upgrade/downgrade. Include ID generation
and profile-path edge cases. Use no live TMDB calls or application database.

Run the affected backend/frontend suites, lint/type/import checks, API generation
consistency checks, and relevant existing browser coverage. Update the README,
search architecture diagrams, and prior architecture/F001 documents with a dated
amendment linking to this design so the earlier identity-deferral policy is not
mistaken for current behavior.

## Decisions left to the builder

Choose internal class/module names, port granularity, and the exact safe dispatcher
mechanism within these contracts. Keep the pool registry adapter-local and reusable
without introducing a generic scheduler. Verify PostgreSQL's required default cast
and choose the smallest correct representation. Do not implement following or add
provider tables unless the user changes the proposed string provider contract.
