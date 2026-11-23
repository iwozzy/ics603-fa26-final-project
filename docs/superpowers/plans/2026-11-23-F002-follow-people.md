# F002: Follow People Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let guests follow up to three existing people through optimistic search actions and view their saved follows in a persistent sidebar destination.

**Architecture:** Framework-free use cases enforce the follow rule through an async unit-of-work port; the Postgres adapter locks the guest profile and commits each follow before success. A shared client state owner combines a separately loaded following snapshot with local pending actions, while Search retains screen-local state. Provider data and browser search caching remain independent of profile-owned follows.

**Tech Stack:** Existing FastAPI/Python, SQLAlchemy async/psycopg, Alembic/PostgreSQL, Expo Router/React Native web, TypeScript, generated OpenAPI/Zod, pytest, Jest, and Playwright. No new dependencies.

**Spec:** [Approved F002 design](../specs/2026-11-23-F002-follow-people-design.md). Read it before implementing this plan.

## Global Constraints

- A follow request contains only `provider` and `provider_id`.
- A missing person returns HTTP `500`, and the client restores `Follow +`.
- Guests can follow at most three people. At the limit, remaining `Follow +` actions are hidden.
- The sidebar is present by default and always contains Search and Following, regardless of follow count.
- The new table is named `follows`. Follow/list database I/O must be asynchronous and yield to the event loop while waiting.
- Following lists people in most recently followed order (`followed_at DESC`), with person ID descending as the stable tie breaker.
- Show no loading or activity indicator on Following. Initial loading, initial load failure, and an empty successful list leave the content area blank.
- Do not automatically repeat the mutation or trigger a list read because the mutation failed, including for cap rejection or an ambiguous commit.
- Leaving Search clears its interaction state and touch selection and cancels pending search work; returning starts with the initial search screen.
- Preserve existing safe provider IDs (`1..2^53-1`), `provider: "tmdb"`, summaries, search order/duplicates, seven-result selection, private browser search caching, quotas, and request deadlines.
- No person creation/update, provider calls, hydration, Unfollow, Movies tab, account prompts, native release, or new environment settings in this feature.
- Use only disposable test databases and fixture provider data. Do not read or write secrets or connect to the application database.

## Review Focus

- Repeated provider identities in search: all copies share follow state, but touching one row reveals only that row (Tasks 5 and 7).
- Hybrid touch/mouse input: synthesized hover/focus cannot activate a hidden action or defeat outside-tap dismissal (Tasks 7 and 8).
- Guest recreation during queued/in-flight work: old follows and responses cannot enter the new guest's state; ordinary bootstrap revalidation preserves it (Tasks 4 and 5).
- A third follow commits but its response is lost: roll back locally, issue no reconciliation read, and allow an idempotent manual retry at the server cap (Tasks 2, 5, and 8).
- Route retention and static web export: navigating cancels/reset Search without cancelling a follow, and rendering/constructing providers performs no network I/O (Tasks 5 and 6).

## File and interface map

Paths below are repository-relative. Task file lists name exact production/test paths; generated transport files remain confined to the API adapter.

| Area | Files and responsibility |
| --- | --- |
| Backend core | New `backend/src/lumiere/domain/following.py`, `application/ports/following.py`, and `application/use_cases/following.py`: identities, snapshots, async contracts, cap/idempotency rules |
| Persistence | New `backend/migrations/versions/0008_follows.py`, `adapters/outbound/persistence/following_repository.py`, and `following_unit_of_work.py`; existing `models.py`: follow schema, async locking/reads/writes |
| HTTP/composition | New HTTP `schemas/following.py` and `routers/v1/following.py`; existing `deps.py`, `errors.py`, `guest_session.py`, `main.py`, `bootstrap.py`, `observability.py`, and OpenAPI exporter |
| Client contract | New `frontend/src/domain/following.ts`, application `ports/following-repository.ts`, `use-cases/follow-person.ts`, `use-cases/list-following.ts`, and API `following-repository.ts`, `following-mappers.ts`; extend shared guest-session port/adapter |
| Shared state | New `frontend/src/application/following-store.ts`, UI `FollowingContext.tsx`, `FollowingProvider.tsx`, and `useFollowing.ts`; existing bootstrap container/providers compose them |
| Navigation/list | New UI `AppShell.tsx`, `FollowingScreen.tsx`, and route `frontend/src/app/following.tsx`; existing `_layout.tsx` keeps the sole route composition exception |
| Search interactions | New UI `SearchResults.tsx` and `SearchPersonRow.tsx`; existing `SearchPeopleScreen.tsx`, `useSearchPeople.ts`, and `PersonRow.tsx`: row reveal, identity overlay, and navigation reset |
| Verification/docs | New focused tests below; extend existing migration/contract/session/cache coverage and README/architecture diagrams |

Execute Tasks 1–8 in order. Each task supplies the interfaces its successors consume. Do not implement optional/deferred features while filling in bodies.

