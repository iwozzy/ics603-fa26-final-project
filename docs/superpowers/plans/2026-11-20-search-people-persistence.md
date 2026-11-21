# Asynchronous Search People Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist returned people asynchronously without making search wait for a database write, and retain provider identifiers for future following.

**Architecture:** Search offers its selected immutable summaries to a bounded queue. One dispatcher runs at most ten batch tasks against a dedicated named connection pool; each task performs one atomic bulk upsert. Application/domain ports remain framework-free, while the persistence adapter and composition root own named pools and sessions.

**Tech Stack:** Existing Python/FastAPI, asyncio, SQLAlchemy async/psycopg, Alembic/PostgreSQL, TypeScript/React Native, generated OpenAPI/Zod, pytest and Jest. No new dependencies.

**Spec:** [Approved design](../specs/2026-11-20-search-people-persistence-design.md).

## Global Constraints

- Do not read or write secrets or application database contents during development.
- Persist only the selected results returned by a backend search: up to seven valid people from TMDB's first page, in provider order.
- Save the same recognition-title strings currently served to the client: zero to three nonblank strings.
- Each returned person gains `provider` and `provider_id`. Rename `department` to `known_for_department`; frontend domain property becomes `knownForDepartment`.
- `provider` is the stable app-defined string `tmdb`; `provider_id` is a positive JSON integer no greater than `9,007,199,254,740,991` (`2^53 - 1`). Do not expose the database person ID.
- One multi-row `INSERT ... ON CONFLICT (tmdb_id) DO UPDATE` statement per nonempty attempt, then one commit; no preliminary SELECT, per-person queries, or ID retrieval.
- `application` and `people_writer` pools each have five retained connections plus five overflow; the maximum is twenty checked-out connections per backend process.
- At most 1,024 outstanding search batches, counting queued and in-flight work; at most ten in-flight tasks.
- Five-second timeout per persistence attempt; at most three attempts per batch; one-second async delay between failures; five-second total shutdown drain.
- Empty results enqueue nothing. Full, stopped, or unavailable people persistence drops work without failing search. Retries retain their outstanding allowance and dispatch slot.
- No request-owned database transaction spans provider I/O. Preserve existing accounting, cache headers, deadlines, duplicate results, and provider ranking.
- Implement no following, durable queue, provider table, local person search, or generic job framework.

## Review Focus

- Provider IDs near `2^53 - 1`: exact identity survives provider validation, JSON, and frontend mapping (Task 1).
- Duplicate and overlapping person IDs: one stored person per TMDB ID, stable app ID, unchanged response duplicates/order (Tasks 2 and 5).
- Database outage or slow checkout: pending plus in-flight work stays bounded and search still returns (Tasks 4 and 5).
- Cancellation during commit or partial startup: no orphan tasks or checked-out sessions remain when pools are disposed (Tasks 2 and 5).
- Telemetry callback/exporter failure: search and queue dispatch continue without logging person data (Tasks 4 and 5).

## File and interface map

| Area | Files and responsibility |
| --- | --- |
| Person data | `backend/src/lumiere/domain/people.py`: provider vocabulary, summary and safe-ID constant; TMDB `dto.py`/`mapper.py`: provider validation and normalized profile path |
| Public contract | HTTP `schemas/people.py`, root `openapi.json`, frontend generated definitions, domain `people.ts`, API `mappers.ts`, UI `PersonRow.tsx` |
| Person persistence | New application `ports/people.py`, migration `0007_people.py`, ORM person row, new persistence `people_repository.py` and `people_unit_of_work.py` |
| Transaction cleanup | Existing persistence `unit_of_work.py`: shared transaction lifecycle, existing access UoW behavior preserved |
| Named pools | Existing persistence `session.py`: parameterized pool construction; new `pools.py`: registry and disposal |
| Async work | New application `people_writer.py`: queue, dispatch, bounded retries, drain and reports |
| Integration | Search use case, `bootstrap.py`, `observability.py`: enqueue, assigned factories, lifespan and sanitized diagnostics |
| Test support | `tests/fakes/search.py`: typed person factory and queue; new `tests/fakes/people.py`: controllable UoW factory with transaction/commit barriers |

