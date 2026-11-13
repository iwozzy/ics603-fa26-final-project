# Search people

Status: resolved
Scope: planning handoff
Accepted: 2026-11-12 (Pacific/Honolulu)

Plan the first feature: search for people by name and display recognizable results. Feature decisions were settled through Q26, and the user accepted the consolidated planning handoff in Q27 on 2026-11-12 (Pacific/Honolulu). Implementation has not started; all five implementation tickets remain open. Concrete tools and runtime bounds are an explicit prerequisite, and public release has a separate operational gate.

## Delivery destination

A locally runnable Expo/React Native for Web client and Python backend perform real TMDB name searches. Match the supplied wireframes' layout and content hierarchy, with responsive spacing, ordinary application typography, and keyboard access. Preserve ports and adapters on both sides, boundary validation, async backend I/O, and server-side provider credentials from ADR-0001.

This feature needs no catalog database, personal authentication, or LLM integration. Working Follow, movie search, debounced typing search, public deployment, and native delivery are follow-ups. Operational telemetry and accounting are distinct from feature-data storage.

## References

- [Initial wireframe](../../docs/samples/wireframes/feature-search-people-initial-wireframe.png)
- [Loading wireframe](../../docs/samples/wireframes/feature-search-people-loading-wireframe.png)
- [Results wireframe](../../docs/samples/wireframes/feature-search-people-results-wireframe.png)
- [Sample TMDB person-search response](../../docs/samples/api/tmdb/v3/search/person.json)
- [Architecture baseline](../../docs/adr/0001-app-architecture.md)
- [Domain vocabulary](../../GLOSSARY.md)

## Agreed behavior

### Scope

- Search people by name across cast and crew. Role descriptions and natural-language discovery are outside this feature.
- Searching does not create Follows or retrieve a person's complete Credits. Working Follow behavior is a subsequent feature.
- Searching people does not persist search inputs/results, catalog entities, or provider mappings, and does not create app-owned Person or Movie identities in this version. Use the provider's identity only to distinguish transient results. Operational telemetry and usage accounting remain permitted under the separate boundary below.
- Show the Cast & Crew mode and a disabled Movies tab as a placeholder.
- Retain the Follow control from the results wireframe as an inactive placeholder. Reveal it on hover or keyboard focus; on touch devices reveal it after tapping the person row. Rows do not navigate to a detail page.
- On touch devices, tapping the revealed row again hides its Follow control; tapping another row moves the reveal there. At most one touch-revealed control is visible, and new search results reset the reveal.
- The example names act as search shortcuts; their parenthetical roles are descriptive and are not included in the submitted name.

### Submission

- Searches run only on explicit submission through Enter / Return or the search icon.
- Typing alone does not issue a search in this version.
- Debounced search-as-you-type belongs to a future feature. The previously recommended 300 ms delay and two-character minimum were not accepted requirements.
- Accept any nonblank name, including a single character. Trim surrounding whitespace, preserve accents and internal spacing, and disable blank submission.
- Example shortcuts submit only the example person's name.

### Client state and outcomes

- Editing without submission preserves displayed results. Editing does not start a search.
- Submission clears displayed results and shows the inline loading indicator from the loading wireframe.
- Keep the editable draft separate from the latest submitted name. Draft edits, including clearing, preserve displayed results and do not supersede pending submitted work. For example, submitting “Tom” and then drafting “Tim” still allows the “Tom” response to appear until another submission supersedes it.
- A new submission supersedes the previous request. Abort superseded requests where possible and ignore their late completion, including results, failures, and loading-state updates.
- Search state lasts only while the screen is mounted. A full reload or a fresh mount returns to the initial examples; do not persist searches or restore them through URLs or application-owned storage. Ordinary browser HTTP caching may still reuse a repeated request.
- Examples appear before the first submission only. Hide them during loading and after a completed search, including empty or failed outcomes. Draft clearing after a submission does not restore the examples.
- Successful and failed searches preserve the entered input.
- A successful search with no valid people displays no result rows and no additional message.
- Failures are silent in the interface and display no result rows. For backend search failures, the client needs only HTTP `500`; no client-facing structured failure detail is required at this stage. Network failures also produce an empty result area.
- Record failures internally under the existing observability boundary; silent presentation does not authorize hiding failures from maintainers.
- A missing or failed portrait uses the same placeholder.

