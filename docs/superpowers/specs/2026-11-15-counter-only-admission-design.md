# Counter-only usage admission

Approved in conversation on 2026-11-15: charge admitted people searches regardless of provider outcome, remove usage reservations and all post-provider accounting. This supersedes the per-attempt outcome recording in the earlier atomic admission design.

## Approaches

The existing implementation already charges permanently before dispatch but stores a reservation and asynchronously records its outcome. We considered retaining that audit history or using counters alone. The user selected counters alone, including removal of existing per-attempt history when the migration is applied. Telemetry remains diagnostic; durable counters are the quota authority.

## Design

Validate the query and guest context, invoke one Postgres function to create/lock/check/increment all nine global/guest/IP minute/day/total counters, commit, then call the provider. No accounting work occurs after provider success, failure or cancellation. Invalid queries and rejected admissions do not consume allowance; ambiguous commits never trigger dispatch or retries. Crashes after a committed charge retain that charge even if provider dispatch never occurred.

`UsageAdmission.admit_and_charge(context, now) -> None` returns after commit or raises. `UsageRepository.admit_and_charge(limits) -> bool` performs one database call. Remove reservation IDs, records, outcomes, finish methods, settlement tasks/timeouts/limits and SearchPeople shutdown ownership. Cancellation propagates naturally; provider exceptions retain existing HTTP failure behavior.

Migration `0004_counter_only_admission` replaces the UUID+JSONB admission function with a JSONB-only function using the same deterministic counter locking and post-lock cap check, then drops `usage_reservations`. Counters, guest identities and cookies remain unchanged. Stop old application writers before migration and start the matching backend afterward. Downgrade recreates the former table empty and restores the old function; dropped audit history cannot be recovered by downgrade.

## Verification

Test that admission commits once before provider I/O, all outcomes retain all counters, and no database access or background accounting occurs after the provider begins. Retain invalid-input, atomic rejection, concurrent cap, rollover, restart, outage, ambiguous-commit and HTTP deadline coverage. Real migration tests verify table removal, both function signatures across upgrade/downgrade, and unchanged counters. Run complete backend tests, lint/type/import/OpenAPI checks, browser flows and fresh code review.
