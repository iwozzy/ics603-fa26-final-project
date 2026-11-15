# App-prefixed Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Namespace application environment variables under `LUMIERE_`.

**Architecture:** Configure Pydantic's prefix and rename Alembic's environment
lookup. Update Compose's explicit variable wiring and translate the operator's
site address to the existing Caddy variable.

**Tech Stack:** Pydantic Settings, Alembic, Docker Compose, pytest, Expo/Caddy.

**Spec:** `docs/superpowers/specs/2026-11-15-prefixed-configuration-design.md`

## Global Constraints

- Keep defaults, validation, explicit migrations, and environment loading behavior unchanged.
- Do not read or modify local environment files.
- Preserve tool-defined `OTEL_*`, `POSTGRES_*`, and `EXPO_*` names.
- Historical design and implementation documents retain their original names.

## Review Focus

- Unprefixed ambient variables must not override app settings.
- Required prefixed variables must not silently fall back to unprefixed ones.
- Compose must propagate the names Settings actually consumes.
- Alembic's migration environment must match the isolated stack.
- Caddy must receive its existing variable from the newly prefixed operator input.

### Task 1: Prefix the runtime configuration contract

**Files:** `backend/src/lumiere/config.py`, `backend/migrations/env.py`,
`backend/tests/unit/test_config.py`, `compose.yaml`, `compose.test.yaml`,
`.env.example`, `README.md`, `e2e/Dockerfile`, `e2e/support/tmdb-server.ts`.

**Interfaces:** Python Settings field names stay unchanged. All application env
names gain `LUMIERE_`; Compose maps `LUMIERE_SITE_ADDRESS` to `SITE_ADDRESS`.

- [x] Update config tests to use prefixed inputs; verify generic ambient names
  cannot satisfy required fields or override the configured cache lifetime.
- [x] Run `uv --directory backend run pytest tests/unit/test_config.py -q`;
  expect failures because Settings does not yet consume prefixed inputs.
- [x] Set `env_prefix="LUMIERE_"`; rename Alembic's lookup, Compose variables,
  example names, and README references. Keep Caddy's internal name unchanged.
- [x] Run `make test` and `make lint`; expect green results.
- [x] Render both Compose stacks with controlled synthetic environment inputs;
  assert backend values and Caddy mapping. Run isolated integration/browser
  checks if Docker is available. Review the full diff for remaining old names.

## Execution record

- Existing linked worktree on `feature/brainstorming/F001-search-people`; clean baseline.
- Default uv cache is outside writable roots; use `UV_CACHE_DIR=/private/tmp/lumiere-uv-cache`.
- Execute inline under the user's instruction to proceed. Leave the changes
  available for review in this worktree without committing or publishing.
- Baseline: 88 backend tests and 34 frontend tests passed.
- Config RED: six failures from missing prefixed lookup; GREEN: all ten config tests passed.
- Full suite: 91 backend tests and 34 frontend tests passed; lint/type/architecture checks passed.
- Synthetic Compose rendering passed for defaults, overrides, standard tool names,
  Caddy mapping, and isolated stack settings. Isolated persistence suite: nine passed.
- Independent read-only review found no critical/important issues and one
  remaining test-fixture variable. Included its rename to complete app-owned
  naming consistently; browser checks exercise the image/consumer contract.
- Preserved the existing provider-base-URL forwarding and HTTPS port behavior;
  changing either would exceed the namespace change and alter existing loading/deployment behavior.
- Browser suite: seven passed; actual Alembic migration and fixture image startup succeeded.
- Dedicated cache-expiry browser check: one passed with the test-only 10-second
  lifetime. Both browser runs removed their isolated containers and networks.
- E2E TypeScript check and final `git diff --check` passed. Task 1 complete;
  changes remain uncommitted for review.