Tasks 2 and 3 consume Task 1's types independently. Task 4 consumes Task 2's ports. Task 5 integrates all preceding tasks. Execute in the order below for simple review and verification.

### Task 1: Carry provider identity and normalized person data through the contract

**Files:** Modify `backend/src/lumiere/domain/people.py`, TMDB `dto.py`, `mapper.py`, HTTP `schemas/people.py`; `backend/tests/fakes/search.py`, domain/API/provider tests and existing summary construction sites. Modify `frontend/src/domain/people.ts`, API `mappers.ts`, `repositories.test.ts`, UI `PersonRow.tsx`, `SearchPeopleScreen.test.tsx`, and `test-utils/fakes/people-search.ts`. Regenerate `openapi.json` and `frontend/src/adapters/outbound/api/generated/`.

**Interfaces:**
- Produce `CatalogProvider(StrEnum)` with `TMDB = "tmdb"` and `MAX_PROVIDER_ID = 2**53 - 1` in domain `people.py`.
- Extend frozen `PersonSummary` with fields, in order: `provider: CatalogProvider`, `provider_id: int`, `name: str`, `known_for_department: str | None`, `profile_image_url: str | None`, `known_for: tuple[str, ...]`, `provider_profile_path: str | None = None`. Use keyword construction at changed call sites.
- Keep `PeopleCatalog.search_first_page(query: str) -> tuple[PersonSummary, ...]` and `SearchPeopleResult` unchanged.
- Produce mapper `profile_path(value: object) -> str | None` using existing image-path validation; `image_url` builds the existing image URL from that normalized path.
- Frontend `PersonSummary` retains `provider: 'tmdb'`, `providerId: number`, `knownForDepartment: string | null` and existing name/image/title fields. Internal profile path is excluded from the HTTP schema.
- Test helper `sample_person(provider_id: int = 4139, *, name: str = "Tom", known_for_department: str | None = None, profile_image_url: str | None = None, known_for: tuple[str, ...] = (), provider_profile_path: str | None = None) -> PersonSummary` in `tests/fakes/search.py` avoids repeating constructors.

- [ ] **Step 1: Add failing boundary and mapping tests.** Extend `test_tmdb_people.py` with `test_provider_identity_and_relative_profile_path`, safe-ID bounds, and invalid path variants. Extend API exact-field assertions and frontend mapping tests:

```python
assert person.provider == CatalogProvider.TMDB
assert person.provider_id == 4139
assert person.provider_profile_path == "/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg"
assert person.known_for == ("Alien", "Top Gun", "Contact")
assert set(response_person) == {"provider", "provider_id", "name",
    "known_for_department", "profile_image_url", "known_for"}
```

```typescript
expect(mapped.people[0]).toMatchObject({ provider: 'tmdb', providerId: 4139,
  knownForDepartment: 'Acting', knownFor: ['Alien'] });
expect(mapSearchResult(payloadWithId(Number.MAX_SAFE_INTEGER)).people[0].providerId)
  .toBe(Number.MAX_SAFE_INTEGER);
expect(() => mapSearchResult(payloadWithId(Number.MAX_SAFE_INTEGER + 1))).toThrow();
```

Define `payloadWithId(id: number)` locally by copying the valid test payload. Provider tests must accept `2**53 - 1` and skip `2**53`, bool, string, nonpositive and fractional IDs; retain current optional-field tolerance and duplicate order.

- [ ] **Step 2: Run the new tests and confirm failure on missing fields/old contract.** Run `uv --directory backend run pytest tests/integration/clients/test_tmdb_people.py tests/api/test_people.py -q` and `npm --prefix frontend test -- --runInBand src/adapters/outbound/api/repositories.test.ts`.
- [ ] **Step 3: Implement the stated domain and mapping interfaces.** Validate safe IDs in provider DTO and HTTP schema; update all existing `PersonSummary` constructions and department references together. Explicitly validate safe integer identity in the frontend mapping if generated Zod bounds alone do not enforce it. Keep the normalized path internal.
- [ ] **Step 4: Regenerate transport definitions with `make generate`.** Review the diff for only intended person-contract changes; update frontend fixtures and UI property access.
- [ ] **Step 5: Run `make test` and `make lint`.** Expected: backend/frontend tests and type/import/lint checks pass, including existing blank/error presentation and provider-order cases.
- [ ] **Step 6: Commit only this contract change and its tests/generated files.** Suggested message: `feat: retain provider identity in people search`.

