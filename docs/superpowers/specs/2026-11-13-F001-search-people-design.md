# F001: Search people

Date: 2026-11-13

Status: Draft for owner approval. Product decisions below were agreed in conversation; implementation proposals remain reviewable. Revised following owner feedback on 2026-11-13.

## Intent and scope

Help users find and recognize actors, directors, and other creative contributors by name, as the entry point to discovering movies through people. Deliver working web search through the Expo client, application API, and TMDB provider. Following is the next feature and receives its own design.

The repository currently contains the approved architecture, wireframes, sample provider data, and Python tooling configuration. There is no application implementation to extend. F001 establishes only the foundations needed for search.

### Agreed product decisions

- Submit on Enter/Return or clicking/tapping the search icon. Typing does not initiate search.
- Use only the provider's first page. Select up to the first seven valid people, preserving provider order. Return fewer when page one has fewer valid people; never fetch another page to fill the list.
- A valid person has a usable provider ID and a nonblank name. Missing photo, department, or known-for titles does not disqualify anyone. Apply no additional person filtering or reranking.
- The first delivery approach, working search through the full application, was explicitly chosen by the owner. Use the captured TMDB response for automated verification.
- Do not cache people-search results on the server. Successful client responses carry exactly `Cache-Control: private, max-age=300`, permitting browser HTTP caching. Omit `Vary: Cookie` at this stage.
- All search API failures return HTTP `500`. The client silently clears the results area and stops loading, with no error or hint message. Successful empty results also leave the results area blank.
- Display up to three known-for titles in provider order, including movie and TV titles.
- Construct profile image URLs using the fixed base `https://image.tmdb.org/t/p/w180_and_h180_face/` and the returned `profile_path`.
- Send only the required search query to TMDB; omit optional parameters so the provider applies its defaults.
- Retain no provider-to-app ID mappings during search. Create those mappings when someone explicitly follows a person in the next feature.
- Omit IDs from the search response. Decide how to capture user selection when designing the following feature.
- Show the initial example-search guidance as supplied in the wireframes. Include no additional hint messages beyond those already shown there.
- Design and implement following separately after search.

### Goals and exclusions

Help distinguish people with similar names, handle incomplete display information, and show loading followed by results or a blank results area. Successful empty results and failures are deliberately indistinguishable in the UI. Preserve provider ranking rather than sorting by name, popularity, department, or completeness.

Following/unfollowing, person details, filmography hydration, timeline display, movie search, registration/login screens, AI operations, native releases, and a local people index are outside F001. Omit the Movies tab and Follow action drawn in the wireframes for this increment. Do not scaffold their future services or workers.

Avoid silently reranking results, calling the provider on every keystroke, expanding to later pages, discarding people without photos, or displaying unsolicited messages. The server still distinguishes failure (`500`) from a successful empty search (`200`) even though both appear blank to users.

## Authority and approaches

The [application architecture](2026-11-09-application-architecture-design.md) supplies the platform, dependency boundaries, guest access, durable usage controls, and observability baseline.

Two delivery approaches were presented:

1. **Working search through the full application, explicitly chosen by the owner.** Expo views call an app-owned backend contract, with TMDB behind a catalog port. More initial foundation work, but arbitrary-name search is usable at the end.
2. **Fixture-backed screen first, not selected.** Faster UI preview using the captured response, with real search deferred. It would not deliver the requested working feature.

The owner amended the selected approach to remove server-side search-result caching and permit private browser caching for 300 seconds. F001 also defers provider-to-app identity mappings until explicit following, uses HTTP `500` for all search failures with a silent blank UI, and permits TV titles as recognition context. These feature-specific exceptions supersede the corresponding search-cache, immediate identity-resolution, typed HTTP-error, and TV-exclusion directions in the architecture. Search candidates are transient display data, not persisted catalog entities. Retained catalog entities in later features still use app-owned IDs. The first increment is split into F001 search and a subsequent following feature. Other future capabilities remain governed by their own designs.

## Interaction and presentation

Use these supplied wireframes as the visual reference, with the scoped control omissions above:

- [Initial](../../samples/wireframes/F001-search-people-initial-wireframe.png)
- [Loading](../../samples/wireframes/F001-search-people-loading-wireframe.png)
- [Results](../../samples/wireframes/F001-search-people-results-wireframe.png)

Text sketch:

