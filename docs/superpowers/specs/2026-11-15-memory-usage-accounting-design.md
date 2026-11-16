# In-memory usage accounting with asynchronous persistence

Approved in conversation on 2026-11-15: remove database charging from search requests, keep full remaining allowances in memory, persist daily/total charges asynchronously through one background async task, and keep minute limits entirely in memory. The user accepts loss of unflushed charges on a crash. This supersedes synchronous counter-only admission.

## Approaches

We considered synchronous Postgres admission, precharging allowance blocks, independently spawned persistence tasks, and one queued background writer. The user selected local admission with one background async task and a queue. It avoids database waits without introducing another process or service, and serializes reconciliation and retries. Hard shared caps across multiple backend processes are outside this design; operate one backend process/replica.

## Behavior

Before serving searches, load all persisted people-provider total counters and the current UTC day's counters. Unknown identities start at zero after this complete snapshot. Startup failure prevents serving. Admission performs no database operations: atomically check global/guest/IP daily, total and minute limits, charge locally, enqueue the six persistent counter keys, then permit provider dispatch. Invalid queries and quota/storage rejections consume nothing. Provider failure/cancellation retains the admitted charge.

Effective daily/total usage equals the last confirmed database count plus all local charges not yet acknowledged. One writer wakes immediately on a charge, drains up to 64 queued charges, atomically adds their deltas, and receives updated database counts. Publish returned counts and subtract just that batch's pending deltas only after commit and unit-of-work exit succeed. Newer admissions remain pending. Date keys are fixed at admission, so delayed writes across UTC midnight charge the original day.

Minute counters (including the guest-bootstrap IP limiter) never reach Postgres. Fixed UTC minute windows retain all active entries and discard expired windows; restart resets them. A limiter capacity of 10,000 active counter keys prevents unbounded bootstrap IP cardinality; reject new entries when full without evicting an active allowance. Guest bootstrap still persists identities, and cold credential resolution still reads Postgres.

## Lifecycle and failure handling

Implementation defaults: at most 1,024 outstanding searches including in-flight persistence; batches of at most 64; five-second persistence timeout; one-second retry delay; five-second shutdown drain. These are constructor defaults, not new environment settings. A full backlog, unstarted/closed service, or failed writer rejects search admission as storage unavailable. Admission never awaits queue space. One writer owns one batch until acknowledged; no unbounded task spawning. Shutdown stops admission, attempts a bounded drain, then cancels/awaits the writer before disposing database connections. A process crash or shutdown timeout may lose pending charges as accepted.

Retry the same writer UUID and sequential batch number after errors or an ambiguous commit. A compact `usage_flush_checkpoints` row per writer stores the last applied batch number in the same transaction as counter updates. Repeating that batch reads the existing counters instead of incrementing again; gaps/older batches fail. This stores no per-search history. Do not reject persistence at quota caps: dispatched usage must be recorded even above a cap. Database-returned counts may include external updates, but reconciliation does not provide strict multi-process admission.

Add a forward migration for checkpoints, preserving existing counters and identities. Historical minute rows and admission functions can remain for migration compatibility; the runtime no longer writes or calls them. Stop old writers before starting the new single-process backend. Downgrade drops checkpoints; stop/drain the new writer first. Daily snapshots are pruned on date rollover, while total counters remain resident. No Redis, external job service, provider outcome ledger, API or configuration changes.

## Verification

Prove admission completes while persistence is blocked, all nine caps reject without partial local charges, and replies preserve charges admitted during a flush. Cover startup hydration/failure, concurrent identities, provider failures/cancellation, minute rollover/restart/capacity, midnight with pending batches, queue saturation, persistence failures/timeouts, ambiguous-commit retry, shutdown drain/cancellation, and no minute rows written. Real Postgres tests verify additive updates, rollback, duplicate batches, restart hydration and migration roundtrips. Run backend tests, lint, type and import checks, API generation checks and relevant browser checks where available, followed by fresh code review.
