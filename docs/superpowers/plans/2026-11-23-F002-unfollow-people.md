# F002 Unfollow People Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete F002 with durable, idempotent unfollowing and optimistic removal from Following using Search's existing action interactions.

**Architecture:** Extend existing following ports, async profile-locked transactions, and the shared serial mutation queue. Track ordered follow/unfollow intents over confirmed state; successful DELETE updates confirmed state locally without a reconciliation GET. Extract common person-action UI so both screens share reveal behavior and styling.

**Tech Stack:** Existing Python/FastAPI, async SQLAlchemy/PostgreSQL, TypeScript, Expo/React Native Web, pytest, Jest, and Playwright; no new dependencies or migration.

**Spec:** [Approved F002 unfollow design](../specs/2026-11-23-F002-unfollow-people-design.md), amending [F002 follow people](../specs/2026-11-23-F002-follow-people-design.md).

## Global Constraints

- Use `DELETE /api/v1/following` with `provider` and `provider_id` in the JSON body.
- Removal is idempotent and returns `204 No Content` on success.
- Match Search's Follow + / Following styling and hover/tap behavior.
- Activating Unfollow immediately removes the person optimistically.
- Extend the shared mutation queue; do not add a post-deletion refresh.
- Keep the existing Expo/React Native client, FastAPI backend, ports and adapters, guest identity, three-person limit, and durable `follows` table. No migration is needed.
- Preserve empty `500` failures for invalid input, origin, session, storage, or deadline errors.
- Never read or write secrets or use the application database. Use fixture providers and disposable databases; no live provider calls.
- Preserve startup/Following-entry reads, blank initial/empty/error Following, guest-generation guards, manual retries, independent search caching, and newest-first ordering.

## Review Focus

- A DELETE may commit before response delivery fails: restore locally, perform no GET/retry, and permit a safe manual repeat (Tasks 2–4, 6).
- Follow/unfollow/follow of one person can be outstanding together: settlement removes one operation, preserving later intent and order (Task 4).
- Removal can fail after a replacement follow was accepted at three: restore the original, retain the queued replacement until settlement, and block further additions (Tasks 4, 6).
- Navigation or a new guest can arrive during DELETE/bootstrap: navigation preserves work; new identity aborts/discards it and ignores late responses (Tasks 3–4, 6).
- Removing a keyboard-focused row destroys its DOM node: rollback restores keyboard access without stealing focus from another control; hidden touch targets never submit on first tap (Tasks 5–6).

---

## File and responsibility map

- Backend following use-case/port/repository modules own removal, profile locking, and commit; existing unit-of-work and schema stay intact.
- HTTP router, services, bootstrap, error boundary, telemetry, exporter, and generated contracts expose DELETE and its empty success.
- Frontend repository/use case own DELETE transport; `FollowingStore` owns chronological intent projection and settlement.
- New `PersonActionRow.tsx` and `PersonActionList.tsx` own shared input/reveal behavior and selection. Existing Search and Following components choose the available action.
- Existing following test modules cover each layer; a new `e2e/tests/unfollow-people.spec.ts` owns real-browser unfollow scenarios. README and existing F002 documents describe the resulting feature.

### Task 1: Durable unfollow use case and repository

**Files:** Modify `backend/src/lumiere/application/ports/following.py`, `backend/src/lumiere/application/use_cases/following.py`, `backend/src/lumiere/adapters/outbound/persistence/following_repository.py`, `backend/tests/fakes/following.py`, `backend/tests/unit/application/test_following.py`, and `backend/tests/integration/persistence/test_following.py`.

**Interfaces:**
- Produce `UnfollowPersonPort.execute(identity: PersonIdentity, context: GuestContext) -> None` (async).
- Produce `UnfollowPerson(factory: FollowingUnitOfWorkFactory)` implementing that port.
- Extend `FollowingRepository` and both implementations with async `remove(profile_id: UUID, person_id: int) -> None`.
- Consume existing `lock_profile`, `find_person`, and unit-of-work commit/rollback; keep `GUEST_FOLLOW_LIMIT = 3` and existing follow/list return types.

