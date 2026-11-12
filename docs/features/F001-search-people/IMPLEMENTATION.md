# F001 implementation and review evidence

Implemented against the revised approved feature specification and its embedded
section 4 test plan. The revisions retain content during loading, restore the
initial examples after failure, cache successful responses privately for 60 seconds,
and use the same generic HTTP 500 search contract for invalid input and provider
failure. No unrelated roadmap milestone is implemented.

## Implemented behavior

- The initial light screen presents Cast & Crew, disabled Movies, a named search
  input, Search, and the three approved examples, without discovery I/O.
- Enter, Search, and example selection submit explicitly. Typing alone does not.
  Examples replace the draft and submit their full name immediately.
- Both cores trim surrounding whitespace and enforce 1–100 Unicode code points.
  Case, accents, punctuation, and internal spaces survive. Overlong drafts silently
  preserve the current display. Following the November 12 review revision, blank
  submissions reset the input, results, and loading state to the initial examples
  without a request. Invalid API input never calls metadata discovery.
- TMDB discovery makes one first-page request, omits language/content settings,
  skips malformed people, and preserves the first seven valid people in order.
  Identical names are not merged. No details, enrichment, or pagination are fetched.
- People remain eligible with movie, TV, mixed, or absent hints. Optional malformed
  fields degrade independently; usable titles retain order and are capped at three.
  Missing hints do not leave separators. Portraits use the fixed HTTPS image base,
  a circle mask, and a decorative silhouette for missing/failed images.
- Previous content stays visible while a spinner and polite searching announcement
  indicate loading. Results announce their count; empty results and failures restore
  examples. Expected failures log a generic console message without an Expo LogBox
  notification, visible error, Retry control, or automatic retry.
- Results have no row action. Follow appears on hover and remains disabled; Movies
  is disabled. Keyboard focus is visible, long strings wrap, and a short/narrow
  browser can scroll to the last result without horizontal page overflow.
- Accepted requests are sequenced. Older successes/failures cannot alter a newer
  result or loading state. Duplicate pending queries are ignored, completed queries
  can be repeated, editing alone does not invalidate a submission, and disposed
  controllers ignore completions and subsequent actions.
- Provider operations have a ten-second total deadline. Frontend HTTP operations
  have a twelve-second deadline covering fetch and body decoding and abort on timeout.
- HTTP summaries expose only display fields. Responses use the approved success
  and error cache headers; all search errors have the stable safe body. OpenAPI
  generates the frontend boundary's committed wire types without starting services.
- State remains in memory. There is no persistence, user selection, history,
  following operation, database, queue, worker, or global state library.
- The backend composition root owns the shared async client and optional Logfire
  setup. Request/provider spans are correlated and include safe outcomes, timings,
  counts, and failures. Routine tests do not export telemetry or call TMDB.

## Incremental RED/GREEN record

Each implementation step followed a focused test run. Production changes followed
an observed failure; the focused suite was rerun after the minimum implementation.
The record below summarizes observed failures rather than treating harness errors
as proof of missing product behavior. New modules initially failed collection when
an interface did not yet exist. Additional regression cases also passed against
behavior already introduced; these were not claimed as new RED cycles.