### Task 2: Add atomic bulk person persistence and reusable transaction cleanup

**Files:** Create `backend/src/lumiere/application/ports/people.py`, `backend/migrations/versions/0007_people.py`, `backend/src/lumiere/adapters/outbound/persistence/people_repository.py`, `people_unit_of_work.py`, `backend/tests/integration/persistence/test_people.py`, `test_people_migration.py`. Modify ORM `models.py`, persistence `unit_of_work.py`, persistence test `conftest.py`, and existing `test_unit_of_work.py` schema expectations.

**Interfaces:**
- Produce `PeopleRepository(Protocol).upsert_batch(people: tuple[PersonSummary, ...]) -> None` (async).
- Produce `PeopleUnitOfWork` protocol with `people: PeopleRepository`, async context-manager methods and `commit()/rollback()`; `PeopleUnitOfWorkFactory.__call__() -> PeopleUnitOfWork`.
- Produce `PostgresPeopleRepository(session: AsyncSession)` implementing `upsert_batch` without committing.
- Test fixture `people_uows(uows: Callable[[], PostgresAccessUnitOfWork]) -> Callable[[], PostgresPeopleUnitOfWork]` uses `uows().factory` as its session factory; the existing fixture retains responsibility for isolated migration setup/teardown.
- Extract existing enter/exit/commit/rollback semantics into `PostgresUnitOfWork(sessions: async_sessionmaker[AsyncSession])` in `unit_of_work.py`. Preserve `PostgresAccessUnitOfWork` as a subclass preparing its existing repositories. `PostgresPeopleUnitOfWork` subclasses the same base and prepares only `people`.
- ORM `PersonRow` uses table `people`: bigint default-generated `id`, unique positive bigint `tmdb_id`, nullable text department/path, nonblank text name, JSONB list-of-title-strings `known_for`. Store no provider column: this version's mapped external key is `tmdb_id`.

- [ ] **Step 1: Write real-Postgres tests for the new repository/UoW.** Reuse the existing `uows` fixture to create/migrate only the fixed disposable database; construct a `PostgresPeopleUnitOfWork` using that test factory's sessions. Add `test_bulk_upsert_preserves_ids_and_replaces_summary`, `test_duplicate_tmdb_ids_use_first_occurrence`, `test_batch_rollback_is_atomic`, `test_overlapping_batches_preserve_unique_identity`, `test_empty_batch_issues_no_write`, and `test_people_cancellation_discards_connection`. Assertions include:

```python
assert len(stored_rows) == len({p.provider_id for p in input_people})
assert after.id == before.id
assert after.known_for == ["Updated"]
assert after.known_for_department is None
assert after.tmdb_profile_path is None
assert len(person_data_statements) == 1  # Excludes SELECTs performed by the test.
assert not unexpected_select_or_returning
```

Capture statements around repository execution and commit with SQLAlchemy events. Inject a constraint-violating row through test data, assert the transaction raises, and verify every batch row's previous state remains intact. Start overlapping batches in separate sessions. Reuse the existing stalled-rollback cancellation test against the new UoW.

- [ ] **Step 2: Add migration tests and verify red.** Test upgrading from `0006_usage_flush_function`, generating IDs in `0 <= id < 2**40` without supplying them, uniqueness of `tmdb_id`, and downgrade removing only `people` while preserving existing identity/counter data. Run `make test-integration`; expected initial failures refer to absent person storage/interfaces. If Docker is unavailable, record that environment limitation and do not substitute the application database.
- [ ] **Step 3: Implement migration, ORM and ports.** Preserve the exact requested UUID-to-40-bit algorithm; use an explicit outer `::bigint` only if the real PostgreSQL test requires it. Use `autoincrement=False` with the server default. Add name and positive-ID constraints; keep JSON contents normalized by the provider/application boundary. Refactor shared UoW cleanup without changing existing exception/cancellation translation.
- [ ] **Step 4: Implement `upsert_batch`.** Return immediately on empty input; require `CatalogProvider.TMDB`; deduplicate by provider ID keeping its first occurrence; sort IDs; map all five requested data fields; execute one PostgreSQL dialect multi-values insert with conflict updates for summary fields only. Do not update or return `id`, and do not create per-row ORM objects that flush separately.
- [ ] **Step 5: Run `make test-integration` and backend lint/type/import checks.** Expected: old access/accounting transaction tests and the new storage/migration tests pass. Update the existing exact schema assertion to include `people`.
- [ ] **Step 6: Commit this migration, persistence boundary, UoW refactor and tests.** Suggested message: `feat: bulk upsert app-owned people`.