- [x] **Step 1: Add failing unit and persistence tests.** Name unit cases `test_unfollow_commits_only_owned_relationship`, `test_unfollow_absent_relationship_and_person_are_idempotent`, `test_unfollow_rejects_missing_profile`, and `test_unfollow_commit_failure_preserves_membership`. Parameterize existing invalid identity/provider cases over follow and unfollow. Assert lock precedes removal and commit, no count/add/list is needed, and unrelated memberships/timestamps are unchanged. Representative assertions after seeding two profiles following person 4139:

  ```python
  assert await UnfollowPerson(store).execute(identity(), context) is None
  assert (context.profile_id, 4139) not in store.memberships
  assert (other.profile_id, 4139) in store.memberships
  assert store.operations.index('lock_profile') < store.operations.index('remove') < store.operations.index('commit')
  ```

  Add persistence cases `test_unfollow_survives_fresh_engine`, `test_unfollow_rollback_and_cancel_restore_relationship`, and `test_follow_and_unfollow_share_profile_lock`. Force both serial orders at the cap with explicit transaction/event gates: deletion first permits a replacement; follow first rejects a fourth, then deletion leaves two. Also force same-person follow/delete in both orders and assert the last committed action determines membership. While deletion waits on the profile lock, an unrelated async read must complete; cancellation must release resources and preserve data. Use existing `following_uows`, `seed`, and disposable engine patterns.
- [x] **Step 2: Run red checks.** `uv --directory backend run pytest tests/unit/application/test_following.py -q`, then `make test-integration`. Expect missing unfollow/removal behavior; skipped persistence tests do not count.
- [x] **Step 3: Implement the interfaces.** Validate before opening storage, using follow's exact provider/strict safe-integer policy. Lock and verify the profile before lookup. Remove only the owned relationship if a local person exists; absent person/membership is successful. Commit even for the idempotent no-op. Use an awaited SQLAlchemy `delete` with both profile/person predicates and existing async cancellation cleanup. Extend the fake's transaction-local membership copy so rollback remains meaningful.
- [x] **Step 4: Repeat Step 2.** Expect all affected unit and full disposable persistence tests to pass without schema changes or provider work.
- [x] **Step 5: Commit the Task 1 files.** Suggested message: `feat: persist idempotent unfollow operations`.

### Task 2: DELETE HTTP contract, wiring, and telemetry

**Files:** Modify `backend/src/lumiere/adapters/inbound/http/routers/v1/following.py`, `backend/src/lumiere/adapters/inbound/http/deps.py`, `backend/src/lumiere/adapters/inbound/http/errors.py`, `backend/src/lumiere/main.py`, `backend/src/lumiere/bootstrap.py`, `backend/src/lumiere/observability.py`, `backend/scripts/export_openapi.py`, `backend/tests/api/conftest.py`, `backend/tests/api/test_following.py`, `backend/tests/unit/test_observability.py`, `backend/tests/unit/test_people_lifecycle.py`, and `backend/tests/unit/test_accounting_lifecycle.py`. Regenerate `openapi.json` and `frontend/src/adapters/outbound/api/generated/`.

**Interfaces:**
- Consume Task 1's `UnfollowPerson`/`UnfollowPersonPort`; add required keyword-only `HttpServices.unfollow_person: UnfollowPersonPort`.
- Register DELETE `/api/v1/following`, operation ID `unfollowPerson`, body `FollowPersonRequest`, returning an explicit empty `Response(status_code=204, headers={'Cache-Control': 'no-store'})` after awaiting the use case. Reuse the strict existing request schema.
- Produce `ObservedUnfollowPerson(inner: UnfollowPersonPort).execute(identity: PersonIdentity, context: GuestContext) -> None` (async), spans `following.unfollow` and `http.following.unfollow`.

