# Durable Guest Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Preserve guest identity through a persistent renewable cookie and charge quotas to the durable profile.

**Architecture:** Opaque cookie digest resolves a durable guest profile through bounded memory cache/Postgres. Bootstrap renews cookie persistence. A migration converts sessions to credentials and aggregates session usage into profile-based guest counters.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest, existing browser suite.

**Spec:** `docs/superpowers/specs/2026-11-15-durable-guest-identity-design.md`

## Global Constraints

- Preserve prior uncommitted changes. Do not read or write secrets or environment files.
- Keep public endpoint, cookie name, OpenAPI and `SESSION_*` configuration compatible.
- Cookie Max-Age is 31536000 seconds and is renewed at each successful bootstrap.
- Profiles and credential mappings do not expire. Cache TTL remains 60 seconds.
- Per-guest quotas use profile ID; global/IP protection and atomic charging remain unchanged.
- Migration preserves profiles, digests and recorded usage; coordinated deployment stops old writers.

## Review Focus

- Returning with an old valid cookie must recover the same profile even after the former 24-hour expiry.
- Renewing cookie persistence or using another credential for the same profile must not reset guest budgets.
- Migration must aggregate all mapped quota windows without affecting global/IP counters or losing orphan history.
- Unknown/missing credentials may create a new identity only through throttled bootstrap; resolution still fails closed.
- Bootstrap failure must not set a cookie or publish a cache-authorized identity; search responses must not rotate cookies.

### Task 1: Persistent guest credentials and profile-owned quotas

**Files:** Update guest domain/ports/service/cache, persistence model/repositories/UoW, bootstrap/HTTP dependency wiring and cookie response, access fakes/tests. Add `0003_durable_guests.py` and durable identity/migration tests. Update README. Rename internal identity modules/types where appropriate; preserve public transport names.

**Interfaces:** `GuestContext(profile_id: UUID, ip_key: str)`; `StoredGuestIdentity(profile_id: UUID)`; `GuestBootstrap(context, proof, is_new)`. `GuestIdentityRepository.find(token_digest: bytes) -> StoredGuestIdentity | None`; `create(profile_id: UUID, token_digest: bytes) -> None`. `GuestIdentityCache.get(digest: bytes) -> StoredGuestIdentity | None`; bootstrap/resolve preserve their HTTP-facing arguments.

- [x] Write failing tests for persistent cookie renewal and returning identity after 48 hours/year; run against the current implementation and observe expiry failures.
- [x] Add real-Postgres migration tests for old/expired credentials, aggregated minute/day/total usage, multiple credentials, orphan counters and downgrade/re-upgrade; observe expected missing-migration failures.
- [x] Implement domain, cache/service, persistence, profile admission and migration changes, preserving public API/configuration compatibility.
- [x] Adapt prior expiry-oriented tests to durable identity and keep cache, current-IP, outage, concurrent quota, accounting, rollback and bootstrap-limit coverage.
- [x] Run complete backend tests on migrated disposable Postgres; run lint/type/import/OpenAPI checks and composed browser flows.
- [x] Update README, obtain fresh read-only code review, fix material findings, and leave verified work reviewable in the existing worktree.

## Verification results

151 backend tests passed on the migrated disposable database; seven composed browser tests passed. Ruff, strict typing, architecture contracts, OpenAPI equality and diff whitespace checks passed. Fresh read-only code review found no issues. Hosted deployment requires stopped application writers, migration through 0003, and starting the matching backend. Browser retention remains subject to browser policy and user deletion.