### Results

- Display at most the top seven valid results from TMDB's person-search endpoint.
- Preserve exactly the endpoint's relative ordering. Do not reorder using popularity, name, department, or local catalog data.
- A valid result has a usable person ID and nonblank name. Missing portraits, departments, or recognition titles do not invalidate the person.
- Inspect provider page 1 only and take its first seven valid people. Accept fewer when that page has fewer valid people; do not fetch further pages to fill the list.
- Deduplicate valid people by provider person ID, retaining the first occurrence, before taking seven results.
- Show each person's name, portrait, primary department, and up to three `known_for` titles as returned by the endpoint.
- Recognition titles may be movies or TV shows; this does not introduce television tracking.
- Use a placeholder for missing portraits and omit unavailable secondary information. Additional provider requests solely to fill row presentation are unnecessary.
- Use `title` for movie recognition entries and `name` for TV entries. Skip blank or unusable labels and keep up to the first three usable labels in the returned array order.
- The user selected `https://image.tmdb.org/t/p/w180_and_h180_face/` as the portrait base, combined with the returned `profile_path` using exactly one slash between them. Missing/failed images use the placeholder; actual transform behavior remains an integration check.

### Provider requests and HTTP caching

- Leave provider language and adult-content options unset, relying on TMDB's current defaults rather than exposing settings or explicitly pinning those values.
- Do not implement server-side query-result caching initially. Requests that reach the backend perform a provider search rather than approximating provider results using the local catalog.
- Use GET with the trimmed name in the query string, allowing the request URI to distinguish searches.
- Send `Cache-Control: private, max-age=60` on successful responses, including genuine empty results, and `Cache-Control: no-store` on failures. Leave ordinary browser caching enabled. A browser cache hit can avoid a backend request; this qualifies the earlier recommendation that every submission reaches TMDB.
- Each backend search makes one TMDB search attempt, with a bounded timeout and no automatic retry. A user may explicitly submit again after failure. Exact timeout configuration remains part of implementation planning.
- Passive browser caching does not make browser presentation responsible for catalog freshness or introduce application-owned client query caching.

## Application API

`GET /api/people/search?query=<URL-encoded trimmed name>`

The backend validates and normalizes the provider response. The API returns only a `results` list, with at most seven rows and no paging controls, provider totals, or implied exhaustive search coverage. The client does not fetch TMDB search directly or hold its credentials. Image loading uses the normalized portrait URL and requires no provider search credentials.

Normalized row fields:

| Field | Contract |
| --- | --- |
| `provider_ref` | Qualified transient reference: provider, entity type, and provider ID. Initially `{ "provider": "tmdb", "entity_type": "person", "id": "31" }`; encode the provider ID as a string in this representation. This is not an app-owned Person ID. |
| `name` | Required nonblank display name. |
| `portrait_url` | Resolved URL using the selected image base, or `null` when no usable profile path is supplied. |
| `department` | Provider's primary department, or `null` when unavailable. |
| `known_for` | Ordered list of zero to three usable recognition-title strings. |

Use API-specific Pydantic schemas, distinct from provider payloads and domain objects. Publish matching TypeScript types and runtime response validation through the tooling selected in ticket 01. Optional absent metadata is normalized to `null` or an empty list rather than invalidating a usable person. Movie labels use `title`; TV labels use `name`; unusable entries are omitted. Schema generation and package/file layout are implementation choices, not new feature behavior.

