# Atomic Search Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Consolidate admission into one Postgres operation and remove dispatch/outcome transactions from people search's response path.

**Architecture:** One application-owned transaction invokes a Postgres function to check/increment all counters and insert a charged attempt. Provider I/O starts after commit. A bounded, service-owned task records outcomes conditionally without changing the charge.

**Tech Stack:** Python, asyncio, SQLAlchemy, PostgreSQL, Alembic, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-atomic-search-admission-design.md`

## Global Constraints

- Preserve all nine durable quota limits and server-resolved identity rules.
- Accounting failure before admission commits prevents dispatch.
- No database transaction spans provider I/O; no hidden provider retries or refunds.
- Preserve HTTP/cache/provider contracts. Do not read or write secrets.
- Outcome unknown remains charged; two-second recording timeout, at most 128 in-flight tasks.

## Review Focus

- Different sessions/IPs contending for the same global cap must not over-admit or deadlock.
- Exhausting any one cap must leave all other counts and the attempt ledger unchanged.
- Failed or ambiguous admission must never dispatch or be automatically retried.
- Slow/broken outcome persistence must not block successful results, failures, or cancellation.
- Legacy reservations and counts must survive migration without refunds or invented outcomes.

### Task 1: Atomic admission and asynchronous outcomes

**Files:** Modify `application/ports/usage.py`, `application/use_cases/{usage_admission,search_people}.py`, persistence `repositories.py` and `models.py`, `bootstrap.py`, migration `env.py`, access/search fakes and tests. Add `migrations/versions/0002_atomic_admission.py` and persistence migration tests. Update README accounting behavior.

**Interfaces:** `UsageAdmission.admit_and_charge(context: GuestContext, now: datetime) -> Reservation`; `UsageRepository.admit_and_charge(limits: Mapping[CounterKey, int], reservation: Reservation) -> bool`; `UsageRepository.finish(reservation: Reservation, outcome: AttemptOutcome) -> None`; `SearchPeople.aclose() -> None`.

- [x] Write tests for charged-before-dispatch behavior and returning results while completion is stalled/broken; run and observe failures against the existing implementation.
- [x] Write real-Postgres tests for one-call admission, atomic rejection at each cap, cross-identity contention, rollback and legacy migration; run and observe failures.
- [x] Implement the migration/function, ports, adapters, fakes, use cases, bounded completion and runtime shutdown ownership.
- [x] Update existing tests to wait explicitly for asynchronous outcomes and replace obsolete reservation/refund expectations with admission-charge behavior. Preserve rollover, restart and outage coverage.
- [x] Run all backend tests with migrated disposable Postgres; run lint, strict typing and import checks. Run composed browser tests if available. Expected: pass.
- [x] Document final behavior and migration requirement; obtain a fresh code review and resolve material findings. Leave the verified changes reviewable in the current worktree.

## Verification results

121 backend tests passed, including real migrated Postgres. All seven composed browser tests passed. Ruff, strict typing, import contracts, and diff whitespace checks passed. Fresh code review found no unresolved issues after regression-tested shutdown and large-cap fixes. Application deployment and latency measurement remain operator steps.
