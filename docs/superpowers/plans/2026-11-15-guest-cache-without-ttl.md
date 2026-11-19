# Guest Cache Without TTL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep validated guest identities in bounded memory until LRU eviction or worker restart.

**Architecture:** Remove clock/deadline state from GuestIdentityCache and retain its existing 10,000-entry OrderedDict LRU. Bootstrap and database fallback remain authoritative when invoked.

**Tech Stack:** Python, OrderedDict, pytest, existing Postgres fixtures.

**Spec:** `docs/superpowers/specs/2026-11-15-durable-guest-identity-design.md`, subsequent TTL-removal amendment approved in conversation.

## Global Constraints

- Preserve prior uncommitted changes. Do not read/write secrets or environment files.
- No identity/cookie/quota/schema change; cache keys are digests and values contain only profile ID.
- Database credential deletion may remain unobserved until eviction or worker restart, including indefinitely for hot entries.

## Review Focus

- LRU must continue bounding memory and revalidating evicted entries.
- Cold workers reject deleted credentials even while warm workers retain prior validation.
- Bootstrap limiter, current IP context and transaction-failure handling remain intact.

### Task 1: Remove cache TTL

**Files:** `application/guest_cache.py`, unit cache and persistence identity tests, README and current design documentation.

**Interface:** `GuestIdentityCache(max_entries: int = 10000)`; existing get/put signatures remain unchanged.

- [x] Change the old clock-controlled expiry test to expect continued warm validation after the old deadline; run and observe failure.
- [x] Remove clock/deadline state and obsolete clock fixtures/expiry tests. Test warm retention, cold-worker rejection and eviction-based revalidation.
- [x] Run the complete backend suite on isolated Postgres and lint/type/import checks; obtain fresh code review.
- [x] Update documentation and leave the verified changes reviewable in this worktree.

## Verification results

146 backend tests passed, including real Postgres eviction/restart checks. The controlled-clock regression was verified to fail against the former TTL implementation and pass against the capacity-only cache. Ruff, strict typing, architecture and whitespace checks passed. Fresh review found no remaining issues.
