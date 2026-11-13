# Search people

Status: resolved
Labels: ready-for-agent
Planning: accepted on 2026-11-12 (Pacific/Honolulu)

## Problem Statement

Visitors need to find actors, directors, and other cast and crew by name and distinguish people with similar names. Recognizable portraits, departments, and familiar movie or TV titles help them identify the intended Person before working Follow behavior becomes available.

The repository currently contains planning documents and samples, with no runnable application or existing test suite. This first feature must establish a locally runnable web experience and backend without requiring saved catalog data, personal accounts, or the later movie-discovery workflows.

## Solution

Provide a centered Cast & Crew search that follows the supplied initial, loading, and results wireframes. Visitors manually submit a name and see up to seven usable, distinct people from the first TMDB search page in exactly the provider's relative order. Each row contains a name, portrait or placeholder, optional primary department, and up to three recognizable movie or TV titles.

Keep typing separate from submission. Preserve displayed results while the visitor edits a nonblank draft. Clearing the input, including whitespace-only input, restores the initial examples, clears rows, and supersedes pending work. A new submission clears results and shows an inline spinner; only the latest submitted search may update the outcome. Successful searches with no matches and failures both display an empty result area without a message while preserving the entered nonblank draft.

Include disabled Movies and Follow placeholders. Search remains transient: it creates no Follows, catalog records, provider mappings, or app-owned identities. Successful responses permit private browser caching for 60 seconds, without a server-side query cache. Deliver the real-TMDB web/Python workflow locally; public deployment and native delivery follow separately.

## User Stories

1. As a visitor, I want to search people by name, so that I can find a particular actor, director, or other creative contributor.
2. As a visitor, I want one Cast & Crew mode to cover people across roles, so that I do not need to choose a profession before searching.
3. As a visitor, I want example searches on the initial screen, so that I can understand the feature and try it immediately.
4. As a visitor, I want an example shortcut to submit only the person's name, so that its descriptive role does not change the search.
5. As a visitor, I want typing a nonblank draft to leave the current search unchanged, so that I control when a request is submitted.
6. As a keyboard user, I want Enter or Return to submit a name, so that I can search without using a pointer.
7. As a pointer user, I want the search icon to submit a name, so that I have a visible search action.
8. As a visitor, I want to submit any nonblank name, including a single character, so that short names and partial names remain searchable.
9. As a visitor, I want surrounding whitespace removed from my submitted name, so that accidental spaces do not change the request.
10. As a visitor, I want accents and internal spacing preserved, so that the submitted name reflects what I entered.
11. As a visitor, I want blank submission disabled, so that an empty draft does not start a search.
12. As a visitor, I want existing results to remain while I edit a nonblank input, so that drafting another name does not discard what I am viewing.
13. As a visitor, I want clearing the draft or leaving only whitespace to restore the initial examples and clear displayed results without a request, so that I can start over.
14. As a visitor, I want the latest submitted search to finish while I edit a nonblank draft, and clearing the draft to supersede it, so that I can explicitly start over without a late response changing the initial state.
15. As a visitor, I want a new submission to clear old rows and show an inline loading indicator, so that I can see that the submitted search is running.
16. As a visitor, I want a newer submission to supersede earlier requests, so that a late response cannot replace the results I most recently requested.
17. As a visitor, I want search completion to preserve my current input, so that I can refine or repeat the search.
18. As a visitor, I want no more than seven distinct usable people shown, so that the initial result list stays compact.
19. As a visitor, I want results in the provider's returned order, so that the significance of its ranking is preserved.
20. As a visitor, I want fewer results when the first provider page contains fewer usable matches, so that the app does not delay the list to fill a target count.
21. As a visitor, I want duplicate occurrences of the same provider person shown once, so that repeated records do not occupy the list.
22. As a visitor, I want people with missing optional metadata to remain discoverable, so that an absent photo or title does not hide an otherwise usable match.
23. As a visitor, I want each result to show the person's name and portrait when available, so that I can recognize the intended person.
24. As a visitor, I want the same portrait placeholder for missing and failed images, so that unavailable images do not break the result layout.
25. As a visitor, I want the primary department shown when available, so that I have another clue for distinguishing people.
26. As a visitor, I want up to three recognizable movie or TV titles per person, so that familiar work helps me identify them.
27. As a visitor, I want recognition titles to preserve their supplied order and omit unusable labels, so that the app displays the available evidence clearly.
28. As a visitor, I want a successful search with no usable matches to leave the result area empty without a message, so that the initial interface remains minimal.
29. As a visitor, I want failures to leave the result area empty without an error message, so that the initial interface follows the same quiet presentation.
30. As a visitor, I want my draft preserved after failure and explicit resubmission available, so that I can try again without retyping.
31. As a visitor, I want initial examples hidden once I submit, including after an empty or failed outcome, until I clear the input to start over.
32. As a visitor, I want a disabled Movies tab visible, so that the intended search-mode layout is represented before movie search is implemented.
33. As a visitor, I want a disabled Follow placeholder that creates no saved activity, so that the intended row action is represented before following is implemented.
34. As a pointer or keyboard user, I want the Follow placeholder revealed on hover or row focus, so that the row interaction is available through either input method.
35. As a touch user, I want tapping a row to reveal its Follow placeholder and tapping it again to hide it, so that I can inspect the intended action without hover.
36. As a touch user, I want tapping a different row to move the reveal there and new results to reset it, so that at most one touch-revealed control is visible.
37. As a visitor on a narrow screen, I want the search and rows to adapt their spacing while retaining their hierarchy, so that the feature remains usable at different viewport sizes.
38. As a pointer or keyboard user, I want focus indicated around the whole search box when its text field or search button is focused, and disabled actions exposed as disabled, so that I can operate the feature with one clear focus treatment.
39. As a visitor, I want a fresh screen mount or full reload to return to the initial state, so that search history is not restored by this first feature.
40. As a visitor, I want a browser to be able to reuse a successful search response for 60 seconds, so that a repeated search may avoid a network request.
41. As a visitor, I want failed responses excluded from that cache policy, so that a subsequent request can discover service recovery.
42. As a visitor, I want searches and returned people to remain transient application data, so that searching alone does not create saved records or activity.
43. As a maintainer, I want normalized, validated search responses and backend rejection of blank input without a provider call, so that clients receive a small, predictable contract.
44. As a maintainer, I want one bounded provider attempt per backend search, so that automatic retries do not multiply request time or usage.
45. As a maintainer, I want internal timing, outcome, and usage visibility without searched names or returned content, so that silent client failures remain diagnosable without retaining feature data.
46. As a maintainer, I want provider credentials kept server-side, so that the browser can search without holding a TMDB secret.
47. As a maintainer, I want reproducible local startup and behavioral verification with real-TMDB smoke evidence, so that the first feature can be run and reviewed before public delivery.

