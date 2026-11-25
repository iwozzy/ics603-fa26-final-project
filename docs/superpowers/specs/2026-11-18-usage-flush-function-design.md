# Usage flush database function

The user selected the PostgreSQL function approach discussed on 2026-11-18 to
reduce the background accounting writer's four database calls to one call per
batch, with commit still owned by the existing unit of work.

## Approaches

Separate statements preserve the current behavior but incur four round trips.
A stored procedure can group the statements but adds no useful transaction
control inside this unit of work. The selected function returns the updated
counter rows directly and keeps all writes in the caller's transaction.

## Design

Add a forward Alembic migration defining
`lumiere_flush_charges(uuid, bigint, jsonb) RETURNS SETOF usage_counters`.
The function creates and locks the writer checkpoint, returns existing counts
for the most recently applied batch, or atomically increments the supplied
counters and advances the checkpoint for the next batch. Reject older batches
and gaps. Order counter upserts consistently across writers.

Keep repository input validation and the existing `flush_charges` interface.
Call the function once with typed parameters and refresh retained ORM rows.
An empty result signals an invalid sequence; raise the existing `ValueError`
in Python so rejection does not abort earlier work in the caller's transaction.
Reject sequences outside bigint before issuing SQL. Keep startup hydration, in-memory admission,
batching, retry behavior, and unit-of-work commit ownership as they are.
Downgrade removes only the function; counters and checkpoints survive.

## Verification

Use real disposable PostgreSQL to check one statement including ORM flush at
commit, retries without double charging, rollback, concurrent batches, sequence
errors, bigint sequence parameters, and migration downgrade/upgrade preserving
data. Reuse the existing accounting and lost-acknowledgment regression tests.
Run backend tests, lint, type checking, and import contracts. Do not read local
configuration or credentials or apply migrations to an application database.