### Task 1: Define following rules and async core contracts

**Files:** Create `backend/src/lumiere/domain/following.py`, `backend/src/lumiere/application/ports/following.py`, `backend/src/lumiere/application/use_cases/following.py`, `backend/tests/fakes/following.py`, and `backend/tests/unit/application/test_following.py`. Modify `backend/src/lumiere/domain/errors.py`.

**Interfaces:**
- Domain frozen dataclasses: `PersonIdentity(provider: CatalogProvider, provider_id: int)` and `FollowingSnapshot(people: tuple[PersonSummary, ...], limit: int)`; `FollowingFailed(category: str)` alongside existing errors.
- `FollowingRepository` async methods: `lock_profile(profile_id: UUID) -> bool`, `find_person(identity: PersonIdentity) -> int | None`, `is_following(profile_id: UUID, person_id: int) -> bool`, `count(profile_id: UUID) -> int`, `add(profile_id: UUID, person_id: int) -> None`, and `list_people(profile_id: UUID) -> tuple[PersonSummary, ...]`.
- `FollowingUnitOfWork` exposes `follows: FollowingRepository`, async enter/exit/commit/rollback. `FollowingUnitOfWorkFactory.__call__() -> FollowingUnitOfWork` returns a fresh instance.
- In the use-case module, define `GUEST_FOLLOW_LIMIT = 3`; `FollowPerson(factory).execute(identity: PersonIdentity, context: GuestContext) -> FollowingSnapshot` and `ListFollowing(factory).execute(context: GuestContext) -> FollowingSnapshot`, both async.
- In the ports module, `FollowPersonPort.execute(identity, context)` and `ListFollowingPort.execute(context)` have those same typed async signatures for HTTP dependencies and observed wrappers.
- Test `MemoryFollowing` is a callable UoW factory with controllable profiles, people keyed by provider identity, stored memberships/timestamps, transaction snapshots, and operation/commit recording. Use `sample_person` from `tests/fakes/search.py`; keep fake state isolated per test.

- [ ] **Step 1: Add failing use-case tests.** Define `test_follow_records_matching_person_before_success`, `test_missing_person_rolls_back`, `test_existing_follow_succeeds_at_three_without_insert`, `test_fourth_distinct_follow_is_rejected`, `test_invalid_identity_has_no_storage_work`, and `test_list_is_owned_by_requesting_profile`. For a seeded context/profile and person `4139`, assert:

```python
result = await FollowPerson(store).execute(PersonIdentity(CatalogProvider.TMDB, 4139), context)
assert result.limit == 3
assert [p.provider_id for p in result.people] == [4139]
assert store.commits == 1
assert store.operations.index("lock_profile") < store.operations.index("count")
```

   Assert missing-person category `missing_person`, cap category `follow_limit`, missing-profile category `session`, and malformed identity category `invalid_identity`. Reject bool/string/fractional/nonpositive/unsafe IDs and unsupported providers before opening the UoW. Assert no provider client or people-write port is a constructor dependency. Simulated commit failure must escape without a success result or persisted membership.
- [ ] **Step 2: Run `uv --directory backend run pytest tests/unit/application/test_following.py -q`.** Expected: collection/assertion failure because the new core is absent.
- [ ] **Step 3: Implement the declared contracts and use cases.** POST acquires the profile lock, resolves the person, checks existing membership before checking the cap, inserts only if eligible, obtains the ordered snapshot, and awaits commit before returning. GET performs one `list_people` call and returns `limit=3`. Do not check the cap using usage counters or in-memory production locks.
- [ ] **Step 4: Rerun that test file and `uv --directory backend run lint-imports`.** Expected: all tests pass and framework-free boundaries remain intact.
- [ ] **Step 5: Commit the core, fake, and tests.** Suggested message: `feat: define transactional guest following rules`.

### Task 2: Persist follows with async transactions and profile locking

**Files:** Create `backend/migrations/versions/0008_follows.py`, `backend/src/lumiere/adapters/outbound/persistence/following_repository.py`, `backend/src/lumiere/adapters/outbound/persistence/following_unit_of_work.py`, `backend/tests/integration/persistence/test_following.py`, and `backend/tests/integration/persistence/test_following_migration.py`. Modify `backend/src/lumiere/adapters/outbound/persistence/models.py`, `backend/tests/integration/persistence/conftest.py`, and `backend/tests/integration/persistence/test_people_migration.py`.

**Interfaces:**
- Consume Task 1's repository/UoW contracts.
- Produce `FollowRow` mapped to `follows`, composite PK `(profile_id, person_id)`, non-null FKs to `guest_profiles.id`/`people.id`, and timezone-aware `followed_at` with database default `clock_timestamp()` so time is assigned at insertion after the lock.
- Produce `PostgresFollowingRepository(session: AsyncSession)` implementing every repository method and `PostgresFollowingUnitOfWork(sessions: async_sessionmaker[AsyncSession])` extending existing `PostgresUnitOfWork` cleanup and binding `self.follows` after async entry.
- Add fixture `following_uows(uows) -> Callable[[], PostgresFollowingUnitOfWork]` using the existing disposable `uows().factory`, never operator configuration.

