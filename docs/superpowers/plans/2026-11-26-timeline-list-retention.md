# Timeline List Retention Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this small change in the current worktree.

**Goal:** Reduce return-navigation flicker without waiting for refresh.

**Architecture:** Retain the list across focus changes and key it only by guest identity. Preserve focus-generation guards and asynchronous store entry; reset per-visit gesture bookkeeping if required.

**Tech Stack:** React, Expo Router, React Native FlatList, Jest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-26-timeline-list-retention-design.md`

## Global Constraints

- Returning must show cached movies immediately without waiting for refresh.
- Inactive or obsolete callbacks must not mutate the timeline.
- Guest changes must still discard the old list.
- Keep refresh and pagination contracts unchanged.

## Review Focus

Pending refresh, stale callbacks, identity changes, deep anchors, and gesture
latches surviving blur are covered by the tests or browser checks below.

### Task 1: Retain the list and verify route return

**Files:** `frontend/src/adapters/inbound/ui/TimelineScreen.tsx`, `TimelineList.tsx` if gesture cleanup is needed, and `TimelineScreen.test.tsx` in the same directory.

**Interfaces:** Keep the existing `TimelineList` props and `TimelineStore` API.

- [x] Add a failing test that the existing FlatList instance and cached movie survive blur and return while the refresh remains pending. Cover inactive callbacks and guest replacement.
- [x] Run `npm --prefix frontend test -- --runInBand TimelineScreen`; confirm the retention regression fails on the current remount.
- [x] Remove focus-driven unmounting and key changes, and explicitly reject callbacks before first focus and while inactive. Reset gesture state per focus if a regression demonstrates that need.
- [x] Preserve deep-anchor coverage and test edge input after returning.
- [x] Run `npm --prefix frontend test -- --runInBand`, `npm --prefix frontend run typecheck`, and `npm --prefix frontend run lint`; expect all to pass.
- [x] Build the web app locally and compare repeated returns with delayed mock API responses, including scrolling before completion. Review the final diff and leave the change available for the user to try.

## Task 1 results

All 190 frontend tests, typecheck, lint, web export, and whitespace checks pass.
A fresh reviewer verified the gesture lifecycle fix with no remaining important
findings. With a 700 ms mock refresh, the final browser Back check displayed the
cached movie after 18 ms and held its exact offset across 60 sampled frames;
scrolling before refresh completion also retained the new position. Sidebar
navigation can still create a new route and briefly flicker during initial
virtualization. A minor possibility of retained last-row footer padding is
deferred. Changes are uncommitted for local evaluation.

### Task 2: Reuse the timeline route on sidebar return

**Files:** `frontend/src/app/_layout.tsx`, `e2e/tests/timeline-navigation.spec.ts`.

- [x] Add and run a browser regression with mocked API data: repeated sidebar returns must retain the actual scroll node and visible anchor before a gated refresh completes. Verify Back and Forward URLs and restored content.
- [x] Confirm the browser regression fails before changing the layout.
- [x] Add `Stack.Screen name="timeline" dangerouslySingular` to the existing stack.
- [x] Run the browser regression against the rebuilt web app, plus frontend tests, typecheck, lint and e2e typecheck. Leave changes uncommitted.

## Task 2 results

The browser regression fails on the original layout because the first sidebar
return creates a different scroll node. With the singular timeline screen it
passes three alternating sidebar returns, checking node identity and ten
visible-anchor samples per return while the API response remains gated. The
visible offset also survives response completion and browser Back/Forward.
All 190 frontend tests, frontend and e2e typechecks, frontend lint, web export,
and whitespace checks pass. Browser checks used a separate local build and
mocked API responses; the running application was not changed.
