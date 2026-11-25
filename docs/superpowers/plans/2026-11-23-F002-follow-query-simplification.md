# Follow Query Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute successful new and repeated Follow actions in three SQL statements while preserving the cap and failure contracts.

**Architecture:** Retain the profile lock. Replace lookup/membership/insert with one idempotent insert CTE reporting person existence. Validate the cap from the response list and roll back excess insertions before commit.

**Tech Stack:** Python, SQLAlchemy async, PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-F002-follow-query-simplification-design.md`

## Global Constraints

- `GUEST_FOLLOW_LIMIT = 3` remains application policy.
- Preserve missing-profile/person errors, repeated-follow timestamps, async I/O, and commit-before-success.
- No schema, provider, client, configuration, or Unfollow changes are needed.
- Do not read secrets or connect to the application database; use the fixed disposable integration harness.

## Review Focus

- Missing people at the cap must still fail with `missing_person`.
- Deleted profiles must still fail even with cached identity resolution.
- Repeating a follow at the cap preserves its original timestamp and ordering.
- A rejected fourth insertion must disappear after rollback and never become visible outside its transaction.
- Concurrent distinct follows from two must commit exactly one addition; unlocked Unfollow keeps its existing contract.

### Task 1: Replace the Follow transaction and verify its contracts

**Files:**
- Modify `backend/src/lumiere/application/ports/following.py` (repository contract).
- Modify `backend/src/lumiere/application/use_cases/following.py` (cap validation).
- Modify `backend/src/lumiere/adapters/outbound/persistence/following_repository.py` (idempotent insert CTE).
- Modify `backend/tests/fakes/following.py` (idempotent in-memory adapter).
- Modify `backend/tests/unit/application/test_following.py` (use-case contracts).
- Modify `backend/tests/integration/persistence/test_following.py` (query budget and real transactions).
- Modify `docs/architecture/follow-people.md` and the original F002 design (link the approved amendment).

**Interfaces:**
- Consumes existing `FollowingUnitOfWorkFactory`, `PersonIdentity`, and snapshot/list ordering.
- Produces `FollowingRepository.add(profile_id: UUID, identity: PersonIdentity) -> bool`: true for an existing local person, including an already-existing membership; false for a missing person.
- Removes `find_person`, `is_following`, and `count`; keep `lock_profile`, `remove`, and `list_people`.

- [x] **Step 1: Write failing regression tests.** Capture actual PostgreSQL statements around new/repeated/over-cap Follow calls and assert three statements. Check missing-person failure at zero/three follows, cap rollback from a fresh transaction, and unchanged repeat timestamps. Update application tests for insert-before-list-before-commit and rollback on over-cap snapshots. Retain deleted-profile, concurrency, and Unfollow tests.
- [x] **Step 2: Run tests red.** Run `LUMIERE_RUN_PERSISTENCE=1 uv --directory backend run pytest tests/integration/persistence/test_following.py -q` against disposable PostgreSQL and the affected unit tests. Expected: the new statement-budget test fails because the current successful new Follow executes six statements.
- [x] **Step 3: Implement the approved flow.** Build a candidate-person CTE, a data-modifying insert CTE using PostgreSQL `ON CONFLICT DO NOTHING`, and a final candidate selection so person existence is known even on duplicate inserts. Update the port/fake/use case and remove obsolete methods. Update integration setup to use the new contract and documentation to describe post-insert cap validation.
- [x] **Step 4: Verify.** Run the affected unit/persistence tests, the full backend suite with disposable persistence enabled, backend Ruff/type/import checks, and `make test` for client regressions. Expected: all pass, with three statements for new/repeat/cap rejection and unchanged concurrency guarantees.
- [x] **Step 5: Review the change.** Check the whole diff against the spec and Review Focus; address material findings and report validation. Leave changes reviewable in this worktree.

## Execution evidence

- Existing linked worktree reused; changes remain reviewable without a commit.
- Used the installed `backend/.venv/bin` tools directly because the default UV cache is outside the writable sandbox. Local PostgreSQL tests required elevated execution for the fixed loopback test connection.
- Baseline: 74 unit/API tests and 21 following persistence tests passed.
- Red: three query-budget cases failed with observed counts of six, four, and four; two unit cases failed on the old transaction sequence.
- Green: 74 affected unit/API tests and 26 following persistence tests passed.
- Full backend: `LUMIERE_RUN_PERSISTENCE=1 .venv/bin/python -m pytest -q --tb=short` from `backend`: 352 passed.
- Client regressions: `npm --prefix frontend test -- --runInBand`: 14 suites, 108 tests passed.
- Backend Ruff, Pyrefly (zero errors), import contracts, and `git diff --check` passed.
- Independent read-only review found no material issues; the reviewer checked the implementation, transaction lifecycle, regression tests, and design/plan consistency.
