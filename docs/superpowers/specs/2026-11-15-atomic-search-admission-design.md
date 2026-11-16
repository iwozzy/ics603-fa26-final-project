# Atomic search admission and charging

Approved in conversation on 2026-11-15: combine Postgres admission consolidation with charging at admission and asynchronous outcome recording.

## Intent and constraints

Reduce sequential database round trips in people search while preserving durable, atomic global/session/IP minute, daily, and cumulative limits. Keep the existing API, browser caching, server-resolved quota identities, provider bounds, and one provider attempt per admitted search. Accounting failure before admission commits prevents dispatch. No database transaction spans provider I/O.

## Approaches

1. Consolidate admission into one Postgres function call and one application-owned commit. Preserves strict shared limits while shortening global-counter lock duration.
2. Charge at admission, eliminate dispatch marking, and record outcomes asynchronously. A crash between charge and dispatch consumes unused capacity conservatively.
3. Redis admission adds infrastructure and durability/failover decisions. Deferred.

The user selected 1 and 2 together. Admission atomically creates missing counters in consistent order, locks/checks all nine, increments all nine, and inserts a `charged` attempt. Any rejection or failure leaves no partial charge. The application commits before provider dispatch; ambiguous commits never trigger retries or refunds. The existing reservation table remains the durable attempt ledger, with legacy states preserved by migration.

## Lifecycle and implementation calls

The application port becomes `admit_and_charge(context, now) -> Reservation` plus `finish(reservation, outcome)`. Admission returns only after commit. Completion is a conditional, idempotent `charged` to success/failed/cancelled update that never changes counts. Query validation happens before charging.

Outcome recording is best effort and outside the response path, with a two-second timeout and at most 128 in-flight recording tasks per search service. When overloaded, timed out, interrupted, or unavailable, records remain `charged` (outcome unknown). Complete outcome reporting and a durable retry worker are not required for quota correctness and are outside this change. The runtime cancels/drains owned outcome tasks before disposing database connections. Successful provider responses remain successful during outcome-accounting failures.

The database function is installed through an Alembic migration. Persistence tests exercise the migrated schema, atomic rejection, concurrent admissions across identities, rollover, restart, rollback, migration compatibility, and the single database-call admission boundary. Unit/API tests exercise charged-before-dispatch ordering and nonblocking outcome handling for success, failure, and cancellation.

## Verification

Run backend unit/API/provider tests, real disposable Postgres persistence tests, lint/type/architecture checks, and composed browser search tests if the local container runtime is available. Latency improvement in the live deployment requires a separate post-deployment measurement; local tests verify the removed round trips and commits.