```text
Initial:  Cast & Crew
          [Search for actors, directors, or creative team   (Search)]
          Example searches:
          Timothée Chalamet (Actor)
          Hayao Miyazaki (Director, Writer)
          Autumn Durald Arkapaw (Cinematographer)

Loading:  Cast & Crew
          [Matthew                                       (Spinner)]
          (Same example-search guidance as the initial state.)

Results:  Cast & Crew
          [Matthew                                        (Search)]
          (Photo) Matthew Lillard
                  Acting · Scream, Scooby-Doo, Five Nights at Freddy's
          ...up to seven people, in provider order

Empty:    (Blank results area; input remains visible.)
Failure:  (Blank results area; input remains visible; spinner stops.)
```

The example-search guidance remains visible in the initial and loading states as shown in the wireframes. After a search completes, show the results or leave the results area blank; do not replace empty results or failures with guidance. Example names and role descriptions are illustrative text, not interactive search controls in this increment (an author proposal).

The following details are **author proposals**, rather than additional owner decisions:

- Trim surrounding query whitespace on client and server. Accept 1–200 Unicode code points after trimming. Blank or overlong client submissions clear the results without a request or validation message. Invalid requests reaching the API fail with `500` and no provider call. Preserve internal whitespace, case, accents, and punctuation. This is an application limit, not a claim about TMDB.
- Keep the search-field placeholder and agreed example-search guidance from the wireframes. Add no refine-query suggestions or other hint messages.
- Keep draft and submitted queries separately. Editing leaves the last completed result visible. Submitting clears the previous list and shows the spinner. Clearing the input returns to the initial state and invalidates in-flight results. Track the submitted query internally without adding a screen message.
- Ignore duplicate submissions of the same trimmed query while in flight. Allow submitting another query; cancel the prior client request when possible and accept results only from the latest submission. Cancellation does not undo a dispatched provider call or its accounting.
- During loading, the input stays editable. Enter/Return can submit the edited query; the icon shows progress for the pending submission and becomes an enabled search action when the draft differs. Do not submit during input-method composition.
- Display a name, profile image or silhouette, optional department, and up to three nonblank known-for titles in provider order. Read movie titles from `title` and TV titles from `name`; do not exclude TV or retrieve extra credits.
- Omit missing/blank department or titles without dangling separators or invented metadata. Failed image loads use the missing-image silhouette. Result rows are informational in F001.
- Show no pagination, Load more, provider total count, exhaustive-match claim, additional hints, no-results messages, or error messages. Preserve the agreed example-search guidance in the initial and loading states.
- Use accessible input/button names, visible keyboard focus, and a loading/busy state. End the busy state on success or failure without announcing an error or no-results message. Provide a usable touch target and preserve input focus after submission.

An empty provider page, or one whose individual records are all unusable, is a successful empty result. A malformed top-level response is a provider failure. Both yield a blank UI, but their HTTP status and server diagnostics differ.

## API and response contract

**Author proposal:** `GET /api/v1/people/search?query=<percent-encoded-trimmed-query>`.

Expose no client-controlled provider, page, limit, language, ranking, or adult-content option. The application fixes the result limit to seven. The TMDB adapter sends only `query` to `/3/search/person`; omit `page`, `language`, `include_adult`, and other optional parameters. The provider currently defaults to page one, as documented in its search reference. Authentication belongs in the authorization header, not another query parameter. Apply no additional person filtering.

Successful response shape:

```json
{
  "query": "Tom",
  "people": [
    {
      "name": "Tom Skerritt",
      "department": "Acting",
      "profile_image_url": "https://image.tmdb.org/t/p/w180_and_h180_face/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg",
      "known_for": ["Alien", "Top Gun", "Contact"]
    }
  ]
}
```

`department` and `profile_image_url` are nullable. `known_for` contains zero to three nonblank movie/TV title strings in provider order. `people` contains zero to seven items; `query` is the submitted trimmed query.

**Agreed search-only contract:** the response is display-only, with no IDs. Validate source IDs internally for eligibility, then discard them after response construction. Decide how to capture user selection and create mappings when designing the following feature. Do not implement that future contract now. Do not expose source payloads, pagination metadata, popularity scores, or followed state.

The search operation has two response statuses: `200` for success, including an empty list, and `500` for every failure. Failures include invalid/missing query, missing/expired guest context, throttling/quota rejection, provider errors or invalid payloads, deadline expiry, and unavailable accounting/persistence. Override FastAPI's default validation/error mappings for this operation so they do not return other error statuses. Keep internal failure categories for server telemetry and accounting; expose no provider errors or retry/reset guidance. Proposed failure representation: an empty response body with `Cache-Control: no-store`.

On any failed HTTP request, network error, malformed client response, or client deadline expiry, clear the results area and stop loading. Display no error, toast, banner, hint, or no-results message. A server failure remains HTTP `500`; silent behavior is a client presentation rule. The user can submit again explicitly, with no automatic provider retry.