| Outcome | HTTP response | Cache policy | Client presentation |
| --- | --- | --- | --- |
| Valid provider response, including no usable matches | `200`, `{ "results": [...] }` | `private, max-age=60` | Show returned rows; zero rows shows an empty area. |
| Missing/blank application query | `500`; no required failure body | `no-store` | Normal UI prevents this; preserve input and show no rows if encountered. Do not call TMDB. |
| Provider/network/timeout failure, unreadable provider envelope, or denied admission | `500`; no required failure body | `no-store` | Preserve input and show no rows or message. |
| Browser network failure or invalid application response | No usable success response | Do not create an application cache entry | Preserve input and show no rows or message. |

An unreadable provider envelope is a failed search; a readable results list containing unusable individual rows may still yield a successful empty response. Do not expose provider exception internals or require the client to parse error content. HTTP `500` for these failures is the deliberately simplified initial contract, including input rejection and admission refusal. The UI also silently handles non-success responses from infrastructure outside the application's control.

## Operational boundary

Record internal timings, outcomes, and usage counts, without searched names or returned person content. Ensure instrumentation and ordinary HTTP access logs respect this boundary; a query in a GET URI is not permission to log the full URI. Silent client outcomes remain observable to maintainers.

Retain ADR-0001's incoming/outgoing admission boundaries and bounded expensive concurrency. Initial local execution needs explicit request/concurrency/timeout bounds; choose their concrete settings before implementation. Before public exposure, select and verify global rate/cumulative usage limits, durable accounting and restart behavior, overshoot tolerance, and operator controls. Operational storage does not authorize storing search or catalog data. No new catalog schema investigation blocks this transient feature.

## Architecture relationship

The manual-only trigger explicitly revises ADR-0001's initial debounced-search direction for this first feature. Abortable HTTP requests and the existing backend/provider/client boundaries still apply; debounced typing search is deferred rather than required now.

Provider-wide people search must not be approximated using an incomplete local catalog. For this initial feature, search is transient and performs no catalog or mapping writes; this explicitly revises ADR-0001's general requirement to retain discovered catalog data for people search. App-owned identities, provider mappings, and shared catalog persistence remain boundaries for later workflows that actually retain data, including Follow. Server-side query-result caching is omitted initially; the selected passive browser HTTP caching does not introduce catalog storage.

The user's reason for keeping search transient is to preserve provider-significant result ordering and defer persistence. Provider order is preserved directly from each response; storing entities would not by itself reproduce provider-ranked search or justify answering a query from a partial local catalog.

This feature also narrows ADR-0001's general structured-error contract: search failures expose HTTP `500` without requiring machine-readable error details, and the interface shows an empty result area. Backend failures remain observable internally. Global admission controls still apply and must refuse work through an HTTP failure rather than pretending that rejected work succeeded.

The first-page, seven-row API is a bounded subset without pagination metadata or navigation. Broader search access requires a later feature decision; the Timeline's existing direct-window and navigation requirements are unaffected.

## Verified provider facts