## Implementation Decisions

- **Architecture:** Use the accepted Expo/React Native for Web TypeScript client and modular async Python backend with ports and adapters. Keep client workflow rules independent of React/platform APIs, provider adaptation behind a backend capability port, and instrumentation outside domain/application decisions. Deliver web first; native release work is separate.
- **Responsibilities:** Build the search presentation, client search workflow/backend-access adapter, normalized application API boundary, backend search operation, async TMDB adapter, and minimum runtime composition/configuration. Introduce only the capabilities needed for this workflow; no catalog persistence or LLM module is required.
- **Search semantics:** Search names across cast and crew, including provider-supported name matching. Do not interpret natural-language role requests or filter people by their displayed department. Leave language and adult-content provider options unset; expose no settings for them.
- **Submission:** Submit manually through Enter / Return, the search icon, or an initial example shortcut. Trim surrounding whitespace, preserve accents and internal spacing, allow single-character names, and disable blank submission. The examples are Timothée Chalamet, Hayao Miyazaki, and Autumn Durald Arkapaw; parenthetical roles are descriptive, not query text. Typing never automatically submits this version.
- **Client state:** Keep the draft separate from the latest submitted name. Editing a nonblank draft retains existing results and does not supersede pending submitted work. An empty or whitespace-only draft resets the submitted name, clears rows and loading, and restores the initial examples without a request. Clearing supersedes pending work, even if the visitor immediately starts another nonblank draft. A new submission clears rows, starts the inline spinner, and supersedes the previous request. Abort superseded requests when possible and ignore all their late results, failures, and loading updates. Completion of active work preserves the current draft, including nonblank edits made since submission.
- **Screen lifetime:** State is local to the mounted screen. Unmount prevents late state updates; a fresh mount or full reload returns to the initial examples. Examples appear before the first submission and after an empty-input reset; they remain hidden while loading and after completed outcomes until the input is cleared. Do not restore searches through application storage or page URLs; query parameters in backend requests are separate from shareable screen URLs.
- **Result selection:** Inspect TMDB person-search page 1 only. A usable person requires a usable provider ID and nonblank name. Skip invalid rows, retain the first valid occurrence of each provider person ID, and take up to seven in their original relative order. Accept fewer; do not sort by popularity, fetch more pages, or make extra detail calls to fill rows.
- **Recognition metadata:** Missing optional metadata does not invalidate the person. Use the supplied primary department and up to three nonblank usable recognition labels in array order. Movie labels come from the movie title field and TV labels from the TV name field. Recognition metadata is not a complete Credit collection and does not introduce television tracking. Omit unavailable secondary text and orphan separators.
- **Portraits:** Resolve the returned profile path against the selected base https://image.tmdb.org/t/p/w180_and_h180_face/ with exactly one joining slash. Missing/unusable paths and failed image loads show the same placeholder. Verify the requested transform during integration; its selection is a user requirement, not a claim of documented support for that size. The client may load the normalized image URL directly without provider search credentials.
- **Application operation:** Expose GET at the people-search API endpoint `/api/people/search`, with the trimmed, URL-encoded name in the `query` parameter. The backend validates, deduplicates, bounds, and normalizes results; clients do not call TMDB search directly.
- **Response contract:** A successful response contains only a `results` list of zero to seven rows, without provider totals or pagination metadata. Each row contains `provider_ref`, `name`, nullable `portrait_url`, nullable `department`, and `known_for` as an ordered list of zero to three title strings. The qualified provider reference contains provider, entity type, and provider ID; use TMDB/person initially and encode the reference's ID as a string. It identifies a transient result, not an app-owned Person. Use API-specific Pydantic boundary schemas and matching TypeScript types/runtime validation, distinct from provider and domain models.
- **Successful empty outcomes:** A readable provider envelope containing no usable people is a successful HTTP 200 response with an empty results list. Display no rows, examples, or additional message, preserve the draft, and stop loading.
- **Failure contract:** Missing/blank application queries are rejected without a provider call. Provider/network/timeout failures, unreadable provider envelopes, and denied admission return HTTP 500 with no required client-facing error details. Invalid individual rows in a readable results list are skipped instead of necessarily failing the search. Do not expose provider exception internals. Browser network failures, non-success responses, and invalid application responses also display zero rows without a message, preserve the draft, and stop loading. This is the deliberate initial status-only failure contract, including rejected input; clients do not require an error body.
- **HTTP caching:** Use `Cache-Control: private, max-age=60` on successful responses, including genuine empty results, and `Cache-Control: no-store` on failures. Preserve default browser HTTP-cache behavior. The GET request URI distinguishes queries; a private browser cache may satisfy a repeated request without reaching the backend. Caching is permitted, not guaranteed. No server-side query-result cache or application-owned client query cache is introduced.
- **Provider attempts:** Each request reaching the backend makes at most one TMDB search attempt after validation/admission, with a bounded timeout and no automatic retry. A visitor may explicitly submit again. Do not add pagination refill, credit ingestion, or detail requests for row presentation. Aborting a client request does not establish rollback or guarantee that the provider avoided already-started work.
- **Transient data:** Searching does not persist inputs/results, catalog entities, provider mappings, or user activity, and creates no app-owned identities. There are no feature-data schema changes and no catalog database prerequisite. Provider order remains authoritative independently of storage; later Follow or saving workflows own their persistence/identity decisions.
- **Disabled actions:** Show Cast & Crew and a disabled Movies placeholder tab. Rows do not navigate to a detail page. Reveal the inactive Follow placeholder on hover or row focus. On touch, the same row tap toggles reveal, another row moves it, and new results reset it. At most one touch-revealed control is visible. Placeholder activation creates no Follow or other saved activity.
- **Visual behavior:** Preserve the wireframes' layout, labels, inline loading placement, and result hierarchy with ordinary application typography and responsive spacing. Indicate focus around the entire search box whenever its text field or search button has focus; suppress individual child outlines within that box. Retain keyboard access and disabled-control semantics rather than requiring a pointer or reproducing the sketches pixel for pixel.
- **Operational data:** Internal timings, outcomes, and usage accounting are permitted, excluding searched names, returned person content, and credentials. Configure instrumentation and ordinary request/access logs accordingly; GET query strings must not leak those names through full-URI capture. Silent client outcomes remain observable internally.
- **Resource bounds:** Retain incoming/outgoing admission boundaries and bounded expensive concurrency. Select concrete timeout, request/input size, concurrency, and local admission settings before implementation. Align client waiting with backend/provider deadlines. Global durable accounting, synchronization/restart behavior, quota values, operator controls, and accepted approximation must be selected and verified before public exposure; no-feature-data persistence does not remove these operational obligations.
- **Architecture alignment:** ADR-0001 already records the agreed Search people exceptions: manual submission before typing/debounce; HTTP 500-only failures with silent UI; a first-page seven-row subset without pagination metadata; and transient search instead of catalog writes. Its broader app-owned identity, provider replacement, future saving, and deployment boundaries remain applicable to subsequent workflows.
- **Deferred tool selection:** The API/HTTP libraries, Expo workspace/package tooling, contract generation/runtime validation, test tooling, module layout, numeric bounds, and local configuration are implementation prerequisites. No framework, timeout number, or database library is selected by this synthesis.

