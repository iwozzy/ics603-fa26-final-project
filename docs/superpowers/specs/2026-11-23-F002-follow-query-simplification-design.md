# F002 Follow query simplification

Approved by the owner on 2026-11-23 after reviewing the three-statement proposal.
This amends the POST transaction in the [original F002 design](2026-11-23-F002-follow-people-design.md).

## Intent and constraints

Reduce a successful Follow from six SQL statements to three, preserving existing
HTTP contracts, missing-profile/person errors, the three-person guest cap,
idempotency, timestamp ordering, and commit-before-success. Use the existing
async application pool and framework-free application ports. No schema, provider,
client, configuration, or Unfollow changes are needed.

## Approaches

The existing lock/lookup/membership/count/insert/list flow is correct but performs
redundant round trips. An unlocked `INSERT ... SELECT ... ON CONFLICT DO NOTHING`
handles duplicates but cannot enforce the cap across concurrent distinct follows.
The owner approved retaining the profile lock, inserting idempotently, and checking
the cap using the response list, rolling back an excess insertion.

## Transaction

1. Lock the resolved guest profile with `SELECT ... FOR UPDATE`; reject a missing
   profile. Follow requests for that profile remain serialized across processes.
2. In one SQL statement, resolve `people.tmdb_id` and insert the membership with
   `ON CONFLICT (profile_id, person_id) DO NOTHING`. A data-modifying CTE reports
   person existence independently of whether a row was inserted. A missing person
   aborts with `missing_person`, including when the profile is at the cap.
3. Read the current following list with the existing joined, newest-first query.
   If its length exceeds `GUEST_FOLLOW_LIMIT = 3`, raise `follow_limit` and roll back
   the transaction. Otherwise commit and return the snapshot. A fourth membership
   is never committed or visible to other transactions.

The repository's `add(profile_id, identity) -> bool` returns person existence,
including for an existing follow. Remove separate lookup, membership, and count
methods. SQL factoring belongs to the adapter; the cap remains in the use case.
Repeats preserve timestamps, including at three follows. Unfollow keeps its current
unlocked DELETE and existing visibility-based concurrency contract.

## Verification

Exercise real PostgreSQL statement counts (new/repeated/cap-rejected follows),
missing-person behavior below/at the cap, rollback of the speculative fourth row,
concurrent duplicate/distinct follows, existing timestamp/durability/cancellation
tests, and application/API regression tests. Use only the fixed disposable
persistence test database; do not read secrets or connect to the application database.