### Task 3: Introduce an adapter-owned registry of isolated named pools

**Files:** Modify `backend/src/lumiere/adapters/outbound/persistence/session.py`; create `pools.py`, `backend/tests/unit/test_pools.py`, `backend/tests/integration/persistence/test_people_pools.py`.

**Interfaces:**
- Parameterize `create_sessions(url: str, *, pool_size: int = 5, max_overflow: int = 5) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]`; preserve pre-ping, hidden parameters and no eager connection.
- Produce frozen `DatabasePool(engine: AsyncEngine, sessions: async_sessionmaker[AsyncSession])` and `PoolRegistry` in `pools.py`.
- `PoolRegistry.register(name: str, url: str, *, pool_size: int = 5, max_overflow: int = 5) -> DatabasePool`; reject duplicate names before constructing a second engine.
- `PoolRegistry.get(name: str) -> DatabasePool`; unknown names raise `KeyError`. `async PoolRegistry.close() -> None` attempts disposal of every registered pool and is safe to repeat. If a disposal fails, finish remaining cleanup before surfacing the failure.

- [ ] **Step 1: Add failing unit tests for registration, lookup and disposal.** Define `test_register_creates_independent_lazy_pools`, `test_duplicate_name_does_not_create_an_engine`, `test_unknown_pool_raises_key_error`, and `test_close_disposes_all_pools_even_after_one_failure`. Inject a fake factory via monkeypatching `pools.create_sessions`; do not construct runtime settings. Assert:

```python
assert application.engine is not people.engine
assert factory_calls == [("application", 5, 5), ("people_writer", 5, 5)]
assert registry.get("people_writer").sessions is people.sessions
assert not connection_attempts
assert all(engine.disposed for engine in fake_engines)
```

Record the registered name alongside factory arguments in the test harness. Test duplicate names, unknown names, partial registration, and disposal continuing after one engine raises.

- [ ] **Step 2: Run `uv --directory backend run pytest tests/unit/test_pools.py -q`.** Expected: fail because the registry does not yet exist.
- [ ] **Step 3: Implement the stated registry interfaces.** Store only named engine/factory resources; no queues, application policy, credentials discovery, or job scheduling belongs here.
- [ ] **Step 4: Add a real pool-isolation test against the disposable database.** Register both pools using the fixed test URL, acquire all ten application connections, and prove two people-pool connections execute concurrently with distinct PostgreSQL backend PIDs. Release those two, acquire ten people connections, and verify an eleventh cannot check out until one returns. Use async barriers/timeouts and always release/dispose resources.
- [ ] **Step 5: Run the registry unit tests, `make test-integration`, and backend lint/type/import checks.** Expected: independent pools with size five and overflow five; no connection leak on test exit.
- [ ] **Step 6: Commit registry, parameterized construction and tests.** Suggested message: `feat: assign isolated database pools by name`.

### Task 4: Implement bounded async scheduling and best-effort delivery

**Files:** Extend `backend/src/lumiere/application/ports/people.py`; create `backend/src/lumiere/application/people_writer.py`, `backend/tests/fakes/people.py`, `backend/tests/unit/application/test_people_writer.py`.