- [x] **Step 1: Add failing API/telemetry tests.** `test_delete_following_is_empty_204_and_idempotent` seeds a follow and calls `api.client.request('DELETE', '/api/v1/following', json=body)` twice, then with a valid absent identity. Assert status `204`, content `b''`, no JSON content type, `cache-control == 'no-store'`, and only the requesting profile is changed. Extend invalid body/origin/missing-session/commit-failure tests to DELETE, including undecodable bytes and malformed JSON, expecting empty `500` with no-store. Add an event-gated commit test proving no response before commit, not merely before entering the use case. Assert failures retain memberships and cause no provider queries/admission. Extend OpenAPI assertions to operation `unfollowPerson`, responses exactly `{'204', '500'}`, required JSON body, and no content on `204`. Telemetry tests assert distinct DELETE span names, finite categories, and absence of request/body/identity/raw-error data.
- [x] **Step 2: Run `uv --directory backend run pytest tests/api/test_following.py tests/unit/test_observability.py -q`.** Expect missing DELETE/telemetry contract failures.
- [x] **Step 3: Implement the contract and composition.** Reuse guest resolution/origin checks, fresh application-pool following UoWs, and existing seven-second boundary. Extend undecodable-JSON HTTP 400 normalization from POST to POST/DELETE; preserve other routes. Classify HTTP following spans by explicit GET/POST/DELETE mapping. Extend observed services and every `HttpServices(...)` construction found by `rg`, including inert export services and lifecycle tests. Remove DELETE's default OpenAPI 422. Run `make generate`; generated files are never edited manually.
- [x] **Step 4: Run `uv --directory backend run pytest tests/unit tests/api tests/integration/clients -q` and `make lint`.** Expect backend/API/architecture checks and unchanged frontend contracts to pass. Verify generated DELETE has empty success and the reusable strict identity schema remains available.
- [x] **Step 5: Commit the Task 2 files and generated contracts.** Suggested message: `feat: expose no-content unfollow endpoint`.

### Task 3: Frontend unfollow port and transport

**Files:** Create `frontend/src/application/use-cases/unfollow-person.ts`. Modify `frontend/src/application/ports/following-repository.ts`, `frontend/src/application/use-cases/following.test.ts`, `frontend/src/adapters/outbound/api/following-repository.ts`, `frontend/src/adapters/outbound/api/following-repository.test.ts`, and `frontend/src/test-utils/fakes/following.ts`.

**Interfaces:**
- Produce `FollowingRepository.unfollow(identity: PersonIdentity, signal: AbortSignal): Promise<void>`.
- Produce `UnfollowPerson(repository: FollowingRepository).execute(identity: PersonIdentity, signal: AbortSignal): Promise<void>` as a framework-free delegating use case.
- Extend `DeferredFollowing` with `unfollowCalls`, whose entries contain identity, signal, `resolve(): void`, and `reject(error: Error): void`; retain existing list/follow call APIs.

- [x] **Step 1: Add failing transport/delegation tests.** Assert exact DELETE URL, JSON identity-only body, same-origin credentials, JSON content type, and abort signal. A response `{ok: true, status: 204, json: jest.fn(() => { throw new Error('must not parse'); })}` must succeed without calling `json`. Reject unexpected success statuses, non-success, deadline/abort, invalid identity, and bootstrap failure as `FollowingFailed`; ensure no retry, GET, or readiness invalidation. A cancellation or new guest notification during bootstrap must prevent obsolete DELETE dispatch through the store guard in Task 4. Update typed repository mocks with `unfollow`, and assert delegation preserves signal and errors.
- [x] **Step 2: Run `npm --prefix frontend test -- --runInBand src/application/use-cases/following.test.ts src/adapters/outbound/api/following-repository.test.ts`.** Expect missing unfollow interface/use-case behavior.
- [x] **Step 3: Implement the interfaces.** Validate outgoing identity using generated `zFollowPersonRequest`, reuse shared guest bootstrap and eight-second `withDeadline`, then require status `204` without body parsing. Factor only shared transport mechanics needed to preserve existing GET/POST mapping and list-only invalidation behavior. Keep generated imports confined to the adapter.
- [x] **Step 4: Repeat Step 2 and run `npm --prefix frontend run typecheck`.** Expect affected tests and all typed mocks to pass; do not change existing GET/POST behavior.
- [x] **Step 5: Commit the Task 3 files.** Suggested message: `feat: add frontend unfollow transport`.

### Task 4: Ordered optimistic follow/unfollow store