## Testing Decisions

- **Previously confirmed seam:** Q26 and the final Q27 acceptance approved behavioral verification through the rendered search workflow and public API with controlled provider behavior. Use one primary product-level seam: the web workflow through the real application API, substituting the external TMDB adapter for deterministic responses, timing, and failures. Add direct requests to the same public API only where necessary to verify invalid inputs, response contracts, headers, and request-count behavior that the UI alone cannot establish. No further seam confirmation is pending.
- **Good tests:** Assert externally visible behavior and contracts rather than component internals, handler/helper calls, class/package structure, or incidental implementation details. Avoid a separate test seam for each new module. Cover presentation/workflow, backend operation, and provider translation through the highest useful boundary.
- **Prior art:** This checkout has no application implementation, test suite, or existing runtime seam to reuse. The supplied response and wireframes are fixtures/design references, not proof of running behavior or exhaustive provider shapes. Concrete runners and harness tools remain part of the explicit implementation prerequisite.
- **Input and submission:** Check typing causes no search; Enter / Return, icon, and example submission use the correct name; blanks are disabled/rejected without upstream calls; single characters, accents, trimming, internal spaces, and URL encoding follow the contract.
- **Provider selection and mapping:** Supply valid and deliberately partial/malformed responses. Verify page 1 only, unset language/adult options, no automatic retries or filler/detail calls, no more than seven valid distinct people, first valid duplicate retention, and exact relative ordering even when popularity differs. Cover missing optional metadata and mixed movie/TV recognition entries with blank labels and more than three usable labels.
- **Request races and lifecycle:** Control completion order. Verify nonblank draft edits preserve results and do not cancel the submitted outcome; clearing or leaving whitespace resets the screen, stops loading, restores usable examples, and prevents late success/failure/loading updates from leaving the initial state. Verify a later submission clears results and supersedes earlier work, and stale updates cannot affect it. Verify unmount/remount behavior and the absence of restored search history.
- **Empty/failure behavior:** Verify HTTP 200 for readable envelopes with zero usable people; HTTP 500 for the selected rejection/failure cases; no client error-body dependency; no rows/examples/messages after empty or failed completion; preserved drafts; stopped loading; and explicit retry by resubmission without automatic retries.
- **Cache behavior:** Inspect exact success and failure cache headers, including successful empty lists and admission failures. Check browser fetch permits normal caching. In a browser that stores a fresh success response, demonstrate repeat-request reuse; absence of browser storage is not itself a product failure. Do not substitute an application query cache for HTTP-cache verification.
- **Presentation and accessibility:** Check initial/loading/results hierarchy at wide and narrow sizes, keyboard submission and whole-search-box focus (including pointer focus, moving focus to the search button, blur, and narrow layouts), disabled Movies/Follow behavior, hover/focus reveal, touch toggle/move/reset, portrait fallback, and optional text omission. Test disabled actions through observable absence of navigation or saved activity.
- **Operational behavior:** Verify configured bounds and admission stop work without automatic retries or feature-data writes. Capture operational output/settings sufficiently to establish that searched names, returned person content, and credentials are not logged while timing/outcome/usage evidence remains available. Durable accounting/public transport/recovery verification belongs to the public-release prerequisite rather than the local feature test suite.
- **Real integration evidence:** After deterministic verification, perform a minimal configured real-TMDB smoke search and portrait-transform check, plus actual browser cache/header checks. Document the commands and evidence. Credentials are runtime configuration; do not claim a live-provider check or image compatibility from fixture-only tests. No runtime verification is claimed by this specification publication.