- TMDB's [Search Person](https://developer.themoviedb.org/reference/search-person) operation searches names and aliases. Its documented parameters include required `query`, `page` (default `1`), `language` (default `en-US`), and `include_adult` (default `false`). There is no documented seven-result limit parameter; the application must bound its own output while preserving provider order.
- The local sample contains both movie and TV recognition entries. Read movie labels from `title` and TV labels from `name`; the sample does not guarantee three usable titles per person or a portrait for every person.
- [Image basics](https://developer.themoviedb.org/docs/image-basics) documents base URL + size + image path construction. The supplied `w180_and_h180_face` transform is not listed among profile sizes in the [official configuration example](https://developer.themoviedb.org/openapi/tmdb-api.json); its actual behavior requires an integration check. Retain the user's selected base rather than substituting a different size based solely on this documentation gap.
- HTTP caching can use a GET request's target URI, including its query string, as a cache key. `private` permits private-cache storage while excluding shared-cache storage; `max-age=60` establishes freshness rather than guaranteeing browser storage. Explicit cache directives can also make HTTP `500` responses cacheable; this feature therefore uses `no-store` on failures. Sources: [RFC 9111: cache keys](https://www.rfc-editor.org/rfc/rfc9111.html#section-2), [storage conditions](https://www.rfc-editor.org/rfc/rfc9111.html#section-3), and [private](https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.7).

## Behavioral acceptance

Verify at the API and rendered workflow boundaries with a controlled provider. Use the supplied sample as fixture evidence, plus deliberately malformed/partial responses and controlled request timing; do not claim the sample proves every possible provider shape.

1. Initial state matches the wireframe hierarchy, provides the three example shortcuts, and includes the disabled Movies tab. Typing alone makes no search request; Enter / Return, the search icon, and examples submit the correct name. Whitespace-only input is disabled; accents/internal spacing and single-character names are preserved.
2. Provider page 1 is requested once, with language/adult options unset and no automatic retries, extra fill pages, detail calls, or catalog writes. Invalid people are skipped; duplicate IDs retain their first valid occurrence; at most seven people retain the original relative order even when popularity suggests another order.
3. Rows use movie and TV recognition labels in array order, take up to three usable labels, and tolerate missing optional fields. Portraits use the requested URL base; absent or failed images show a placeholder. Optional text does not leave orphan separators.
4. Submission clears rows and shows the inline spinner. Draft edits/clearing preserve existing rows and allow the latest submitted request to finish. Submit A then B and resolve/fail A last: A cannot change B's rows or loading state. Unmounting prevents late state updates; remount/reload restores the initial examples.
5. Successful empty results and failures show no rows, examples, or additional messages, preserve the current draft, and stop loading. Backend failures use `500`; invalid queries call no provider; unreadable envelopes fail while unusable rows in a valid envelope are skipped.
6. Successful responses, including empty results, have exactly the selected private 60-second cache policy; failures use `no-store`. Browser requests permit default HTTP caching. Verify reuse when the browser stores a fresh response without requiring every browser to cache it.
7. Disabled Follow is revealed through hover/keyboard focus, and through one-row toggle behavior on touch. Disabled controls create no Follow or navigation. Narrow layout and keyboard interaction preserve content and usable submission.
8. Operational signals expose outcomes, timing, and counts without credentials, searched names, or returned content. Configured timeouts/admission deny work within bounds, without retrying or leaking feature data into telemetry/storage.

After deterministic checks pass, perform a minimal configured real-TMDB smoke check and verify the requested portrait transform. Document local startup/configuration commands. Runtime tests and compatibility are future implementation evidence, not claims made by this planning handoff.

## Implementation backlog and explicit deferrals

No feature-behavior questions remain open. The user accepted this consolidated handoff in Q27. The following work is intentionally unstarted:

| Ticket | Scope and dependency |
| --- | --- |
| [01 — Choose minimum implementation tools and bounds](issues/01-implementation-prerequisites.md) | Separate implementation prerequisite: select the API/HTTP tools, Expo workspace setup, contracts/testing tools, numeric runtime bounds, and local configuration. No database stack is required for catalog data. |
| [02 — Implement the transient search API](issues/02-transient-search-api.md) | After 01; implement normalized API, provider adaptation, validation/order/limits, error/cache behavior, local bounds, and operational signals. |
| [03 — Implement the search screen and workflow](issues/03-search-screen-and-workflow.md) | After 01; implement the agreed presentation and request state against the normalized contract; can proceed alongside 02 using controlled responses. |
| [04 — Integrate and verify the local feature](issues/04-local-integration-and-acceptance.md) | After 02 and 03; deterministic behavioral checks, browser-cache/portrait integration evidence, real-provider smoke check, and runnable handoff. |
| [05 — Define and verify public-release operations](issues/05-public-release-prerequisites.md) | Separate gate before public exposure; not a blocker for the locally runnable feature. Addresses hosting, global durable accounting, telemetry/access, attribution, and release verification under ADR-0001. |

Revisit persistence/app-owned identities when Follow or another saving workflow is specified; provider ordering remains authoritative regardless of storage. Revisit typing/debounce when that feature is requested, broader results when seven first-page matches are insufficient, and error detail when clients need differentiated recovery. Movie search, personal accounts, search history/URL restoration, native delivery, and public deployment need their own scope. No model/gateway/semantic-search work is needed here.

## Comments

### Human decisions — 2026-11-12 (Pacific/Honolulu), Q2–Q7

- Q2: Search first; retain a hover-visible inactive Follow placeholder.
- Q3: People search is by name only.
- Q4: Explicit Enter / Return or search-icon submission initially; debounced typing search comes later.
- Q5: Up to three provider-returned recognition titles, regardless of movie or TV type; supplied the portrait base above.
- Q6: Up to seven valid results in exactly the provider's ordering.
- Q7: Cast & Crew search and example shortcuts; retain a disabled Movies placeholder tab.

### Human decisions — 2026-11-12 (Pacific/Honolulu), Q8–Q14

- Q8: A usable ID and nonblank name establish row validity; optional recognition metadata may be absent. Use page 1 only, taking up to its first seven valid results.
- Q9: Trim surrounding whitespace; preserve accents/internal spacing; any nonblank name is allowed; disable blank submission.
- Q10: Accept loading and supersession behavior, except that editing without submission does not clear existing results.
- Q11: Empty results need no message. Failures silently show no rows, with HTTP `500` as the only failure information the client needs. Input is preserved; missing/failed portraits use a placeholder.
- Q12: Retain disabled placeholders; reveal Follow after a row tap on touch devices rather than displaying it permanently.
- Q13: Leave language and adult-content options unset and use provider defaults.
- Q14: No server-side query-result cache; send `Cache-Control: private, max-age=60` for passive browser-cache reuse.

### Human decisions — 2026-11-12 (Pacific/Honolulu), Q15–Q21

- Q15: Draft edits, including clearing, preserve displayed results and permit the latest submitted search to complete. Only another submission supersedes that request.
- Q16: GET with the trimmed name in the query string; successful responses use `Cache-Control: private, max-age=60`, including genuine empty results; failures use `Cache-Control: no-store`.
- Q17: Keep the first occurrence of each valid provider person ID before taking seven people; use up to three nonblank recognition labels in array order.
- Q18: Touch reveal toggles on the same row, moves when another row is tapped, and resets on new results.
- Q19: One TMDB search attempt per backend search, bounded timeout, no automatic retry; explicit resubmission is allowed.
- Q20: No feature-data persistence from people search in this version. The user cited preservation of provider-significant ordering; the proposed catalog/mapping writes were rejected.
- Q21: Search state is screen-local and resets on reload/fresh mount; ordinary browser HTTP caching remains available.

### Human decisions — 2026-11-12 (Pacific/Honolulu), Q22–Q26

- Q22: `GET /api/people/search?query=...` returns a normalized results list containing qualified provider references, names, portrait URLs, departments, and recognition titles. Backend owns validation, deduplication, and the seven-row bound.
- Q23: Reject missing/blank queries without provider calls under the initial HTTP `500` failure contract. Unreadable provider responses fail; bad individual rows are skipped; a readable response with no usable people is successful and empty.
- Q24: No feature-data persistence; internal timings/outcomes/usage accounting are allowed without searched names or returned person content. Durable accounting is required before public exposure.
- Q25: Preserve wireframe layout/labels/hierarchy with ordinary typography and responsive spacing/keyboard access. Examples appear only before the first submission and remain hidden for loading, empty, and failed outcomes.
- Q26: Finish with the feature spec and small implementation backlog. Concrete tools and public-release operations are separate prerequisites; deliver a locally runnable real-TMDB web/Python feature with behavioral checks, leaving public deployment and native delivery to later work.

### Final shared-understanding confirmation — 2026-11-12 (Pacific/Honolulu), Q27

- The user answered “Yes” to accepting the completed planning handoff.
- Planning is resolved. All five implementation tickets remain open; this confirmation accepts the plan and does not begin implementation.