| Increment | Observed RED evidence | GREEN evidence |
| --- | --- | --- |
| Backend query forwarding/trimming | Application module absent | Trimmed Unicode/internal-space query reached fake port; 1 test passed. |
| Backend input bounds | Three invalid queries did not raise | Invalid inputs rejected before port call; Unicode boundaries passed; 6 tests. |
| Ordered seven-person cap | Nine summaries returned instead of seven | First seven retained without merging; application suite 8 tests. |
| Provider fixture and first-page request | TMDB adapter absent | Repository fixture, exact parameters, single request, names/hints/image URL passed. |
| Movie/TV hint normalization | Whitespace and unsupported hints appeared in output | Trimmed usable movie/TV titles retained in order; first three only. |
| Malformed people | Pydantic failure aborted the page | Invalid people skipped before taking seven. |
| Optional-field degradation | Usable people dropped; invalid image URL and raw whitespace escaped | Five failing cases passed with independent fallback and safe logging. |
| Invalid envelopes/all-unusable pages | Provider failure contract absent | Empty page succeeds; malformed envelopes/nonempty unusable pages fail. |
| Provider failures and deadline | Raw HTTPX failures escaped; delayed operation succeeded | 401/429/500/503 and transport failures translated; controlled ten-second deadline passed; adapter suite 21 tests at that step. |
| HTTP success contract | Composition root did not accept an injected metadata port | Exact display-only seven-result body, cache header, trimmed forwarding, OpenAPI passed. |
| HTTP errors/invalid input | Missing input returned 422; other errors lacked approved header/body | All six HTTP cases passed with safe 500/no-store and no invalid-input provider calls. |
| Controller initial state | Controller module absent | Draft editing caused no request. |
| Explicit frontend submission | Subscription/submission behavior absent | Loading then results published through the injected search port. |
| Silent frontend validation | Invalid submissions changed submitted/display state | Three invalid cases and Unicode boundaries passed; 7 controller tests. |
| Duplicate pending query | Corrected focused test observed two calls instead of one | Pending duplicate ignored; completed same query accepted; 8 tests. |
| Frontend failure transition | Rejection escaped the controller | Previous results retained while loading, then examples restored and safe failure logged; 9 tests. |
| Response-order protection | Four cases overwrote results or stopped newer loading | Older success/failure suppressed before and after latest completion; 13 tests. |
| Disposal | Disposal operation absent | Late completions/actions ignored; editing did not invalidate accepted request; 16 tests. |
| Frontend HTTP translation | HTTP adapter absent | Encoded query and generated-wire-to-application translation passed. |
| HTTP failure classification | Wrong/unclassified errors escaped | Safe HTTP and transport categories, no response-payload read or retry. |
| Frontend deadline | Requests had no abort signal/deadline | Fake clocks verified 11,999 ms pending, 12,000 ms timeout, abort, body coverage, and cleanup; 6 adapter tests. |
| Initial UI | Search screen absent | Three named examples, input, Search, disabled Movies, no discovery call. |
| UI submission paths | Each action made zero calls | Enter, button, and example each submitted; typing did not. |
| Loading/results UI | Searching indicator absent | Spinner, retained examples, result hints, announcement, and disabled Follow passed. |
| Portrait fallback | Portrait and fallback nodes absent | Missing/failed decorative portraits retained names/hints; 6 row tests. |
| Root route | Old scaffold heading rendered | Actual Expo route composed the search screen. |
| Backend tracing/privacy | Provider span absent; HTTPX logged full search URLs | Correlated spans, safe attributes/logs, and suppressed routine URL logs passed. |
| Browser hover and silent failure | Follow opacity was always 1; Expo displayed a failure notification | Hover opacity changed 0→1→0; both failure cases restored examples with no notification. |
| Failure telemetry counts/outcomes | Failure spans lacked skipped counts; requests lacked outcomes | Success, upstream failure, and all-malformed cases passed with correlation and privacy. |
| Disposal side effects | Disposed failed request still invoked failure logger | Disposed success/failure produced no subscriber/log side effect. |
| Narrow-browser scrolling | Final row remained outside viewport after wheel scrolling | ScrollView made the seventh result reachable. |
| Required error-schema fields | OpenAPI lacked a required-field declaration for code/message | Both literal fields are required in OpenAPI/generated types; all six HTTP tests passed. |

Refactors extracted provider normalization helpers, refined plain types, removed an
unnecessary effect-driven state update, and applied the existing formatters.
Relevant tests were rerun without weakening expected behavior.

Test corrections made during the work:

1. The duplicate-query test initially awaited an unresolved duplicate before its
   call-count assertion and timed out. Moving the assertion before resolution
   produced the intended two-versus-one RED result; the requirement stayed intact.
2. Portrait queries explicitly include accessibility-hidden nodes, because portraits
   are decorative. Assertions still require their presence and exclusion from
   accessible image roles.
3. Playwright parameterization uses ordinary loops, replacing an unsupported
   Jest-style `test.each`; all cases/assertions were retained.
4. Scaffold-only assertions were updated to the approved feature: the search route
   now exists, and the initial screen is people search instead of the startup text.

Jest setup transforms gluestack's source, supplies React Aria's native-test screen
object, and stubs only Metro's theme engine. Browser tests use the real engine and
verify light presentation even under a dark browser preference.

## Commands and complete-suite results

Focused cycles used these commands with the relevant file or selected browser case:

