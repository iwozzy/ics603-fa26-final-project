# In-memory Usage Accounting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Admit searches using local counters and asynchronously persist daily/total usage through one bounded background task.

**Architecture:** Startup hydrates durable counters. Local admission charges all scopes and enqueues six persistent keys; one writer reconciles committed database counts with unacknowledged deltas. A sequential checkpoint makes retries idempotent.

**Tech Stack:** Python asyncio, existing application ports, SQLAlchemy/Postgres, Alembic, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-memory-usage-accounting-design.md`

## Global Constraints

- One backend process/replica; crash-time loss of pending charges is accepted.
- No database charging on the request path; no persisted minute increments.
- Constructor defaults: 1,024 outstanding charges, batch size 64, persistence/shutdown timeout five seconds, retry delay one second, 10,000 minute keys.
- Preserve API/configuration, durable identities and existing counters; never access operator credentials.

## Review Focus

- New charges admitted during a blocked flush must survive database reconciliation (Task 2).
- A commit acknowledged as a failure must not double-count on retry (Tasks 1, 2).
- Midnight and failed persistence must preserve original day keys and cap enforcement (Task 2).
- Saturated queues and minute-key capacity must reject without partial charges (Task 2).
- Startup/shutdown failures must not leave live tasks using disposed connections (Task 3).

### Task 1: Durable additive batches and retry checkpoints

**Files:** `application/ports/usage.py`, persistence repositories/models, new migration `0005_async_usage.py`, `tests/fakes/access.py`, new `tests/integration/persistence/test_async_usage.py` (backend paths).

**Interfaces:** Produce `load_counts(day: str) -> dict[CounterKey, int]` and `flush_charges(writer_id: UUID, sequence: int, deltas: Mapping[CounterKey, int]) -> dict[CounterKey, int]` on `UsageRepository`. Existing unit of work owns commit.

- [x] Write integration tests for snapshot filtering, additive updates, returned counts above caps, rollback, duplicate sequence after commit, invalid sequences and checkpoint migration roundtrip.
- [x] Run new tests against disposable Postgres; expected failure before implementation.
- [x] Implement checkpoint model/migration and repository methods, plus transactional fake behavior. Retain historical admission adapter for migration compatibility.
- [x] Run persistence tests and lint/type checks; expected pass.

### Task 2: Local admission, minute limits and background writer

**Files:** `application/use_cases/usage_admission.py`, new `application/minute_limits.py`, `application/use_cases/guest_identity.py`, application unit tests.

**Interfaces:** Keep `admit_and_charge(context, now) -> None`; add `start(now: datetime) -> None`, `drain() -> None`, `close() -> None`. Consume Task 1's repository methods. One `MinuteLimiter` implements synchronous atomic fixed-window checks/charges for search and bootstrap.

- [x] Write tests for blocked persistence with immediate admission/provider dispatch, each cap, concurrency, queue fullness, returned snapshot plus newer charges, retries/timeouts/ambiguous commit, pending midnight rollover, startup failure and shutdown timeout/drain.
- [x] Run new unit tests; expected failure before implementation.
- [x] Implement the bounded queue/writer, startup hydration, committed reconciliation, bounded shutdown and memory-only minute limiter. Move bootstrap minute charging before identity storage.
- [x] Update superseded synchronous-accounting tests to assert the approved behavior, preserving identity/provider coverage. Run application tests; expected pass.

### Task 3: Runtime ownership and whole-change verification

**Files:** `bootstrap.py`, `search_people.py`, runtime/persistence tests, `README.md`.

**Interfaces:** `AppContainer` owns admission, starts it before serving, and closes it before network/database clients. Readiness includes admission readiness.

- [x] Write lifecycle tests proving startup loading, bounded teardown and cleanup ordering, plus real-Postgres request-path/flush/restart tests. Run them; expected failure before wiring.
- [x] Wire lifecycle and update comments/documentation for single-process limits, local minute counters, startup reads and crash loss.
- [x] Run `pytest`, `ruff check`, `pyrefly check`, `lint-imports`, API export checks, disposable Postgres integration tests and available browser flows. Expected pass; report any unavailable checks explicitly.
- [x] Obtain a fresh read-only whole-change code review, address material findings, rerun relevant verification, and mark this plan's tasks complete.

## Execution notes

User explicitly approved the approach and requested implementation; execute inline in the existing isolated worktree without another approval gate. Keep changes reviewable in the worktree; do not publish or merge.

## Verification results

Backend: 169 tests passed including real Postgres. Frontend: 34 passed. Browser: 7 passed. Ruff, pyrefly, import contracts, frontend/e2e TypeScript checks, frontend lint and OpenAPI export checks passed. Fresh read-only code review found no Critical, Important or Minor findings. Disposable test services were removed after verification.