**Interfaces:**
- Produce `PeoplePersistenceQueue(Protocol).enqueue(people: tuple[PersonSummary, ...]) -> bool` (synchronous).
- Produce frozen `PeopleWriteEvent(kind: Literal["accepted", "dropped", "started", "succeeded", "retry", "failed"], outstanding: int, in_flight: int, attempt: int = 0, duration_ms: int = 0)` in the same port module. No input content or exceptions are event fields.
- `PeopleWriter(uow_factory: PeopleUnitOfWorkFactory, *, max_pending: int = 1024, max_concurrent: int = 10, attempt_timeout: float = 5, max_attempts: int = 3, retry_delay: float = 1, shutdown_timeout: float = 5, report: Callable[[PeopleWriteEvent], None] | None = None)` implements the queue.
- `PeopleWriter.start() -> None` schedules the dispatcher without database I/O; async `drain() -> None` waits for outstanding work; async `close() -> None` stops acceptance, drains with the timeout, cancels/awaits work, discards undispatched entries on timeout, releases their allowances and supports repeated close. Read-only `outstanding: int` and `in_flight: int` expose bounded counts for tests/reporting.
- Fake `ControlledPeoplePersistence` implements `PeopleUnitOfWorkFactory`, recording input batches, distinct active session tokens, attempts, successful commits and rollbacks. Give it per-batch entry/release barriers, optional upsert/commit errors and a max-active counter; no real database.

- [ ] **Step 1: Add failing capacity/concurrency tests using controlled barriers.** Use production defaults for the ten-task limit, and small injected bounds for saturation. Assert:

```python
assert writer.enqueue(batch) is True
assert writer.outstanding == 1024  # Queue plus blocked in-flight work.
assert writer.enqueue(next_batch) is False
assert persistence.max_active == 10
assert writer.in_flight == 10
assert len(persistence.active_session_tokens) == 10
```

Define `test_inflight_counts_toward_capacity`, `test_ten_batches_run_concurrently_and_next_starts_on_completion`, `test_empty_and_stopped_enqueue_do_not_write`, and `test_failed_batch_does_not_stop_later_batches`. Release one barrier and observe the next queued batch start without releasing the other nine.

- [ ] **Step 2: Add failing retry/lifecycle tests.** Define `test_three_attempts_then_drop`, `test_each_attempt_has_five_second_timeout`, `test_retry_retains_capacity_and_dispatch_slot`, `test_primary_key_collision_retries_whole_batch`, `test_commit_ack_loss_retries_without_double_release`, `test_shutdown_drains_then_cancels_and_awaits`, `test_cancelled_batch_rolls_back`, `test_dead_dispatcher_rejects_enqueue`, and `test_report_failure_cannot_break_enqueue_or_dispatch`. Verify constants via constructor defaults; inject short timeouts/delays for behavioral tests rather than sleeping five seconds repeatedly. Assert exactly three factory calls for a permanently failing batch, one final outstanding release, zero outstanding/queued work and no surviving write tasks after close.
- [ ] **Step 3: Run `uv --directory backend run pytest tests/unit/application/test_people_writer.py -q`.** Expected: fail because the writer is missing.
- [ ] **Step 4: Implement the queue and dispatcher interfaces.** Use non-awaiting acceptance with a combined outstanding counter. Dispatch only after securing a concurrency slot, keep a bounded set of task references, consume task outcomes, and make completion/cancellation release counters exactly once. Each attempt creates a fresh UoW, awaits one repository call and commit within `asyncio.timeout`. Catch ordinary persistence errors for bounded retry; let cancellation unwind cleanup. Report with fixed-category data and contain reporter failures.
- [ ] **Step 5: Run the new writer suite plus existing application tests and backend lint/type/import checks.** Expected: capacity/concurrency/retry/lifecycle assertions pass without a live database; no change to usage accounting.
- [ ] **Step 6: Commit the port, writer and controlled tests.** Suggested message: `feat: schedule bounded best-effort people writes`.

### Task 5: Wire search, assigned pools, lifecycle and sanitized observability

**Files:** Modify `backend/src/lumiere/application/use_cases/search_people.py`, `bootstrap.py`, `observability.py`; add `backend/tests/unit/test_people_lifecycle.py` and `backend/tests/integration/persistence/test_people_pipeline.py`. Update `tests/fakes/search.py`, API fixture/tests, existing `SearchPeople` and `AppContainer` construction sites (including accounting/observability tests), and relevant `e2e/tests/search-people.spec.ts`. Update `README.md`, `docs/architecture/search-people.md`, and dated amendments in the architecture/F001 specs.