## Out of Scope

- Working Follow, unfollow, saved user activity, person-detail navigation, complete Credit retrieval, or Timeline population.
- Movie search; the Movies tab remains disabled. TV recognition labels do not introduce show, season, episode, or television tracking.
- Search-as-you-type, debouncing, natural-language discovery, profession filters, configurable locale/adult settings, pagination, additional provider pages, or more than seven displayed results.
- Search/catalog/provider-mapping persistence, app-owned identity creation from search, catalog database schema/migrations, server-side query-result caching, application-owned client query caches, saved searches/history, shareable search-page URLs, or state restoration.
- Client-facing failure explanations, differentiated recovery codes, automatic retries, retry-until-full result loops, or background jobs/progress channels.
- Personal authentication, private-account provisioning, LLM/gateway features, semantic search, Movie suggestions, imports, or unrelated architecture implementation.
- Public deployment and native delivery as part of the local feature. Public hosting, verified HTTPS/HTTP/2, durable global accounting/recovery, telemetry access/retention, attribution and operational feasibility are separate release prerequisites.
- Selecting the concrete frameworks, test runners, package layout, or numerical bounds in this synthesis; those remain the agreed implementation prerequisite.

## Further Notes

The user accepted the feature decisions through Q26 and confirmed the consolidated planning handoff in Q27 on 2026-11-12 (Pacific/Honolulu). This document synthesizes that accepted conversation without reopening the interview. `Status: open` describes unimplemented feature work; `ready-for-agent` is its triage label, not a claim that the deferred tools or public-release settings have been chosen.