- [ ] **Step 1: Write failing integration tests.** `test_following_newest_first_and_repeat_preserves_timestamp` seeds distinct timestamps plus a tied pair and asserts `followed_at DESC, person_id DESC`; a repeated follow leaves timestamp/order unchanged. `test_two_concurrent_distinct_follows_from_two_allow_exactly_one` gathers two use-case requests from two existing follows and asserts one success, one `follow_limit`, and exactly three rows. `test_concurrent_repeat_creates_one_row` asserts both calls succeed, one row persists. `test_following_uses_current_summary_and_profile_ownership` changes the stored summary through the existing people writer repository and asserts only its owner's GET sees the updated summary and fixed image URL/fallback.

   Add `test_waiting_profile_lock_yields_to_other_requests` using separate async sessions: hold profile A's lock, start its follow with a short database lock timeout, and prove a heartbeat and profile B's query complete while A is still waiting. Bound waits and release/cancel in `finally`. Add rollback/cancellation/fresh-session tests proving no partial membership, leaked connection, or lost committed follow.

```python
assert len(successful_results) == 1
assert rejected_result.category == "follow_limit"
assert await repository.count(profile_id) == 3
assert heartbeat_completed and not waiting_follow.done()
assert repeated_follow_timestamp == original_follow_timestamp
```

   Migration tests assert FKs/PK/timezone timestamp, duplicate rejection, no `person_follows` table, upgrade preservation of existing guests/people/counters, and downgrade removing only `follows`. Existing `test_people_migration.py` directly invokes 0007 downgrade; have it downgrade 0008 first and restore 0007 then 0008 at each roundtrip, without weakening its existing assertions.
- [ ] **Step 2: Run `make test-integration`.** Expected: the new tests fail before the adapter/migration exists. This command starts/removes isolated Postgres; tests skipped without `LUMIERE_RUN_PERSISTENCE=1` do not count as verification.
- [ ] **Step 3: Implement schema and async adapter.** Migration revision `0008_follows` descends from `0007_people` (recheck the head before creating it). Parameterize queries. `lock_profile` uses `SELECT ... FOR UPDATE`; lookup matches `people.tmdb_id`; ordered list joins follow/person in one SELECT and maps to `PersonSummary`. Reuse the pure existing TMDB `image_url` mapper for URL construction without instantiating a client. Reuse shared transaction cancellation cleanup; its existing `SearchFailed("storage")` remains recognized by the HTTP boundary rather than redesigning all storage errors.
- [ ] **Step 4: Run `make test-integration` again.** Expected: the entire persistence suite passes, including older migration tests, real concurrency, idempotency at three, and event-loop progress.
- [ ] **Step 5: Commit schema, adapter, migration compatibility change, and tests.** Suggested message: `feat: persist follows with async profile locking`.

### Task 3: Expose following HTTP endpoints and guest creation metadata

**Files:** Create `backend/src/lumiere/adapters/inbound/http/schemas/following.py`, `backend/src/lumiere/adapters/inbound/http/routers/v1/following.py`, and `backend/tests/api/test_following.py`. Modify `backend/src/lumiere/adapters/inbound/http/deps.py`, `backend/src/lumiere/adapters/inbound/http/errors.py`, `backend/src/lumiere/adapters/inbound/http/routers/v1/guest_session.py`, `backend/src/lumiere/main.py`, `backend/src/lumiere/bootstrap.py`, `backend/src/lumiere/observability.py`, `backend/scripts/export_openapi.py`, `backend/tests/api/conftest.py`, `backend/tests/api/test_sessions.py`, `backend/tests/api/test_openapi.py`, `backend/tests/unit/test_observability.py`, `backend/tests/unit/test_people_lifecycle.py`, and `backend/tests/unit/test_accounting_lifecycle.py`. Regenerate root `openapi.json` and `frontend/src/adapters/outbound/api/generated/`.

**Interfaces:**
- HTTP `FollowPersonRequest`: forbid extras; `provider: CatalogProvider`; strict integer `provider_id` in `1..2^53-1`. `FollowingResponse`: `people` of existing `PersonResponse` (maximum three), `limit: Literal[3]`, attribute-based mapping with hidden validation inputs.
- `following_router(services: HttpServices) -> APIRouter` registers GET/POST `/api/v1/following`, operation IDs `listFollowing`/`followPerson`. Both return `200` snapshots or empty `500`; all responses are `no-store`.
- Add required keyword-only `HttpServices.list_following: ListFollowingPort` and `.follow_person: FollowPersonPort`. Update every existing service construction listed above using explicit fake/inert ports; do not make optional production dependencies.
- Bootstrap success adds `X-Lumiere-Guest-Created: true|false` from `GuestBootstrap.is_new`, keeping empty `200` body and cookie behavior. Declare that response header in OpenAPI.
- Runtime builds both use cases with fresh following UoWs from `application.sessions`. Add `ObservedListFollowing(inner: ListFollowingPort)` and `ObservedFollowPerson(inner: FollowPersonPort)` implementing their respective service ports, spans `following.list`/`following.follow`, HTTP spans `http.following.list`/`http.following.follow`, and finite `missing_person`, `follow_limit`, `invalid_identity`, `session`, `origin`, `storage`, `deadline` categories.

