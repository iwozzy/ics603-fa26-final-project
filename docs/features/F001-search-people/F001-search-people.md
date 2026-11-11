# F001 — Search People: Technical Design

## 1. Purpose and user workflows

F001 implements roadmap milestone M1: an Expo web screen searches TMDB through the application backend and displays up to seven matching people.

This slice establishes the minimum frontend/backend foundation. Persistence, following, identity resolution, and background processing begin in later milestones.

### User stories

- As a movie enthusiast, I can search by a person’s name to find actors, directors, and other creative contributors.
- As someone distinguishing similar names, I can inspect portraits, department hints, and known-for titles.
- As a first-time visitor, I can select an example to try the search immediately.
- As someone refining a search, I can submit another name without reloading the application.

### Primary workflow

1. Open the application’s single search screen.
2. Enter a name and press Enter or activate the search button.
3. The screen clears previous results and displays loading.
4. The backend requests the first TMDB people-search page.
5. The screen displays up to seven valid people in provider order.
6. Edit and submit another name to replace the results.

Typing alone makes no requests. Rows have no selection or detail action. Follow buttons and the Movies control remain visible but disabled.

### Example workflow

The initial screen offers:

- Timothée Chalamet — Actor
- Hayao Miyazaki — Director, Writer
- Autumn Durald Arkapaw — Cinematographer

Selecting an example fills the input with its name and immediately submits it. Example role descriptions are static presentation text.

### Empty, invalid, and failed searches

- A successful search with no results displays the initial state.
- Blank or overlong submissions are silently rejected without changing the current search state.
- Request failures stop loading and leave the results area blank. Errors are logged; there is no error message or Retry control.
- Users can submit another ordinary search after any completed request, including the same name.

## 2. Requirements and UI behavior

### Functional requirements

- Trim surrounding whitespace and accept names containing Unicode, spaces, and punctuation.
- Accept 1–100 Unicode code points after trimming. Do not change case, remove accents, or collapse internal whitespace.
- Submit only through Enter, the search button, or an example selection.
- Fetch only the first provider page and return at most seven valid people.
- Preserve provider ordering; do not add ranking or merge people with identical names.
- Retain people regardless of department or whether their known-for hints contain movies, TV, both, or neither.
- Show each person’s name, portrait or fallback, available department, and up to three known-for title strings.
- Omit unavailable department and known-for text without leaving empty separators.
- Keep search state in memory. Reloading or remounting returns to the initial state.
- Create no catalog records, follows, jobs, or search history.

