# Single-statement Unfollow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the owner's approved simplification: one joined DELETE, with no Unfollow profile-existence check or profile lock.

**Architecture:** The removal port accepts public person identity and profile ID; the persistence adapter resolves membership through DELETE USING people. Follow retains its profile lock and cap enforcement. Commit, input validation, identity/origin resolution, rollback, and client queue stay intact.

**Tech Stack:** Existing Python, SQLAlchemy, PostgreSQL, pytest; no dependencies or migration.

**Spec:** ../specs/2026-11-23-F002-unfollow-people-design.md, with the owner-approved simplification amendment.

## Global Constraints

- Never read/write secrets or access the application database; use disposable PostgreSQL only.
- Delete only the requesting profile's selected provider identity, using bound parameters.
- Missing profile, person, or relationship is a successful no-op after guest identity resolution; missing/invalid credentials remain failures.
- Keep strict identity validation, empty 204/500 responses, awaited commit, and cancellation cleanup.
- Follow retains its profile lock around count-and-insert; concurrent Follow/Unfollow now follows database visibility rather than shared profile-lock order.
- No frontend changes or reconciliation requests.

## Review Focus

- Zero-match DELETE still issues exactly one statement and commits (parameterized persistence query-count test).
- Joined deletion scopes both profile and selected person, preserving unrelated timestamps (existing ownership/durability tests).
- Removing Unfollow's lock must not weaken Follow's three-person cap (existing concurrent Follow tests and sequential Follow/Unfollow cases).
- An uncommitted concurrent Follow may survive a completed Unfollow, as approved (event-gated persistence test).
- DELETE can still wait on a matching follow row; cancellation must preserve data and release resources (row-lock cancellation test).

### Task 1: Simplify removal and align contracts

**Files:** Following port/use case/persistence adapter/fake; unit, API, and persistence following tests; README, following architecture, and approved F002 designs.

**Interfaces:** Change `FollowingRepository.remove(profile_id: UUID, identity: PersonIdentity) -> None` (async) and both implementations. `UnfollowPerson.execute` validates identity, awaits remove, then commit. Follow APIs remain unchanged.

- [x] **Step 1: Write failing tests.** Replace missing-profile rejection with successful no-op; require only removal plus commit. Add API success after an already-resolved profile disappears. Parameterize an actual database query counter over present/absent profiles/persons and assert one DELETE USING people. Replace obsolete profile-lock serialization assertions with no-wait-on-profile-lock and uncommitted-follow visibility tests; preserve sequential ordering, cap, rollback, and row-lock cancellation coverage.
- [x] **Step 2: Run RED checks.** `uv --directory backend run pytest tests/unit/application/test_following.py tests/api/test_following.py -q` and `make test-integration`. Expected: new missing-profile/statement-count/nonblocking assertions fail against current implementation; no skipped persistence checks.
- [x] **Step 3: Implement.** Use a bound SQLAlchemy DELETE joining follows.person_id to people.id and filtering profile_id and people.tmdb_id. Suppress unnecessary ORM synchronization. Make the fake resolve identity within remove; remove Unfollow's profile lock and lookup. Amend docs for the approved policy and concurrency changes, preserving the historical completed plan.
- [x] **Step 4: Verify.** Run the focused backend checks, `make test`, `make lint`, `make test-integration`, `make generate`, generated-contract no-drift, and `git diff --check`. Expected: all green; generated HTTP contracts unchanged.
- [x] **Step 5: Commit.** `refactor: simplify unfollow to one joined delete`. Complete one fresh-context review of this follow-up range; fix material findings with failing regression tests. Preserve the local branch.

Authorization: the owner approved this exact simplification in the current conversation; continue inline without another handoff approval.

Execution: implemented inline under the owner's approval. RED: 4 focused unit/API and 10 persistence failures. GREEN: 74 focused unit/API, full `make test` (267 backend and 108 frontend), 80 disposable PostgreSQL tests, and deterministic contract generation with no drift. Sequential `make lint` passed; final fresh-context review pending. No frontend code or HTTP schema changed.
