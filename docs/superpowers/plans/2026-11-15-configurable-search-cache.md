# Configurable Search Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Configure successful search cache lifetimes and run expiry checks with 10 seconds.

**Architecture:** Settings supplies a positive integer to HttpServices through build_container. The dedicated npm expiry script sets a test-only Compose interpolation variable.

**Tech Stack:** Python, Pydantic Settings, FastAPI, Docker Compose, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-15-configurable-search-cache-design.md`

## Global Constraints

- Default 300 seconds; expiry test 10 seconds, waiting 12 real seconds.
- Preserve private caching, empty success caching, no-store failures, and normal browser tests.
- Do not read or write secrets.

## Review Focus

- Settings must accept lifetimes above 10,000 seconds and reject nonpositive values.
- Environment overrides must reach the HTTP response through production composition.
- Dedicated expiry settings must not change normal browser tests.
- An immediate repeat must reuse the response before expiry.
- CI descriptions and runtime documentation must reflect the shorter test.

### Task 1: Configure lifetime and shorten expiry check

**Files:** Modify `backend/src/lumiere/config.py`, `backend/src/lumiere/bootstrap.py`, `backend/src/lumiere/adapters/inbound/http/deps.py`, `backend/src/lumiere/adapters/inbound/http/routers/v1/people.py`, `compose.yaml`, `compose.test.yaml`, `e2e/package.json`, `e2e/tests/cache.spec.ts`, `.github/workflows/ci.yml`, `README.md`. Add `backend/tests/unit/test_config.py` and extend `backend/tests/api/test_people.py`.

**Interfaces:** Settings.search_cache_max_age_seconds and HttpServices.search_cache_max_age_seconds, positive integer/default 300; runtime env SEARCH_CACHE_MAX_AGE_SECONDS; isolated Compose override LUMIERE_TEST_SEARCH_CACHE_MAX_AGE_SECONDS.

- [x] Add failing tests for the default, environment overrides (10 and 10001), invalid lifetimes, and configured headers on normal/empty success.
- [x] Run focused tests and confirm missing configuration fails.
- [x] Implement the setting, composition wiring, headers, and Compose options.
- [x] Update expiry test to assert max-age=10, confirm immediate reuse, wait 12 seconds, then confirm another dispatch; use a bounded 40-second timeout.
- [x] Update npm expiry script, CI wording, and README.
- [x] Run backend suite/checks, e2e typecheck, regular browser tests and expiry command; inspect diff and obtain review.

Execution: proceed in the existing isolated worktree as authorized by the user's request. Leave changes available for review without committing.

## Verification

- Existing baseline: 77 backend tests passed.
- New focused tests: 11 failed before implementation, then 11 passed.
- Backend suite: 88 passed.
- Ruff, Pyrefly, import contracts, and e2e TypeScript checks passed.
- Regular browser suite: 7 passed using the default 300 seconds.
- Dedicated browser expiry test: 1 passed; test body 13.2 seconds, including 12 real seconds of waiting.
- Independent code review: no findings.