**Files:** Modify `frontend/src/application/following-store.ts`, `frontend/src/application/following-store.test.ts`, `frontend/src/bootstrap/container.ts`, `frontend/src/test-utils/renderWithPorts.tsx`, and constructor call sites in `frontend/src/adapters/inbound/ui/FollowingProvider.test.tsx`, `FollowingScreen.test.tsx`, `SearchResults.test.tsx`, and `SearchPeopleScreen.test.tsx`.

**Interfaces:**
- Consume Task 3's `UnfollowPerson` and deferred unfollow calls.
- Change constructor to `FollowingStore(list: ListFollowing, follow: FollowPerson, unfollow: UnfollowPerson, sessions: GuestSessionRepository)`; update every `new FollowingStore` construction.
- Produce `requestUnfollow(person: PersonSummary): boolean`, synchronous like `requestFollow`, accepting only active, known, currently projected membership.
- Keep public `FollowingViewState.confirmed`, `pending`, `people`, `phase`, and `canFollow`; derive `pending` as unique projected pending follow additions. Internally use `FollowingIntent = { readonly id: number; readonly kind: 'follow' | 'unfollow'; readonly person: PersonSummary }`, identifying settlements by operation ID rather than person identity.

- [x] **Step 1: Write failing store tests.** Add `unfollow_removes_immediately_and_204_confirms_without_get`, `unfollow_failure_restores_original_order`, `mixed_intents_keep_click_order_for_same_identity`, `unfollow_pending_follow_does_not_resurrect_on_earlier_success`, and `failed_removal_at_cap_preserves_queued_replacement`. Representative immediate assertions after `ready(3, 2, 1)`:

  ```typescript
  expect(store.requestUnfollow(person(2))).toBe(true);
  expect(store.getSnapshot().people.map(p => p.providerId)).toEqual([3, 1]);
  expect(store.getSnapshot().canFollow).toBe(true);
  expect(store.requestUnfollow(person(2))).toBe(false);
  ```

  Resolve/reject deferred requests separately. For follow A → unfollow A → follow A, expect serial dispatch kinds in exactly that order and visible A throughout the final pending follow. For failed deletion plus pending replacement, expect the original restored alongside provisional replacement, `canFollow === false`, then restoration to the original three when replacement is rejected. Include initial/inactive rejection, full rollback order, duplicate identity, failed earlier follow followed by deletion, multiple different removals, successful DELETE removing only its confirmed identity, no GET/retry on loss, and a later explicit idempotent retry. Extend existing stale-read/revision, refresh-failure, start/stop/restart, navigation, readiness, and new-guest tests to active/queued DELETE and guest creation during `ensure`.
