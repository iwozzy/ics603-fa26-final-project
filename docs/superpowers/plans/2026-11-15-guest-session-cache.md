# Guest Session Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Skip repeated Postgres session lookups using a bounded process-local validation cache.

**Architecture:** A standard-library LRU cache holds immutable stored session identities by digest with a monotonic fixed TTL. GuestSessionsService warms after committed bootstrap/successful database reads and rebuilds request IP context on each hit.

**Tech Stack:** Python, OrderedDict, monotonic time, existing UoW and pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-guest-session-cache-design.md`

## Global Constraints

- Preserve existing uncommitted atomic admission changes. Quota charging is unchanged.
- No raw cookie values or IP context in cache. Do not read/write secrets or environment files.
- Default cache capacity 10,000, TTL 60 seconds, constructor configurable; no new runtime settings.
- Check true session expiry on every hit. Hits do not extend TTL.
- Bootstrap remains database-authoritative; only publish after successful transaction exit.

## Review Focus

- A failed/ambiguous bootstrap commit must never create a cache-authorized session.
- Actual session expiry must override a still-live cache TTL.
- Repeated cache hits must not postpone database revocation checks indefinitely.
- Switching IPs on a warm session must charge the current IP's counters.
- Invalid cookies and cache misses during storage failure must never authorize a session.

### Task 1: Cache validated guest sessions

**Files:** Create `backend/src/lumiere/application/session_cache.py` and `backend/tests/unit/application/test_session_cache.py`; modify `application/use_cases/guest_sessions.py`, add real-Postgres session-cache coverage in `tests/integration/persistence/test_sessions.py`; document behavior in README.

**Interfaces:** `GuestSessionCache(max_entries: int = 10000, ttl_seconds: float = 60, timer: Callable[[], float] = monotonic)`; `get(digest: bytes, now: datetime) -> StoredGuestSession | None`; `put(digest: bytes, session: StoredGuestSession) -> None`. `GuestSessionsService(..., *, cache: GuestSessionCache | None = None)` owns a default cache when omitted.

- [x] Write deterministic service/cache tests for zero-UoW warm hits, fixed TTL, expiry, LRU eviction, per-worker cold fallback, current IP, failed commits/exits/reads, invalid sessions and bootstrap quotas. Run and observe expected failures.
- [x] Implement the bounded cache and service integration; run the unit suite until green.
- [x] Add real-Postgres tests proving a warm resolve performs no SQL, deletion is observed after TTL, and session expiry/identity behavior remains correct.
- [x] Run full backend tests against migrated disposable Postgres, lint/type/import checks and composed browser tests; expect pass.
- [x] Update README, obtain fresh read-only code review, fix material findings and leave changes reviewable in the existing worktree.

## Verification results

145 backend tests passed, including 24 real migrated Postgres persistence tests and 22 deterministic session-cache cases. Seven composed browser tests passed. Ruff, strict typing, import architecture and diff whitespace checks passed. A fresh scoped code review found no issues. Warm resolution was verified to emit zero SQL and open no database unit of work. Hosted latency requires deployment measurement.
