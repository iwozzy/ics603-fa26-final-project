# Sidebar Screen Retention Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans in the existing worktree.

**Goal:** Reuse all sidebar destinations and preserve Search state on return.

**Architecture:** Add singular stack entries for Search (`index`) and Following. Remove Search's blur reset while preserving hook-level clear and unmount cancellation.

**Tech Stack:** React, Expo Router, Jest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-26-sidebar-screen-retention-design.md`

## Constraints and review focus

- Existing timeline work must be committed first; done as `f487282`.
- Keep existing URLs and nonblocking focus refreshes.
- Preserve completed results, draft edits, and pending-search completion across sidebar navigation.
- Clearing, reload and unmount still discard the appropriate local state or work.
- Verify mixed browser history and membership refresh; no API or dependency changes.

### Task 1: Retain Search and Following

**Files:** `frontend/src/app/_layout.tsx`, `frontend/src/adapters/inbound/ui/SearchPeopleScreen.tsx`, its existing test, and `e2e/tests/sidebar-navigation.spec.ts`.

Also update the existing navigation assertions in `e2e/tests/follow-people.spec.ts`
and the current behavior descriptions in README and the search/follow architecture docs.

- [x] Add failing unit tests for completed and pending Search across blur/refocus; confirm current reset loses state.
- [x] Add a browser regression for Search and Following reuse, draft/result retention, pending completion while away, Back/Forward, clearing and reload; run it against the existing build and confirm failure.
- [x] Add singular `index` and `following` screen entries and remove only Search's blur-reset wiring.
- [x] Run all frontend tests, frontend typecheck/lint, e2e typecheck and web export; run the new browser regression and the existing timeline-navigation regression against the separate mocked local build.
- [x] Review the final diff and report the initial commit separately from the new implementation.

## Results

The prior timeline changes were committed as `f487282` before new work began.
The new implementation passes all 192 frontend tests, both typechecks, frontend
lint, web export and whitespace checks. All 29 affected search, follow, unfollow,
sidebar and timeline-navigation browser tests pass against the isolated Docker
test stack. The standalone mocked browser run also passed all three navigation
regressions. A fresh reviewer found no remaining important issues after updating
the old reset-on-return test and current behavior documentation. New changes are
left uncommitted, separate from the initial checkpoint.