- [ ] **Step 1: Write failing API/composition tests.** For GET assert `200`, `{"people": [], "limit": 3}`, and `no-store`. POST a matching person and assert the exact six summary keys, full snapshot, and no internal IDs. Missing person/cap/session/origin/storage/deadline/unhandled failures and invalid bodies must assert:

```python
assert response.status_code == 500
assert response.content == b""
assert response.headers["cache-control"] == "no-store"
```

   Parameterize IDs `True`, `"4139"`, `1.5`, `0`, `-1`, `2**53`, unsupported providers, missing fields, malformed JSON, extra `name`, and extra `profile_id`. Verify rejection creates no follow. Test correct-cookie ownership, repeat success at the cap, no catalog dispatch/usage charge, and that blocking commit keeps HTTP completion pending. Session tests assert creation header `true` initially and `false` on reuse, unchanged body/cookie attributes. Extend pool-composition tests to assert both follow use-case factories use `application.sessions`. Telemetry tests use sentinel bodies/names/errors and assert none appear in attributes.
   Extend the `Api` fixture with its `MemoryFollowing` instance and share profile IDs with the synthetic `MemoryAccess` identity store; seed/resolve the bootstrapped test profile before follow requests rather than accepting arbitrary profiles in the fake.
- [ ] **Step 2: Run `uv --directory backend run pytest tests/api tests/unit/test_observability.py tests/unit/test_people_lifecycle.py tests/unit/test_accounting_lifecycle.py -q`.** Expected: new API/header assertions fail.
- [ ] **Step 3: Implement routing, composition, validation/error mapping, and telemetry.** Resolve guest context using current cookie/IP rules; POST runs `check_origin` before mutation. Extend validation handling/OpenAPI response cleanup only for the two new operations as well as existing search. Extend `_failure_category` to recognize `FollowingFailed` and retain existing storage mapping; use category `origin` for `check_origin` failures. Retain sanitized SQL, bounds, and seven-second server deadline. Exporter constructs inert typed following ports without settings/network discovery.
- [ ] **Step 4: Run `make generate`, the Step 2 tests, and `make test`/`make lint`.** Expected: all pass; OpenAPI exposes only `200`/`500` for following and search, a documented bootstrap header, and strict identity-only POST. Review generated changes; search fields/cache semantics do not change.
- [ ] **Step 5: Commit API, wiring, diagnostics, fixtures, and generated contract together.** Suggested message: `feat: expose durable following endpoints`.

### Task 4: Add client following transport and guest-generation events

**Files:** Create `frontend/src/domain/following.ts`, `frontend/src/application/ports/following-repository.ts`, `frontend/src/application/use-cases/list-following.ts`, `frontend/src/application/use-cases/follow-person.ts`, `frontend/src/application/use-cases/following.test.ts`, `frontend/src/adapters/outbound/api/following-repository.ts`, `frontend/src/adapters/outbound/api/following-mappers.ts`, `frontend/src/adapters/outbound/api/following-repository.test.ts`, and `frontend/src/adapters/outbound/api/guest-session-repository.test.ts`. Modify `frontend/src/domain/errors.ts`, `frontend/src/application/ports/guest-session-repository.ts`, and `frontend/src/adapters/outbound/api/guest-session-repository.ts`, plus existing `repositories.test.ts` response helpers.

**Interfaces:**
- Domain `PersonIdentity = Pick<PersonSummary, 'provider' | 'providerId'>`; `FollowingSnapshot { readonly people: readonly PersonSummary[]; readonly limit: number }`; pure `personKey(person: PersonIdentity): string` returns `provider + ':' + providerId`; error `FollowingFailed`.
- `FollowingRepository.list(signal: AbortSignal): Promise<FollowingSnapshot>` and `.follow(identity: PersonIdentity, signal: AbortSignal): Promise<FollowingSnapshot>`.
- `ListFollowing(repository).execute(signal)` and `FollowPerson(repository).execute(identity, signal)` return `Promise<FollowingSnapshot>` and contain no UI/network-framework imports.
- `HttpFollowingRepository(fetchImpl: typeof fetch, sessions: GuestSessionRepository)` implements the port; `mapFollowingSnapshot(value: unknown): FollowingSnapshot` uses generated validation and existing summary field mapping.
- Preserve session `.ensure(signal): Promise<void>` and `.invalidate(): void`; add readonly `.identityGeneration: number` initially zero and `.subscribeIdentityCreated(listener: (generation: number) => void): () => void`. This identity generation is separate from the existing bootstrap request generation.

