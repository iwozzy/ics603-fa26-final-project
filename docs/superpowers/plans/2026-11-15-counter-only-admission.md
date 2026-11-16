# Counter-Only Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce and charge quotas before dispatch with no reservation ledger or post-provider writes.

**Architecture:** One JSONB-only Postgres function atomically checks/increments all counters inside an application-owned transaction. Search invokes the provider after commit and performs no outcome accounting.

**Tech Stack:** Python, SQLAlchemy, Alembic, PostgreSQL, pytest and existing browser suite.

**Spec:** `docs/superpowers/specs/2026-11-15-counter-only-admission-design.md`

## Global Constraints

- Preserve prior uncommitted identity/cache/admission work and existing transport/configuration contracts.
- Do not read or write secrets or environment files.
- Preserve all nine atomic caps, fail-closed admission, conservative ambiguous-commit behavior and provider deadlines.
- User approved dropping existing outcome history; migration downgrade recreates an empty ledger without changing counters.

## Review Focus

- Provider success, exception and cancellation must leave all charges durable with no post-provider storage access.
- Removing a returned reservation ID must not change concurrency admission counts or quota rejection.
- Function/table migration must preserve counters and remain downgrade-compatible with earlier migrations.
- Deadline cancellation must propagate promptly without settlement tasks.
- Existing guest identity and LRU cache behavior must remain intact.

### Task 1: Remove reservations and outcome settlement

**Files:** Usage/domain/search/persistence/bootstrap files and fakes; charged-search, atomic admission, migration, search and deadline tests; add migration 0004; update README and spec amendment.

**Interfaces:** `UsageAdmission.admit_and_charge(context: GuestContext, now: datetime) -> None`; `UsageRepository.admit_and_charge(limits: Mapping[CounterKey, int]) -> bool`; database function `lumiere_admit_and_charge(limits jsonb) RETURNS boolean`.

- [x] Write and run failing tests showing no database work is allowed after provider entry for success/failure/cancellation.
- [x] Add a migration test for dropped table/history, unchanged counters and restored old function on downgrade; observe missing-migration failure.
- [x] Remove reservation/outcome types and APIs, settlement tasks/shutdown ownership, and table model; implement counter-only migration and update fakes/tests.
- [x] Verify complete backend suite on disposable migrated Postgres, lint/type/import/OpenAPI checks and browser flows.
- [x] Document destructive audit-history removal and coordinated migration; obtain fresh code review, resolve material findings, leave work reviewable.

## Verification results

143 backend tests passed on migrated disposable Postgres; seven composed browser tests passed. Ruff, strict typing, import contracts, OpenAPI equality and diff whitespace checks passed. Fresh scoped review found no issues. Migration 0004 intentionally deletes existing per-attempt history; counters survive upgrade/downgrade, and the migration requires stopped writers and matching backend deployment.