Describe the API with OpenAPI. Generate transport types and runtime validators behind the client HTTP adapter. Application/domain code does not depend on generated transport code.

## Selection and provider translation

1. Validate the request and establish admission before external dispatch.
2. Search TMDB once with only the required query, relying on its default first page. Disable automatic HTTP/SDK retries; a user retry is a separate admitted attempt.
3. Validate the envelope and inspect records in returned order. The adapter translates usable provider records into transient app-owned candidate DTOs. Provider IDs are used only for validity checks; no catalog identity is resolved or retained.
4. For TMDB, a usable ID is a strictly positive integer, excluding booleans and coerced strings. A usable name is a string whose trimmed form is nonempty; use that trimmed name for display. Skip invalid records. Extra fields do not break parsing; malformed optional display fields become missing values rather than disqualifying someone.
5. Select the first seven valid candidates, or all available valid candidates if fewer remain. Do not sort or deduplicate the sequence under a new eligibility rule.
6. Serialize display data in the same order with the required cache header. Create no app UUIDs, source mappings, or person catalog records.

The application owns the seven-result and first-page policies; the adapter owns TMDB field translation. Pydantic validates transport/provider boundaries; plain application/domain types hold use-case rules. One bad record must not invalidate an otherwise usable page.

Build profile image URLs in the TMDB adapter using the owner-specified base `https://image.tmdb.org/t/p/w180_and_h180_face/`. Normalize only the joining slash: `BASE + profile_path.lstrip("/")`. For example, `/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg` becomes `https://image.tmdb.org/t/p/w180_and_h180_face/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg`. Missing/unusable paths become `null`. No configuration or person-detail lookup is needed. Clients receive complete URLs. Provider image caching is separate from search-response caching.

## Cache behavior and retained data

Every `200` search response, including an empty list, carries:

```http
Cache-Control: private, max-age=300
```

Omit `Vary: Cookie` for F001. Successful response contents are independent of guest identity and contain no profile-owned state. Browser cache reuse may span guest-cookie changes in the same browser; followed state is not part of the response.

The browser HTTP cache may reuse the exact GET representation during its freshness lifetime. `private` prevents compliant shared caches from storing it. Reuse is permitted rather than guaranteed: browser settings, eviction, or reload behavior can cause another request. Use normal browser caching without random URL parameters, `cache: no-store`, forced revalidation, or middleware headers that negate the successful-response policy. Add no application query cache, service-worker search cache, localStorage result cache, or server/proxy result cache.

Introduce no query-to-results records, ranked page snapshots, provider search payload retention, successful-fetch records for search refresh, stale-result fallback, or search-refresh worker. An admitted request reaching provider dispatch performs a new search using the provider's default first page. Validation/admission/dependency failure can prevent dispatch. Browser cache hits do not reach the API or spend provider allowance. Provider downtime yields `500` and a silently blank results area for new network requests.

**Agreed identity deferral:** retain no app UUID ↔ provider/person-ID mappings, person catalog records, names, photos, known-for lists, query strings, or ordered results during search. Source data and source IDs are transient on the server. Identity mapping begins only when a user explicitly follows someone in the next feature.

Only usage/session state is persisted for F001. Use short database transactions outside provider network calls. Accounting/storage failures yield an uncached `500`; retain conservative accounting for already-dispatched attempts. Add no catalog/identity-mapping migrations for search.

## Application boundaries and minimum foundations

Use the architecture baseline: Python 3.13+/uv, async FastAPI, Pydantic boundaries, async SQLAlchemy/psycopg and Alembic for Postgres state; TypeScript/Expo/React Native for web and Expo Router. Preserve ports and adapters on both sides. Logfire instrumentation belongs at composition and adapter boundaries. Add no Pydantic AI or future-feature dependencies.

The backend search use case depends on catalog search and usage admission/accounting ports. The HTTP adapter handles query transport, session context, HTTP caching, and failure-status mapping. TMDB supplies transient provider data; Postgres adapters supply sessions and durable admission state. Search has no catalog identity-resolution or persistence dependency. Neither core code nor client views import provider/storage internals.

The client view invokes a client-owned search use case/port. Its HTTP adapter handles encoding and runtime validation. React lifecycle glue manages cancellation and current-submission state. Browser caching and cookie transport stay in platform/HTTP adapters.

Guest search is available without registration. Implement the smallest guest-session bootstrap needed for server-owned usage identity, with an opaque HttpOnly same-site cookie and durable session/profile records. Bootstrap is noncacheable and completes before the first search request; session recovery must not repeatedly redispatch search. If bootstrap/recovery prevents search, leave results blank without a message. Successful search responses do not create/rotate cookies, include profile-owned data, or add `Vary: Cookie`. Login, credentials, registration, native session transport, and follow caps belong to later features.