- [x] **Step 2: Run `npm --prefix frontend test -- --runInBand src/application/following-store.test.ts`.** Expect missing requestUnfollow and mixed-intent failures.
- [x] **Step 3: Implement ordered projection and settlement.** Keep outstanding intents in click order, including the active request. Compute projected membership by replaying intents over confirmed people: follow inserts an absent identity at the front; unfollow removes that identity. Successful POST replaces confirmed with its full snapshot; successful DELETE removes that identity from confirmed; failure leaves confirmed unchanged. Remove only the settled operation, replay remaining intents, and send the next. Do not coalesce opposite intents, key completion by person identity, or add reconciliation. Increment revision on acceptance and settlement; retain epoch/generation checks and abort cleanup. Gate additions on known state and projected count `< confirmed.limit`, including after rollback. Wire the new use case using the existing shared repository/session instance.
- [x] **Step 4: Run all frontend tests, typecheck, and lint.** Commands: `npm --prefix frontend test -- --runInBand`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`. Expect existing follow semantics and constructor consumers to pass alongside mixed-intent tests.
- [x] **Step 5: Commit the Task 4 files.** Suggested message: `feat: queue optimistic follow and unfollow intents`.

### Task 5: Shared reveal actions and Following integration

**Files:** Create `frontend/src/adapters/inbound/ui/PersonActionRow.tsx` and `PersonActionList.tsx`. Modify `SearchResults.tsx`, `FollowingScreen.tsx`, `useFollowing.ts`, `SearchResults.test.tsx`, and `FollowingScreen.test.tsx` in that same directory. Delete `SearchPersonRow.tsx` after moving its behavior into the shared row.

**Interfaces:**
- Produce `PersonAction = 'follow' | 'following' | 'unfollow' | 'hidden'` exported by `PersonActionRow.tsx`.
- Produce `PersonActionRow({ person, rowId, action, touchSelected, onTouchSelect, onActivate })`, with `person: PersonSummary`, `rowId: string`, `action: PersonAction`, `touchSelected: boolean`, `onTouchSelect(rowId: string): void`, and `onActivate(person: PersonSummary): void`.
- Produce `PersonActionList({ people, resultSetKey, actionFor, onActivate, rowIdFor, testIdFor })`, with `people: readonly PersonSummary[]`, `resultSetKey: string`, `actionFor(person: PersonSummary): PersonAction`, `onActivate(person: PersonSummary): void`, and both ID callbacks `(person: PersonSummary, position: number): string`.
- `useFollowing()` adds `unfollow: store.requestUnfollow`; Following uses shared list action `unfollow`, IDs from `personKey`, and test IDs `following-person-<personKey>`. Search preserves `search-result-<position>` and positional row IDs; its previous row-specific action mapping moves into SearchResults.

- [x] **Step 1: Write failing UI tests.** Assert Following's Unfollow starts at opacity 0/pointer-events none, reveals on hover/focus/touch, uses Search's exact border/padding/type styling, removes immediately, restores original row order on failure, and leaves blank content after the last removal. Test hidden-coordinate first tap does not submit, second visible-button tap submits once, selection switches/dismisses, moved/cancelled gestures do nothing, and route exit/removal clears selection. Preserve Search's duplicate-position selection and all existing status/focus tests. Update the obsolete loaded-Following assertion forbidding Unfollow; preserve empty/loading/error assertions forbidding controls.
- [x] **Step 2: Run `npm --prefix frontend test -- --runInBand src/adapters/inbound/ui/FollowingScreen.test.tsx src/adapters/inbound/ui/SearchResults.test.tsx`.** Expect missing unfollow UI behavior; retain existing regression tests.
- [x] **Step 3: Extract and integrate shared interactions.** Move Search's modality/gesture/reveal and styles into PersonActionRow. PersonActionList owns single touch selection and platform-guarded outside-touch dismissal, using a common row containment attribute and positional identities independent of business identities. Reset on result-set replacement/route departure; prune deleted selection. Keep hidden eligible controls keyboard reachable. Following must also preserve a removed keyboard action's restoration token in its surviving list owner: focus the restored control only if focus still belongs to the removed action's fallback, never after navigation or user movement. Clear stale restoration state on later interaction and guest changes. Preserve Search's button-to-status focus transfer and native/server-render safety; no DOM/network work during construction/render.
- [x] **Step 4: Run frontend tests, lint/typecheck, and `npm --prefix frontend run export:web`.** Expect both routes to export, shared interactions to pass, and no dependency-boundary regressions. Real DOM focus/touch behavior is verified in Task 6.
- [x] **Step 5: Commit the Task 5 files.** Suggested message: `feat: add shared unfollow reveal actions`.

### Task 6: Real-browser verification and F002 documentation

**Files:** Create `e2e/tests/unfollow-people.spec.ts`; modify `e2e/tests/follow-people.spec.ts`, `README.md`, `docs/architecture/follow-people.md`, and `docs/superpowers/specs/2026-11-23-F002-follow-people-design.md`. Update this plan's execution tracking.

**Interfaces:** Consume Tasks 2–5's real DELETE route, Following row test IDs, and shared action behavior. Use the existing disposable real-stack fixture harness and explicit bounded user retries for accepted best-effort catalog persistence races. Do not change production behavior to accommodate tests.

- [x] **Step 1: Add browser acceptance tests and run focused coverage.** Run `npm --prefix e2e test -- --grep 'unfollow|following|follow people'`. Cover mouse hover into/out of Unfollow, keyboard Enter/Space, real touch first reveal/second activation, outside navigation without interception, touch scroll/cancel, final-row blank state, immediate disappearance under a held DELETE, no resurrection during navigation, and persistence after reload. Count GETs with request listeners and assert DELETE success/failure introduces none. In a committed-but-lost DELETE test, use `route.fetch()` to commit then abort delivery once; expect the original row back and manual retry `204`. Test keyboard rollback twice: retain focus when the user stayed, preserve another control's focus when they moved. Test successful replacement at three and failed removal plus backend-rejected replacement. Assert provider dispatch count is unchanged by follow/delete/list. Update only the old populated-list assertion that forbids Unfollow; blank-state assertions remain valid. If all behavior already passes, do not manufacture a red failure.
- [x] **Step 2: Resolve any observed integration failures within the approved design.** Use event/response gates instead of sleeps. Keep cache tests in their existing un-routed contexts and preserve the search cache contract. If a command cannot run due to missing tools or Docker, report the limitation; skipped checks are not evidence of success.
- [x] **Step 3: Amend documentation.** Link the approved unfollow amendment from the original F002 design and replace its obsolete exclusions while preserving Search's non-mutating Following status. Update architecture/README with DELETE body, empty `204`, idempotent absent-person success, shared queue replay/rollback, immediate slot release and failure-at-cap behavior, shared reveal/focus/touch rules, no migration/provider work, and unfollow spans. Preserve actual refresh triggers: startup, Following entry, new guest; correct README's stale route/foreground wording while editing. Do not rewrite completed historical implementation-plan checkboxes as if the old delivery already included unfollow.
- [x] **Step 4: Run final checks after code settles.** Run `make test`, `make lint`, `make test-integration`, `make test-e2e`, `npm --prefix e2e run typecheck`, and `make generate`. Since generated files were committed in Task 2, `git diff --exit-code -- openapi.json frontend/src/adapters/outbound/api/generated` must show no drift (commit intentional later contract changes first). Run `git diff --check` and inspect working-tree scope. Run the separate cache-expiry suite only if cache behavior changed or failures warrant it. Record actual outcomes without claiming unavailable checks passed.
- [x] **Step 5: Commit browser tests, documentation, fixes, and tracking.** Suggested message: `test: verify and document F002 unfollow lifecycle`. Complete the selected execution workflow's whole-branch review before integration. This plan does not authorize merging, pushing, or deploying.

## Self-review and execution handoff

All design sections map to tasks: durable scoped idempotency and transactions (1), DELETE/errors/telemetry/generated contracts (2–3), chronological optimism and identity/race protection (4), shared styling/reveal/focus/navigation behavior (5), real browser/lost delivery/cap coverage and documentation (6). Review Focus conditions have explicit tests in their owning tasks. Names and return types above are the shared contracts. No unresolved product decision or schema change is required.

Status: All six tasks executed inline with `executing-plans` on 2026-11-23. Final fresh-context review completed; both Important findings were fixed with RED→GREEN regression tests in one pass. Integration remains owner-controlled.

Verification: `make test` (266 backend, 108 frontend), `make lint`, `make test-integration` (72 disposable PostgreSQL), `make test-e2e` (28 real-browser), e2e typecheck, web export, deterministic `make generate`, generated-contract no-drift check, and `git diff --check` passed. New browser assertions were corrected to scope retained route copies to visible rows and to use the fixture's actual fourth result, Tom Cruise. No production workaround was required. Cache behavior is unchanged; the independent cache-expiry suite was not required.

Final review: Following touch selection now survives an ordinary refresh while the selected person remains; Search still clears selection on result replacement. Pen input shares first-tap reveal, gesture cancellation, outside dismissal, and second-tap activation. Both regressions failed before the fix, passed afterward, and passed fresh-build browser probes. Final web export, lint/typechecks, and generated-contract no-drift checks passed.

Deferred minors from the reviewer: removal buttons have the generic accessible name `Unfollow` rather than including the person's name; the final-row reload browser assertion can pass before GET completes (durable deletion also has fresh-engine persistence and surviving-row browser coverage). Native-device release and cross-tab synchronization remain explicitly deferred by the approved designs.