```sh
uv --directory backend run --locked pytest tests/test_search_people.py -q
uv --directory backend run --locked pytest tests/test_tmdb.py -q
uv --directory backend run --locked pytest tests/test_search_http.py -q
uv --directory backend run --locked pytest tests/test_observability.py -q
uv --directory backend run --locked pytest tests/test_boundaries.py -q
npm --prefix frontend test -- --runTestsByPath tests/search-controller.test.ts
npm --prefix frontend test -- --runTestsByPath tests/search-http.test.ts
npm --prefix frontend test -- --runTestsByPath tests/search-screen.test.tsx
npm --prefix frontend test -- --runTestsByPath tests/person-row.test.tsx
npm --prefix frontend test -- --runTestsByPath tests/startup.test.tsx
npm --prefix frontend run test:e2e -- --reporter=line
npm --prefix frontend run test:e2e -- --reporter=line --grep 'narrow browser can'
```

Supporting validation and formatting commands executed:

```sh
uv --directory backend run --locked ruff check . --fix
uv --directory backend run --locked ruff format .
uv --directory backend run --locked pyrefly check --min-severity=warn
npm --prefix frontend run format
npm --prefix frontend run lint:check
npm --prefix frontend run typecheck
npm --prefix frontend run boundaries:check
npm --prefix frontend run api:generate
make check
make smoke-logfire
```

Sandboxed runs used `UV_CACHE_DIR=/tmp/lumiere-uv-cache` to keep cache writes in a
writable location. Local server checks needed sandbox permission to bind loopback.
HTTPX moved from the development dependency group to runtime dependencies through
uv, preserving the dependency-age policy and lockfile. No npm packages were added.

The full check command covers Python dependency consistency, lint/formatting,
complexity, type checks, real import boundaries, negative boundary probes, backend
coverage, Expo compatibility, ESLint, Prettier, TypeScript, component/controller/HTTP
tests, generated-type drift, a production web build, and real browser workflows.
Final `UV_CACHE_DIR=/tmp/lumiere-uv-cache make check` completed successfully:

- Backend: **45 passed**, **99% statement coverage** (application, domain, HTTP,
  configuration, and composition root: 100%; provider adapter: 98%). The two
  uncovered statements are explicit-null optional-text/path returns; missing
  fields and malformed optional values are otherwise covered.
- Frontend: **43 passed** across five Jest suites.
- Browser: **13 passed** in Chromium, with real Expo/FastAPI and stubbed images.
- Dependency checks, Ruff lint/formatting/complexity, Pyrefly, both import contracts,
  negative boundary probes, Expo compatibility, ESLint, Prettier, TypeScript,
  generated-type drift, and production web export all passed.
- `git diff --check` passed.
- The separate `make smoke-logfire` command did **not** pass: it stopped before
  export because process export configuration was unavailable. It is excluded from
  ordinary checks intentionally and does not count as verified remote telemetry.

## Acceptance review

| AC | Behavior and evidence | Status |
| --- | --- | --- |
| 1 | UI initial state and real browser request-count check | Verified locally |
| 2 | Three UI submission paths; browser Enter/button/example/repeat workflows | Verified locally |
| 3 | Backend/controller Unicode bounds; overlong submissions preserve results, blank submissions restore examples and invalidate prior completions; neither sends a request | Verified locally |
| 4 | Fixture normalization, application cap, exact HTTP response, browser provider order | Verified locally |
| 5 | Row optional-field/portrait tests; browser disabled hover control; circular UI mask | Verified locally |
| 6 | Focused TV-only, mixed, unsupported, and absent-hint fixtures retain people | Verified locally |
| 7 | Empty controller/UI/browser transitions restore initial examples | Verified locally |
| 8 | HTTP/transport tests, safe logging, no retry counts, browser failure/no-notification workflows | Verified locally |
| 9 | Per-person provider validation, unusable-page failure, fixture-backed browser failure path | Verified locally |
| 10 | Controlled promises cover older success/failure before/after newer completion; real browser gated responses | Verified locally |
| 11 | Controlled backend deadline and frontend fake clocks, including stalled response bodies | Verified locally |
| 12 | Reload resets input/results; source/boundary review confirms no durable-data or background-work implementation | Verified locally |
| 13 | Browser keyboard, focus, 320px wrapping/no horizontal overflow, stable form, 375px scrolling | Verified locally |
| 14 | CI command and negative boundary/type-drift checks run locally; workflow uses the same command | Local checks pass; hosted Actions run not triggered |
| 15 | Local exporter verifies request/provider correlation/privacy; explicit remote smoke command attempted | Remote receipt unverified: process export configuration unavailable |

## Manual verification

Run `make fixture-api` and `make web` in separate terminals, then open
<http://localhost:8081>. Fixture mode needs no live metadata provider; ordinary names
return the repository's canned Tom results, including example-name submissions.
For live metadata, use `make api` instead with the backend provider configuration
already supplied in its process environment.