- [ ] **Step 1: Write failing transport/session/use-case tests.** Assert GET and POST same-origin cookie transport, no-store GET, JSON POST exactly `{provider:'tmdb', provider_id:4139}`, no summary/profile fields, valid six-field mapping, and rejection of malformed JSON/schema/unsafe numeric IDs. For a failed follow assert exactly one POST and zero follow-up GETs/retries. Use a real `Headers` object in mocked bootstrap responses with `X-Lumiere-Guest-Created` set, preserving existing search tests' expectations of platform search caching.

   Session tests assert creation header `true` advances generation/notifies once; `false` and readiness `.invalidate()` do not advance it; a superseded bootstrap cannot notify/publish readiness; one aborted waiter leaves another usable; missing/invalid header fails validation; unsubscribe prevents notifications. Thin use-case tests assert exact identity/signal delegation and error propagation.

```typescript
expect(JSON.parse(postOptions.body as string)).toEqual({ provider: 'tmdb', provider_id: 4139 });
expect(listRequestsAfterFailedPost).toBe(0);
expect(sessions.identityGeneration).toBe(generationBeforeReadinessInvalidation);
expect(mapped.people[0].providerId).toBe(Number.MAX_SAFE_INTEGER);
```
- [ ] **Step 2: Run `npm --prefix frontend test -- --runInBand src/adapters/outbound/api src/application/use-cases/following.test.ts`.** Expected: failures for new contracts/events.
- [ ] **Step 3: Implement the declared transport/use cases/session events.** Reuse `withDeadline` and shared session bootstrap. After `ensure`, check abort before dispatch. Publish identity creation only for a current successful bootstrap after setting readiness. Following failures throw `FollowingFailed` and perform neither mutation retry nor list reconciliation; do not mark session readiness stale merely for a follow `500`. Keep generated imports/validation in the API adapter.
- [ ] **Step 4: Rerun Step 2 and `npm --prefix frontend run typecheck`/`npm --prefix frontend run lint`.** Expected: new and existing transport tests pass, with no boundary violations.
- [ ] **Step 5: Commit the client contracts, adapter, events, and tests.** Suggested message: `feat: add following client transport and identity events`.

### Task 5: Own shared optimistic following state above navigation

**Files:** Create `frontend/src/application/following-store.ts`, `frontend/src/application/following-store.test.ts`, `frontend/src/test-utils/fakes/following.ts`, `frontend/src/adapters/inbound/ui/FollowingContext.tsx`, `frontend/src/adapters/inbound/ui/FollowingProvider.tsx`, `frontend/src/adapters/inbound/ui/FollowingProvider.test.tsx`, and `frontend/src/adapters/inbound/ui/useFollowing.ts`. Modify `frontend/src/bootstrap/container.ts`, `frontend/src/bootstrap/Providers.tsx`, and `frontend/src/test-utils/renderWithPorts.tsx`.

**Interfaces:**
- `FollowingViewState`: readonly `confirmed: FollowingSnapshot | null`, `pending: readonly PersonSummary[]`, `people: readonly PersonSummary[]` (effective merged newest-first display), `phase: 'idle' | 'loading' | 'ready' | 'failed'`, and `canFollow: boolean`. Unknown `confirmed` always makes `canFollow=false`.
- `FollowingStore(list: ListFollowing, follow: FollowPerson, sessions: GuestSessionRepository)` exposes stable cached `.getSnapshot(): FollowingViewState`, `.subscribe(listener: () => void): () => void`, `.start(): void`, `.stop(): void`, `.refresh(): Promise<void>`, and `.requestFollow(person: PersonSummary): boolean`. Return `true` only for a newly accepted pending identity; duplicate/full/unknown/inactive requests return `false` without dispatch.
- UI `FollowingContext` carries `FollowingStore`; `FollowingProvider({store, children})` owns start/stop and browser/native foreground subscriptions; `useFollowing()` returns `{state: FollowingViewState, follow(person): void, refresh(): Promise<void>}` using `useSyncExternalStore` with a stable server snapshot.
- Container returns `{searchPeople, followingStore}`; create one shared session adapter and following repository, then both new use cases/store. Constructors/rendering do no I/O. Bootstrap Providers composes the existing PeopleSearchContext with FollowingProvider. Test wrappers inject an already-loaded empty following fake by default so existing search tests do not start uncontrolled network work.

- [ ] **Step 1: Write failing store/provider tests with a deferred fake repository.** Name tests `pending_third_hides_actions_and_rejection_releases_slot`, `duplicate_identity_has_one_pending_entry`, `mutations_send_sequentially_and_preserve_other_pending_entries`, `old_read_cannot_replace_newer_mutation_snapshot`, `initial_failure_is_unknown_but_refresh_failure_preserves_confirmed`, `lost_response_rolls_back_without_get_then_manual_retry_succeeds`, and `navigation_subscribers_do_not_own_mutation_lifetime`. Assert effective people prepend pending in most-recent-click order while confirmed retain server ordering.