**Interfaces:**
- Require `SearchPeople(catalog: PeopleCatalog, admission: UsageAdmission, clock: Clock, people_queue: PeoplePersistenceQueue)`. Preserve `execute`; select `candidates[:7]`, offer a nonempty batch once, return regardless of a rejected enqueue. Contain ordinary enqueue failures so an unavailable side effect cannot fail search; do not suppress cancellation.
- `FakePeopleQueue(accepted: bool = True, error: Exception | None = None)` records `batches: list[tuple[PersonSummary, ...]]` and implements the queue. Supply it explicitly in existing isolated search tests.
- `AppContainer` owns `services`, `client`, `pools: PoolRegistry`, `admission`, and `people_writer: PeopleWriter`; replace the single owned engine with the registry. Production creates `application` and `people_writer`, binds existing UoWs to the former and `PostgresPeopleUnitOfWork` to the latter, and instruments each engine once.
- Start admission hydration before serving, then start the people dispatcher. On close, run both writer closes concurrently, collect errors, and always close the HTTP client and all pools after writer cleanup, including partial startup failure. Preserve the existing readiness check using the application pool only.
- Add `record_people_write(event: PeopleWriteEvent) -> None` to `observability.py`, using `people.persistence` spans and an explicit allowlist of event kind, outstanding count, in-flight count, attempt, and integer duration milliseconds. Pass it into the writer; preserve telemetry-off behavior.

- [ ] **Step 1: Add failing nonblocking search/API tests.** Create a real `PeopleWriter` over controlled fake persistence, block its commit, execute a search, and assert it returns before releasing the barrier. Assert the queued batch is exactly `candidates[:7]`, duplicates/order are retained, empty search queues nothing, full/stopped/broken queue still yields HTTP 200 with existing cache headers, and provider errors/cancellation before enqueue produce no batch. Verify client cancellation after enqueue does not stop the independent write.
- [ ] **Step 2: Add lifecycle, isolation and privacy tests.** Assert both named pools have `(5, 5)` limits; block people work while usage accounting completes through its own factory; assert no pool is disposed while either writer has active work. Exercise startup hydration failure, repeated close, five-second drain expiration through injected short defaults, cancellation while committing, and cleanup after an individual close raises. Extend telemetry sentinel tests to people events, reporter failure, and both database engines; no input, query, connection parameter or exception text may appear.
- [ ] **Step 3: Run targeted new tests and confirm failures on missing wiring.** Run `uv --directory backend run pytest tests/unit/application/test_search_people.py tests/unit/test_people_lifecycle.py tests/unit/test_observability.py tests/api/test_people.py -q`.
- [ ] **Step 4: Implement integration and update existing call sites.** Keep queue/SQLAlchemy details out of HTTP routes. Ensure the inert OpenAPI exporter still constructs no runtime settings, engines or clients. Use nested cleanup/finally logic so failure in one resource cannot skip disposal of another. Use existing tracing facilities rather than introducing a metrics dependency.
- [ ] **Step 5: Add the disposable-Postgres pipeline check and update architecture docs.** Through the real provider mapper, use case, writer and people-pool UoW, prove selected rows eventually appear with the requested field mappings and stable IDs on repeat searches. Preserve browser-cache behavior; browser tests assert the new response fields and unchanged visible name/department/title presentation. Update diagrams to show search-to-queue and separate pool ownership; document capacity, retries, accepted losses, and twenty-connection maximum. Mark the previous identity-deferral policy superseded with a link to the approved design.
- [ ] **Step 6: Run final acceptance checks.** Run `make generate`, `make test`, `make lint`, `make test-integration`, and `make test-e2e`. Check generation is deterministic by comparing the contract/generated-file diff after a second generation; run `git diff --check`. Expected: all checks pass with only intended generated changes. Report unavailable infrastructure accurately; do not read runtime credentials or use a live application database. The separate real-time cache-expiry suite is unnecessary unless browser-cache behavior changes or existing cache coverage fails.
- [ ] **Step 7: Commit runtime wiring, integration tests and documentation.** Suggested message: `feat: persist people search results asynchronously`.

## Completion and handoff

The plan is self-reviewed against the approved design. Every data field, pool
assignment, scheduling bound, lifecycle rule and contract change has an owning task;
the five review-focus cases are assigned tests above. Do not treat this statement
as evidence that implementation checks have run. After execution, report actual
check results, obtain the required code review under the chosen execution workflow,
and use the branch-finishing workflow for integration.