TMDB searches names and aliases. The adapter will use its people-search endpoint and omit language and adult-content parameters so the provider applies its defaults. ([TMDB people search](https://developer.themoviedb.org/reference/search-person))

### UI states

| State | Presentation and behavior |
|---|---|
| Initial | Active Cast & Crew heading, disabled Movies control, empty search form with placeholder text, and examples below. Wireframe: [F001-search-people-initial-wireframe.png](F001-search-people-initial-wireframe.png) |
| Loading | Previous results and examples remain visible until new results are ready; a progress spinner announces searching. Input and submission remain available. Wireframe: [F001-search-people-loading-wireframe.png](F001-search-people-loading-wireframe.png)|
| Results | Up to seven rows with identification hints and a disabled Follow button appearing on row hover. Wireframe: [F001-search-people-results-wireframe.png](F001-search-people-results-wireframe.png)|
| Empty | Initial state. Search form remains available. |
| Failed | Loading stops; UI returns to initial state. No failure message, notification, or retry control. |

Invalid submissions preserve whichever state is already displayed. Missing or failed portraits use a generic person silhouette and do not change the search state.

### People portraits

The TMDB search person results include profile_path in the response when available. A portrait URL can be constructed using the following base: https://image.tmdb.org/t/p/w180_and_h180_face/ and appending the profile_path to it. 

The app should display the portrait with a circle mask.

### Concurrent submissions

- Every accepted submission receives a monotonically increasing request sequence.
- Only the latest accepted submission can update the displayed state.
- Older successes and failures cannot replace newer results or stop a newer loading indicator.
- Ignore repeated submission of the same normalized query while that query is already pending.
- Editing the input alone does not invalidate a submitted request.
- Ignore completions after screen disposal.

This requires response-order protection rather than a cancellation framework. Each HTTP request still has its own deadline.

### Layout and accessibility

- Use Expo, React Native Web, gluestack-ui, and UniWind.
- Add only components needed for this screen; keep copied library components within the UI adapter.
- Use a light theme, centered content, and a single-column result list.
- Use a maximum content width of approximately 48rem, with fluid width and page padding on narrow browsers.
- Preserve the wireframes’ content hierarchy without reproducing sketch typography or adding the broader application sidebar.
- Keep the form in a consistent position as results change.
- Support keyboard submission, visible focus, accessible input/button names, and loading/result announcements.
- Mark future controls as disabled and prevent pointer or keyboard activation.
- Treat portraits as decorative because the adjacent name identifies the person.
- Allow long names and titles to wrap without horizontal page scrolling.

### Nonfunctional requirements

- Use async backend I/O.
- Bound the complete provider operation to 10 seconds and the frontend HTTP operation to 12 seconds.
- Implement no automatic retries or dedicated manual retry behavior.
- Make one provider search request per valid submitted backend request; perform no detail lookups or enrichment.
- Render results without waiting for portrait downloads.
- Keep domain/application modules independent of HTTP, provider, UI, and persistence frameworks.
- Keep routine tests independent of live TMDB and telemetry export.
- Introduce no global state library, database, queue, or additional monorepo tooling.

No live-provider latency or availability guarantee is introduced. Deadlines and fixture-controlled behavior are the measurable requirements for this slice.

## 3. Contracts, components, and data behavior

### Public HTTP API

**Endpoint:** `GET /api/people/search`

| Input | Contract |
|---|---|
| `query` | Required string; trimmed length 1–100 Unicode code points. |
| Pagination, user ID, locale, content settings | Not supported by the F001 contract. |

**Success:** HTTP 200 with a `results` array containing zero to seven display summaries.

| Summary field | Type | Meaning |
|---|---|---|
| `name` | string | Nonblank display name. |
| `portrait_url` | string or null | Fully formed HTTPS image URL. |
| `department` | string or null | Available department hint. |
| `known_for` | string array | Zero to three normalized title strings. |

Results expose no identity, provider IDs, pagination metadata, totals, or following state. They are transient display summaries rather than persisted Person entities. M2 will introduce stable application UUIDs alongside persistence.

Responses use `Cache-Control: private, max-age=60`. No application search cache is introduced.

### Error contract

At this time, if a search fails for whatever reason, a HTTP status 500 will be returned.

Error response will contain a stable `code` of `SEARCH_FAILED` and safe, generic `message` field of `Unable to complete search.`

Errors preserve the API distinction between invalid input and provider failure even though this slice’s UI displays neither.


Raw upstream responses are never returned to the client.

### Application services and ports

| Component | Responsibility and interface |
|---|---|
| Backend `SearchPeople` operation | Accept a query, enforce input rules, invoke metadata discovery, and return at most seven summaries. |
| Backend metadata-search port | Async `search_people(query)` returning ordered normalized summaries. Exposes no HTTPX, Pydantic, or TMDB types. |
| TMDB adapter | Perform HTTP I/O, validate provider data with Pydantic, normalize hints/images, and translate failures. |
| FastAPI adapter | Validate HTTP input, invoke the application operation, map responses/errors, and publish OpenAPI. |
| Backend composition root | Assemble configuration, operation, metadata adapter, shared async HTTP client, and Logfire instrumentation. |
| Frontend search controller | Own draft/submitted queries, state transitions, validation, sequencing, and disposal independently of React. |
| Frontend search port | Async operation accepting a query and returning frontend application summaries. |
| Frontend HTTP adapter | Call the backend, enforce its deadline, translate generated wire types, and classify transport failures. |
| React screen and components | Bind controller state to controls, examples, result rows, and accessibility behavior. |
| Frontend composition root | Assemble the HTTP adapter and controller and provide the gluestack theme. |

Use plain Python application types and TypeScript application types. Generated OpenAPI types remain in the frontend HTTP boundary.

Use HTTPX for backend HTTP access and `openapi-typescript` for generated frontend wire types. Generate from an application instance that requires neither live provider access nor telemetry export.

### Provider normalization and validation

- Require a response object containing a `results` array. Other provider envelope fields are unused.
- Validate people independently so one malformed person does not fail the whole page.
- A usable person requires a nonblank string name. Ignore unused provider fields.
- Missing or invalid optional display fields degrade to null or empty hints, with malformed values logged.
- For known-for hints, use movie `title` or TV `name`. Ignore unsupported media types and unusable hint entries without discarding the person.
- Preserve hint order and take the first three usable titles.
- Skip malformed people, then take the first seven valid summaries from the first page. Never fetch another page to fill the list.
- A genuinely empty provider array is a successful empty search.
- A nonempty provider array with no usable people is a provider error.

The adapter constructs portrait URLs using a fixed HTTPS TMDB image base and a supported profile size. Missing or unusable paths produce null; the frontend handles download failures locally. TMDB documents image URLs as a combination of base URL, size, and returned path. ([TMDB image basics](https://developer.themoviedb.org/docs/image-basics))

### Persistence and authorization

There is no persistence in F001:

- No SQLAlchemy models, Alembic migrations, database sessions, or Neon connection.
- No local storage, durable browser state, or retained search history.
- No Person, Movie, Credit, Follow, or source-reference records.
- No seeded-user adapter or authorization policy is needed for this shared, read-only operation.
- The client cannot select an acting user.

Browser assets may use normal browser caching; application search responses and state are not persisted.

### Foundation and observability

- Retain the root Python project and introduce a Python `src` layout plus a separate frontend directory.
- Preserve uv, Ruff, Pyrefly, pytest, the complexity limit, and the existing dependency-age policy.
- Use npm with a committed lockfile.
- Establish ESLint, TypeScript checks, jest-expo, React Native Testing Library, and Playwright.
- Add Python import-boundary checks and frontend restricted-import checks.
- Add GitHub Actions checks without provider access or telemetry export.
- Document exact setup, API, frontend, testing, and type-generation commands when implementation creates them.
- Preserve the existing repository security instructions. Configuration comes from the process environment; tooling must not automatically load configuration files prohibited by those instructions.

Logfire records backend request and provider spans, durations, outcomes, skipped-record counts, and failures. Browser failures use console logging. Avoid logging raw request/response payloads and search text. Telemetry export is optional locally and disabled in ordinary tests; an explicit smoke check verifies exported tracing.


## 4. Automated testing and acceptance criteria

### Testing strategy

| Layer | Required scenarios |
|---|---|
| Backend application | Query trimming and Unicode limits; invalid input makes no provider call; ordered seven-result cap; fake metadata failures. |
| TMDB adapter | Repository fixture; first-page request; omitted language/content parameters; movie/TV hint normalization; absent portraits; missing hints; malformed people; all-malformed response; invalid envelope; timeout, rate limit, and upstream failures. |
| HTTP contract | Success/error schemas and statuses; direct invalid requests; no identity fields; response cap; no-store header. |
| Frontend application | Explicit submission; example submission; silent validation; duplicate pending submission; repeat completed submission; state transitions; disposal; late success and late failure suppression. |
| UI components | Required hints; optional-field omission; portrait fallback and image failure; disabled controls; keyboard interaction; loading and empty states; blank failure state. |
| Browser integration | Real frontend and FastAPI with a fixture-backed metadata adapter; search, examples, repeated queries, empty results, provider failure, and delayed responses. Stub external images. |
| Architecture/contracts | Forbidden imports fail checks; generated types match OpenAPI; lint, formatting, type checks, tests, and web build pass. |

Use the existing TMDB JSON as the baseline fixture. Add small focused fixtures for branches it does not exercise within the first seven results.

### Explicit acceptance criteria

1. Initial load displays the search form, three examples, and disabled Movies control without making a provider request.
2. Enter, the search button, and example selection each submit a valid search; typing alone does not.
3. Blank and overlong input sends no request, shows no validation message, and preserves current state.
4. Results contain at most seven valid people in provider order, with no pagination or limit message.
5. Each result displays its name, portrait or fallback, available department, up to three title hints, and a disabled Follow button on hover.
6. People with TV-only, mixed, or absent known-for hints remain eligible.
7. A successful empty result displays the initial state.
8. Provider or transport failure stops loading, returns to the initial state, and logs the failure without a message, Retry control, or automatic retry.
9. Malformed people are skipped; an entirely unusable nonempty response produces HTTP 500.
10. Neither an older success nor an older failure can change the latest submitted search’s display.
11. Request deadlines are verified with controlled clocks or mocked transports.
12. Reload returns to the initial state; searching creates no durable data or background work.
13. UI keyboard behavior and narrow-browser layout pass browser checks.
14. CI passes the applicable checks, including generated-type drift and dependency boundaries.
15. An explicit smoke check confirms correlated backend request/provider spans in Logfire.

## 5. Architectural validation and deferred capabilities

### Decisions validated by F001

| Existing decision | Evidence from this slice |
|---|---|
| Ports and adapters on both sides | Application tests run through fake ports; dependency checks enforce framework independence. |
| Expo/TypeScript and async FastAPI | A complete browser-to-provider search path works through the selected runtimes. |
| Provider isolation | TMDB fields and errors are translated inside its adapter; public summaries use application terminology. |
| Pydantic boundary validation | HTTP and provider inputs are validated without introducing persistence models into application code. |
| REST/OpenAPI and generated wire types | The frontend boundary consumes generated types with reproducible drift checks. |
| Composition-root dependency wiring | Runtime adapters can be replaced with fixtures without changing application behavior. |
| Incremental infrastructure | Search works without introducing infrastructure scheduled for M2/M3. |
| Basic observability | Request/provider tracing and failure logging cover the first runtime path. |

F001 does not validate stable catalog identities, shared catalog persistence, user isolation, transactions, durable jobs, worker recovery, timeline derivation, or AI boundaries. Those remain assigned to later milestones.

### Exclusions and deliberate deferrals

- Following/unfollowing, saved following state, and person details.
- Authentication, seeded identity, and user-owned operations.
- Databases, migrations, catalog reconciliation, and source references.
- Filmography loading, enrichment, workers, queues, and refresh scheduling.
- Pagination, search-as-you-type, ranking, filtering, history, and URL-backed state.
- Movie search, timeline, Watchlist/seen state, imports, AI, and semantic search.
- Language/content settings and native mobile builds.
- Automatic retries, Retry controls, user-visible request errors, and validation messages.
- Global state management, frontend telemetry infrastructure, hosting, and deployment.

The approved roadmap governs milestone scope where the older workflow illustrations include saving follows. Disabled future controls are included by explicit choice; they introduce no behavior or speculative interfaces.