Authoritative local references:

- [Initial wireframe](../../docs/samples/wireframes/feature-search-people-initial-wireframe.png)
- [Loading wireframe](../../docs/samples/wireframes/feature-search-people-loading-wireframe.png)
- [Results wireframe](../../docs/samples/wireframes/feature-search-people-results-wireframe.png)
- [Sample TMDB person-search response](../../docs/samples/api/tmdb/v3/search/person.json)
- [Domain glossary](../../GLOSSARY.md)
- [ADR-0001: application architecture and Search people exceptions](../../docs/adr/0001-app-architecture.md)

The supplied sample demonstrates nullable portraits and both movie and TV recognition objects. It does not guarantee every person has three usable recognition titles or establish all nullable/missing field cases. The selected portrait transform still needs actual integration evidence; retain the user's base unless a failing check requires a follow-up decision.

The accepted implementation sequence remains:

1. Settle minimum implementation tools, contracts, local configuration, and numeric runtime bounds.
2. Implement the transient backend API and provider adaptation.
3. Implement the search screen and client workflow; this can proceed alongside the backend once the contract/tools are settled.
4. Integrate and verify the locally runnable real-TMDB feature, including reproducible startup instructions.
5. Resolve and verify the separate operational gate before public exposure.

Later requirements to Follow/save people trigger persistence and app-owned identity planning. Requests for typing search, broader results, differentiated failure recovery, or native delivery trigger their respective feature decisions. None is silently included here.

## Comments

### Publication from the accepted conversation — 2026-11-12 (Pacific/Honolulu)

Published through the to-spec skill to the repository's local Markdown tracker with `ready-for-agent`. The earlier scratch specification/tickets were absent in this checkout; this publication creates only the requested template-based specification and does not restore removed tickets. The accepted Q26–Q27 testing seam and final planning confirmation carry forward.

### Local implementation completed — 2026-11-12 (Pacific/Honolulu)

Implemented and verified the local Expo/React Native for Web and async Python workflow. The full deterministic suite passed 25 API and 23 browser cases; TypeScript/Python checks and lint passed. A configured real-TMDB browser smoke verified one search attempt, the requested 180×180 portrait transform, actual HTTP-cache reuse, and content-free operational output. The independent standards/spec review found one deadline-configuration gap, which was corrected and rechecked.

See [startup and verification](../../README.md), [implementation choices and evidence](implementation.md), and [two-axis review](review.md). Public deployment, durable global accounting, and native delivery remain the explicitly separate release work.

### Search reset and focus revisions — 2026-11-12 (Pacific/Honolulu)

The user revised clearing behavior: an empty or whitespace-only search input returns to the initial examples, clears results/loading, and supersedes pending work. Nonblank draft edits continue to preserve displayed and submitted work. A submitted nonblank query with no matches still uses the silent empty-outcome behavior. Focus now outlines the whole search box while either the text field or search button is focused. These revisions supersede the earlier clearing and field-only focus behavior. The existing rendered-workflow testing seam remains in use.

Verification: all 27 browser tests passed, including clearing completed work, whitespace-only reset during pending work, ignored late success/failure, usable restored examples, whole-box pointer/keyboard focus, blur, and narrow layout. Prettier, ESLint, and TypeScript checks passed. The narrow-screen focus rendering was visually inspected.