```typescript
const readsBeforeFailure = fake.listCalls.length;
store.requestFollow(person);
fake.rejectActiveFollow(new Error('lost response'));
await flushPromises();
expect(store.getSnapshot().pending).toHaveLength(0);
expect(fake.listCalls).toHaveLength(readsBeforeFailure);
expect(store.requestFollow(person)).toBe(true);
```

   Define `flushPromises` locally using microtask settlement, without sleeps. The fake records list/follow calls and exposes controlled resolve/reject operations with typed snapshots. Test new-guest events during `ensure`, queued and active follows, and GET: unsent old work is discarded; abort/ignore old responses; initial new-guest notification restarts loading exactly once. Bootstrap `false`/search readiness invalidation leaves confirmed state intact. Test start/stop/start and cancellation cleanup, deduplicated refreshes, no network on construction/render, and foreground subscriptions removed on unmount.
- [ ] **Step 2: Run `npm --prefix frontend test -- --runInBand src/application/following-store.test.ts src/adapters/inbound/ui/FollowingProvider.test.tsx`.** Expected: missing-store/provider failures.
- [ ] **Step 3: Implement the store and providers.** Use immutable snapshots with a unique identity map and bounded serial mutation queue. Register optimism synchronously; merge pending over confirmed by `personKey`; on settlement remove only that pending item. Before each queued dispatch, await session readiness and recheck guest generation/abort to prevent old work from crossing bootstrap recreation. Guard read publication by both guest generation and mutation revision; ignore obsolete reads without scheduling reconciliation. Session creation resets/aborts old work and starts a fresh initial load after bootstrap readiness; identity events and queue dispatch must be serialized. Provider effects call start/stop and refresh on foreground via platform-guarded browser visibility/focus or React Native AppState, deduplicating overlapping reads. Stop aborts owned work and removes subscriptions; route unmounts do neither.
- [ ] **Step 4: Rerun Step 2, all frontend tests, typecheck, and lint.** Expected: passes including existing search behavior, stable external-store snapshots, no unhandled rejections, and no generated imports in application/UI.
- [ ] **Step 5: Commit shared state, composition, fakes, and tests.** Suggested message: `feat: manage shared optimistic following state`.

### Task 6: Add persistent navigation and blank-capable Following route

**Files:** Create `frontend/src/adapters/inbound/ui/AppShell.tsx`, `frontend/src/adapters/inbound/ui/AppShell.test.tsx`, `frontend/src/adapters/inbound/ui/FollowingScreen.tsx`, `frontend/src/adapters/inbound/ui/FollowingScreen.test.tsx`, and `frontend/src/app/following.tsx`. Modify `frontend/src/app/_layout.tsx`, `frontend/src/adapters/inbound/ui/SearchPeopleScreen.tsx`, `frontend/src/adapters/inbound/ui/useSearchPeople.ts`, and `frontend/src/adapters/inbound/ui/useSearchPeople.test.tsx`.

**Interfaces:**
- `AppShell({children}: PropsWithChildren)` renders the Lumière brand and unconditional Search (`/`) / Following (`/following`) links, current-route styling, and a shrinking content region compatible with existing 375px browser coverage.
- `FollowingScreen()` consumes `useFollowing`, renders `state.people` through existing `PersonRow`, keyed by provider identity, and renders no activity indicator, empty-state copy, Follow, or Unfollow control.
- Route `following.tsx` exports FollowingScreen; root `_layout.tsx` wraps its existing Stack in AppShell inside Providers. Keep bootstrap imports confined to this existing layout exception.
- Extend `useSearchPeople` with `.reset(): void` that invalidates/aborts the current search and restores its initial state; existing empty-draft logic delegates to it. SearchPeopleScreen uses route focus lifecycle to reset on leaving even if Expo retains its instance. Each route entry requests an ordinary shared following refresh; initial entry deduplicates with provider startup.

- [ ] **Step 1: Write failing UI/navigation tests.** Assert both links in all follow phases, correct destinations/active route, Following renders newest-first summaries and image fallbacks, and loading/error/empty snapshots have blank content with no `progressbar` or added copy. Loaded snapshots remain visible during ordinary refresh failure. Assert direct Following entry triggers list loading. Extend hook/screen tests to show leaving Search clears draft/results, aborts pending search, ignores its late completion, and does not abort a shared pending follow.

