# Usage Flush Function Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each accounting batch with one database function call.

**Architecture:** A PostgreSQL function owns checkpoint locking and counter
updates inside the existing unit-of-work transaction. The repository retains
validation and maps returned rows to counter counts.

**Tech Stack:** PostgreSQL 18, PL/pgSQL, Alembic, SQLAlchemy, psycopg, pytest.

**Spec:** `docs/superpowers/specs/2026-11-18-usage-flush-function-design.md`

## Global Constraints

- Keep the existing `flush_charges` interface and unit-of-work commit ownership.
- Downgrade removes only the function; counters and checkpoints survive.
- Do not read local configuration or credentials or apply migrations to an application database.

## Review Focus

- ORM commit must not emit another checkpoint update after the function call.
- Duplicate concurrent calls must apply a batch once.
- Invalid sequences must retain the existing ValueError contract.
- Writer sequences beyond int32 must work through typed bigint parameters.
- Migration roundtrips must preserve counters and checkpoint state.

### Task 1: Implement and verify the function-backed repository

**Files:**
- Create: `backend/migrations/versions/0006_usage_flush_function.py`
- Modify: `backend/src/lumiere/adapters/outbound/persistence/repositories.py`
- Test: `backend/tests/integration/persistence/test_usage_flush_function.py`
- Reuse: `backend/tests/integration/persistence/test_async_usage.py`

**Interfaces:**
- Consumes: existing writer UUID, sequential batch number, and CounterKey deltas.
- Produces: `lumiere_flush_charges(uuid, bigint, jsonb) RETURNS SETOF usage_counters` and the unchanged repository `dict[CounterKey, int]` result.

- [x] Add real-database tests for a single statement through commit on new and duplicate batches, bigint sequences, older-sequence rejection, concurrent different writers with reversed input order, and migration data preservation.
- [x] Run the new tests against the old implementation. Expect failures for multiple statements and the missing migration.
- [x] Implement the forward migration and replace the repository's statements with a typed function call; preserve sequence errors by rejecting an empty function result in Python, and refresh retained ORM rows.
- [x] Run `LUMIERE_RUN_PERSISTENCE=1 backend/.venv/bin/python -m pytest backend/tests/integration/persistence -q`. Expect all tests to pass.
- [x] Run `backend/.venv/bin/python -m pytest backend/tests -q`, backend ruff, pyrefly, and import-linter. Expect tests/checks to pass; database tests run separately above.
- [x] Review the diff and record verification results. Leave changes available for user review in the existing worktree.

## Verification results

The initial tests observed four statements for a new batch and three for a
duplicate, and failed for the missing migration. The first implementation
passed all 44 persistence tests. Independent review identified retained ORM
instances returning stale counts and sequence rejection aborting the caller's
transaction. Four additional regression cases reproduced these problems and
an out-of-bigint sequence becoming a storage error. The final implementation
refreshes ORM instances and rejects invalid sequences in Python.

Final verification: `LUMIERE_RUN_PERSISTENCE=1 backend/.venv/bin/python -m pytest
backend/tests -q --tb=short` passed all 180 tests. Backend ruff, pyrefly, import
contracts, and `git diff --check` passed. Only the disposable test database was
migrated; application rollout requires `make migrate` before backend restart.