Before a TMDB attempt, enforce durable global and guest/session request limits plus provider daily and cumulative attempt caps through the usage port. Apply server-resolved IP abuse controls with trusted-proxy handling; do not trust client-supplied quota identities. Reserve at most one provider attempt per search and count dispatched failures conservatively. Use bounded deadlines, response sizes, connection pools, and concurrency with no hidden retries. Deployment supplies documented admission limits before live dispatch is enabled; numeric operating thresholds are implementation/configuration choices. Per-process counters are not the authoritative ledger. Unavailable accounting fails closed before new external dispatch, returning `500` and a blank client result.

Use one same-origin web/API ingress with HTTP/2 where available and Docker-compatible packaging. No hydration or refresh process is needed. Document local setup, migrations, and running web/API with configured Postgres and TMDB access. Publishing/hosted deployment is not part of planning.

Log correlation, provider latency/outcomes, selected/invalid counts, quota outcomes, and internal failure categories. Silent client failure does not erase server diagnostics. Keep raw payloads and full query strings out of default logs/traces, including HTTP access/query-string logging. Do not read, write, mention, or commit secrets, as required by AGENTS.md. Runtime configuration is supplied by the operator; credentials/session secrets never reach bundles or telemetry. Telemetry is not the usage ledger.

## Verification and acceptance

Use the captured [TMDB fixture](../../samples/api/tmdb/v3/search/person.json) and focused malformed/incomplete variants. Ordinary checks require no live provider access.

- Return exactly Tom Skerritt, Tom Holland, Tom Hanks, Tom Cruise, Tom Hopper, Tom Hardy, and Tom Welling from the supplied fixture, in that order. Popularity never changes order. Tom Hopper's titles include The Umbrella Academy, Resident Evil: Welcome to Raccoon City, and I Feel Pretty; Tom Welling's include Smallville, Lucifer, and The Fog, preserving movie/TV order.
- Skip invalid IDs/names before the seven-person cap; retain people with missing/invalid optional fields. Test fewer than seven valid people and no page-two call. No qualifying people is `200` with an empty list; a malformed envelope is `500`.
- Each admitted network search makes one provider request with only `query` and the authorization header. Assert omitted optional parameters, no additional-page/configuration/detail request, no result-cache access, and no search-content persistence. A repeated network request dispatches again.
- Verify exact successful `Cache-Control` and absence of `Vary: Cookie`, including empty results, through middleware/ingress. Errors are not cacheable. A browser test with caching enabled demonstrates that a repeated identical fresh request can avoid API/provider calls. Verify dispatch after expiry using deterministic browser-cache tooling or an opt-in longer check; API-only clients do not prove browser caching.
- Repeated/concurrent searches create no catalog people, app UUIDs, or provider-to-app mappings. Verify durable admission caps and restart continuity, including no dispatch when accounting is unavailable.
- Every search failure category returns `500`, including validation failures normally assigned another status by FastAPI. A successful empty result returns `200` with `people: []`. Both leave the results area blank; network errors and malformed client responses do too. Assert no error, empty-state, validation, retry, refine-query, or other additional hint messages, and that loading stops. Separately verify that the wireframe's example-search guidance appears in the initial and loading states.
- Exercise keyboard/pointer submission, no keystroke search, fallback images/text, and at most seven informational rows. Verify the exact `w180_and_h180_face` image base and a single joining slash.
- Delay/reorder responses so older submissions cannot overwrite newer results or repopulate cleared input. Double-submit an identical in-flight query and assert no duplicate client dispatch.
- Run appropriate backend unit/adapter checks, client interaction checks, API/runtime validation, dependency-boundary checks, lint/type checks, and the focused web end-to-end flow. Avoid tests that merely mirror trivial implementation details.

## Decisions left to implementation

Choose package paths, package manager, styling, code-generation/runtime-validation tooling, test runners, migration naming, session-bootstrap route, and deploy host consistently with the architecture. Choose/document operational thresholds before live dispatch. These choices must preserve the agreed submission, eligibility, order, page, limit, failure, blank-presentation, title, image, identity-deferral, and cache rules.

No product code, scaffolding, dependency installation, or implementation plan is authorized by this draft alone. After owner approval, the next step is an implementation plan.

## References

- [TMDB people search](https://developer.themoviedb.org/reference/search-person): required query and optional-parameter defaults.
- [TMDB image basics](https://developer.themoviedb.org/docs/image-basics): image URL composition. The exact size/base above is owner-specified.
- [HTTP caching specification, RFC 9111](https://httpwg.org/specs/rfc9111.html): private-cache storage and freshness.