```typescript
expect(screen.queryByRole('progressbar')).toBeNull();
expect(screen.queryByText('Unfollow')).toBeNull();
expect(searchHook.result.current).toMatchObject({ draft: '', phase: 'initial', people: [] });
expect(searchCall.signal.aborted).toBe(true);
expect(followCall.signal.aborted).toBe(false);
```
- [ ] **Step 2: Run `npm --prefix frontend test -- --runInBand src/adapters/inbound/ui/AppShell.test.tsx src/adapters/inbound/ui/FollowingScreen.test.tsx src/adapters/inbound/ui/useSearchPeople.test.tsx`.** Expected: missing-shell/route/reset assertions fail.
- [ ] **Step 3: Implement the interfaces and route integration.** Keep the shell outside route content. Route focus callbacks must be stable so ordinary following publications do not reset Search or cause repeated GETs. Render list rows with no action slot. Use responsive spacing rather than overflowing the existing web viewport; reference the F002 wireframes for desktop layout.
- [ ] **Step 4: Rerun Step 2, frontend lint/typecheck, and `npm --prefix frontend run export:web`.** Expected: tests/import boundaries pass and static export creates both routes without runtime configuration, network I/O, or server DOM errors.
- [ ] **Step 5: Commit shell, route, reset behavior, and tests.** Suggested message: `feat: add sidebar and following page`.

### Task 7: Add mouse, keyboard, and touch follow actions to search

**Files:** Create `frontend/src/adapters/inbound/ui/SearchResults.tsx`, `frontend/src/adapters/inbound/ui/SearchPersonRow.tsx`, and `frontend/src/adapters/inbound/ui/SearchResults.test.tsx`. Modify `frontend/src/adapters/inbound/ui/PersonRow.tsx`, `frontend/src/adapters/inbound/ui/SearchPeopleScreen.tsx`, and `frontend/src/adapters/inbound/ui/SearchPeopleScreen.test.tsx`.

**Interfaces:**
- `PersonRow({person, action?}: {person: PersonSummary; action?: ReactNode})` keeps existing recognition display/fallback and accepts an optional right-side slot; it owns no follow rule or row selection.
- `SearchResults({people, resultSetKey}: {people: readonly PersonSummary[]; resultSetKey: string})` consumes shared following state and owns one touch-selected row ID. Use `resultSetKey + ':' + position` for row selection/test identity, distinct from `personKey` for business state; preserve duplicate search order.
- `SearchPersonRow` props: `person`, `rowId`, `status: 'available' | 'following' | 'hidden'`, `touchSelected: boolean`, `onTouchSelect(rowId: string): void`, and `onFollow(person: PersonSummary): void`. Hover/focus ownership is row-local; normalized outside-touch handling belongs to SearchResults. Keep browser DOM listeners platform-guarded and inside UI; do not add a state/dependency library.

- [ ] **Step 1: Write failing interaction tests.** Assert row hover reveals `Follow +`, moving into its button keeps it revealed, keyboard focus reveals a visible focus ring, and Enter/Space submits once. With touch: first row tap only reveals, a visible-action tap submits, another row tap hides the previous action and selects the new row, and outside tap hides it while the outside control still operates. A scroll/moved/cancelled gesture and a first tap at a hidden button's coordinates submit nothing. Assert touch-produced focus/hover does not undo dismissal.

   Test duplicate provider rows independently selected but jointly `Following` after one click; unknown following state hides available actions; the third pending/save hides only remaining available actions; failure restores eligibility with no GET; `Following` is accessible, non-mutating, and uses the same reveal rules. Clearing/replacing/leaving search resets touch selection. Keep existing optional-field, title, image-fallback, latest-search, and no-Movies assertions.

```typescript
// After the first recognized touch tap:
expect(within(selectedRow).getByRole('button', { name: 'Follow +' })).toBeVisible();
expect(follow).not.toHaveBeenCalled();
// In the separate three-pending case:
expect(screen.queryByRole('button', { name: 'Follow +' })).toBeNull();
```
- [ ] **Step 2: Run `npm --prefix frontend test -- --runInBand src/adapters/inbound/ui/SearchResults.test.tsx src/adapters/inbound/ui/SearchPeopleScreen.test.tsx`.** Expected: action/reveal assertions fail.
- [ ] **Step 3: Implement the interfaces and input semantics.** Render eligible hidden controls so they can receive keyboard focus but cannot receive invisible pointer hits. Treat a complete touch tap as selection and consume no follow activation from that first touch, including synthesized click. Clear touch selection on an outside touch without preventing the outside control's action; identify row containment through registered UI refs. A tap inside an already selected row does not deselect it. Distinguish input modality so a touch dismissal overrides touch-origin focus/hover until an actual mouse or keyboard interaction. Follow status derives from unique confirmed/pending identities, never a component-local optimistic boolean. Wire the slot to `useFollowing().follow` and leave FollowingScreen action-free.
- [ ] **Step 4: Rerun Step 2, all frontend tests, lint, and typecheck.** Expected: unit/UI coverage passes; actual browser event semantics are verified next, not assumed from synthetic tests.
- [ ] **Step 5: Commit search interactions and tests.** Suggested message: `feat: follow search results with accessible reveal actions`.

### Task 8: Verify the full flow and document F002