1. Confirm the Cast & Crew heading, empty named input, three examples, and disabled
   Movies control. Check the browser Network panel: no people-search request occurs.
2. Type `Tom`: nothing is fetched until Enter or Search. Submit and check up to
   seven ordered rows with names, circular portraits/fallbacks, and available hints.
   Hover a row to reveal disabled Follow. Clicking a row has no action.
3. Submit the same name again, then another name. Click an example after returning
   to the initial state: its full name fills the input and submits immediately.
4. In fixture mode, submit `Empty`, `Failure`, and `Unusable`. Each restores examples
   and stops the spinner; failures produce only a generic browser console entry.
   There is no error message, notification, Retry control, or automatic retry.
   A subsequent ordinary search works.
5. After showing results, submit an empty or whitespace-only draft with Enter or
   the magnifier: examples return, the input clears, and loading stops without a
   request. Submit more than 100 Unicode code points: results stay in place. Neither
   case displays validation text.
6. Submit `Slow success`, then `Latest`. Confirm the initial content remains during
   loading and the distinct latest result appears. Release the old request with:

   ```sh
   curl -X POST --get --data-urlencode 'query=Slow success' http://127.0.0.1:8000/__test__/release
   ```

   Repeat with `Slow failure`. Neither completion may replace the latest result.
   The control endpoints exist only in the test composition root.
7. Narrow the browser to 320–375px. Submit `Long` to inspect wrapping, then `Tom` and
   scroll to the seventh row. Check for no horizontal page scroll and a consistent
   form position. Tab through the form/examples: enabled controls have visible
   focus; disabled Movies/Follow cannot activate by pointer or keyboard.
8. Refresh. The input/results reset to the initial state. With a screen reader,
   check searching/result announcements and that portraits are skipped.

## Remaining verification limits

- `make smoke-logfire` stopped before export because existing process export
  configuration was unavailable. Configure export externally, rerun the command,
  and confirm `HTTP request` → `TMDB people search` in the printed trace under
  `lumiere-api` in Logfire. Local captured spans are not proof of remote receipt.
- Hosted GitHub Actions has not been triggered; its complete command is exercised
  locally. No commit, push, deployment, or unrelated feature was performed.
- Live-provider availability/latency and native mobile builds were not tested;
  F001 deliberately measures deadlines and fixtures instead. Full assistive-technology
  testing remains a manual review step beyond the automated accessibility checks.
- There are no intentional deviations from the revised product behavior. The
  outstanding external verification prevents claiming all acceptance criteria complete.


## Review revisions — November 12, 2026

These user-requested changes supersede the original blank-submission requirement
and its historical test evidence above. The backend still rejects direct invalid
API input using the approved error contract.

| Revision | RED evidence | GREEN evidence |
| --- | --- | --- |
| Backend environment prefix | Configuration test supplied `LUMIERE_` variables but received defaults. | `Settings` now uses `LUMIERE_`; startup/config tests pass. Runtime scripts, CI, type generation, and README references use the new prefix. |
| Placeholder | Exact wireframe placeholder query failed. | Text now reads `Search for actors, directors, or creative team to follow`; muted placeholder color distinguishes it from unchanged entered-text styling. |
| Search control | Visible `Search` text remained instead of an icon. | Circular magnifier replaces the text, preserving the accessible `Search` name and existing submission behavior. |
| Blank reset | Blank/whitespace submissions retained results and submitted query. | Both now restore initial state without a request; overlong-input assertions remain unchanged. |
| Reset concurrency | Late success replaced reset results; late failure published another state. | Reset advances the request sequence so neither completion can undo it. |

The old blank-input preservation assertions were replaced because the user changed
the requirement. They were not removed to accommodate a failing implementation.
Component coverage checks Enter and button resets with empty and whitespace input;
browser coverage checks actual reset behavior, icon geometry, and computed placeholder
versus entered-text colors.

Revision verification: `UV_CACHE_DIR=/tmp/lumiere-uv-cache make check` passed with
45 backend tests, 43 frontend tests, and 13 Chromium browser tests. Backend coverage
remains 99%. Formatting, lint, complexity, types, dependency boundaries, generated-type
drift, and the production web build also pass. `git diff --check` passes.

To review manually, restart the backend with the renamed `LUMIERE_` settings, open
the web screen, and check the muted exact placeholder and circular magnifier. Search
for a name, clear the input, and press Enter or the magnifier: the three examples
return with an empty input and no additional search request.