**Files:** Create `e2e/tests/follow-people.spec.ts` and `docs/architecture/follow-people.md`. Modify `e2e/tests/search-people.spec.ts`, `e2e/tests/cache.spec.ts` only where needed for startup/list traffic or real cached-result status overlay, `README.md`, `docs/architecture/search-people.md`, `docs/architecture/search-people-async-persistence.md`, and `docs/superpowers/specs/2026-11-09-application-architecture-design.md`. Update the task checkboxes in this plan during execution.

**Interfaces:**
- Use the existing real-stack fixture provider and disposable Compose database. New browser tests can intercept following requests for bounded failure/latency cases; keep real HTTP-cache tests in separate contexts with no request routing, HAR, service workers, or cache mocks.
- Give search row roots `testID={'search-result-' + position}` and keep exact visible action labels `Follow +`/`Following`; use roles/labels for sidebar navigation and search. Test helpers may explicitly retry a user click while waiting for best-effort person persistence, checking `500` rollback between attempts and bounding the number/time; the product must never retry automatically.

- [ ] **Step 1: Write browser tests and run them red.** Cover unconditional sidebar/blank Following under delayed/empty/failed initial GET; direct route/browser back-forward; mouse/keyboard/touch flows; three follows then hidden actions and direct-HTTP fourth rejection; newest-first order; reload persistence; search resets on route change while a follow completes; and existing-person retry at the cap. Use fresh browser contexts/profiles per test and assert no extra provider dispatch from follow/list.

   For lost response, route a POST through `route.fetch()` so the real backend commits, then abort delivery once. Assert `Follow +` returns and GET count stays unchanged; a second explicit user click succeeds with one saved membership. For missing person, provide a valid search-shaped fixture identity absent from the disposable people table, then let the real follow endpoint return `500`. For caching, re-search the same query in an un-routed context, assert provider count is unchanged, and assert its action overlay reflects saved follows. Add a touch-enabled context and real pointer taps/scroll gestures; assert first tap never follows, outside/navigation tap still works, and synthesized hover/focus does not leave stale actions.

```typescript
// In the lost-response test, count GETs with page.on('request', ...):
expect(followingGets).toBe(getsBeforeFailedDelivery);
await expect(row.getByRole('button', { name: 'Follow +' })).toBeVisible();
// In the real-touch test, count POSTs before and after the first tap:
await row.tap();
expect(followPosts).toBe(postsBeforeFirstTap);
```

   Run `npm --prefix e2e test -- --grep 'following|follow people'` with matching new test titles. Expected: genuine behavior failures before any fixes, or all green if prior task tests already determined the behavior; do not force an artificial red by breaking working code.
- [ ] **Step 2: Fix integration issues within the approved design.** Keep Playwright setup disposable and single-worker; avoid arbitrary sleeps. Use state/response assertions and existing fixture control counts. Do not add test-only endpoints to production or query the application database. Re-run the focused failing test until its actual event/contract issue is resolved.
- [ ] **Step 3: Update documentation.** Document GET/POST bodies/responses, guest creation header, `follows`, async transaction/lock/commit semantics, newest-first order, mouse/focus/touch reveal, manual retry without reconciliation, blank loading, search reset, and missing-person failures caused by best-effort search persistence. Add a dated architecture amendment linking the approved design and explicitly deferring follow-time hydration. Preserve search-cache and provider-usage guarantees in the diagrams.
- [ ] **Step 4: Run final verification once after the final code changes.** Run `make test`, `make lint`, `make test-integration`, `make test-e2e`, `npm --prefix e2e run typecheck`, `make generate`, and `git diff --exit-code -- openapi.json frontend/src/adapters/outbound/api/generated` after intended generated changes have been committed. Expected: all applicable suites pass, including existing un-routed cache coverage, and regeneration has no diff. Do not run the separate 12-second cache-expiry suite unless search-cache behavior changed or its coverage fails. Verify working-tree scope and no unintended dependencies/configuration/provider calls. Report any unavailable Docker/tooling as a verification limitation instead of claiming its checks passed.
- [ ] **Step 5: Commit integration tests, fixes, documentation, and completed plan tracking.** Suggested message: `test: verify and document F002 following flow`. Use the selected execution workflow's whole-branch review before integration; this plan does not authorize merging, pushing, or deployment.

## Plan self-review and execution handoff

The task mapping covers every design section: identity/cap/idempotency (1–3), async storage and migration safety (2), HTTP/header/telemetry (3–4), client ordering/races/manual retry/identity lifecycle (4–5), navigation/blank loading/search reset (6), input interactions and duplicates (7), and real-browser/cache behavior plus architecture updates (8). Review Focus conditions each have named owning tests. Shared signatures in Interfaces blocks are the contracts between tasks.

This plan changes no runtime code until execution is selected. Recommended execution: **Native**, because these eight tasks share contracts and one client state lifecycle, so retaining context avoids repeated handoffs; a whole-branch independent review still checks the result. The alternative is **Subagent-driven**, with a fresh implementer/reviewer gate per task and a final whole-branch review, at higher context cost.
