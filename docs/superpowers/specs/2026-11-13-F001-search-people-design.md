# F001: Search people

Date: 2026-11-13

Status: Draft for owner approval. Product decisions below were agreed in conversation; implementation proposals remain reviewable.

## Intent and scope

Help a user find and recognize actors, directors, and other creative contributors by name, as the entry point to discovering movies through people. Deliver working web search through the Expo client, application API, and TMDB provider. Following is the next feature and receives its own design.

The repository currently contains the approved architecture, wireframes, sample provider data, and Python tooling configuration. There is no existing application implementation to extend. F001 establishes only the client/backend foundations needed for this feature.

### Agreed product decisions

- Submit on Enter/Return or clicking/tapping the search icon. Typing does not initiate search.
- Request only the provider's first page. Select up to the first seven valid people, preserving provider order. Return fewer when page one has fewer valid people; never fetch another page to fill the list.
- A valid person has a usable provider ID and a nonblank name. Missing photo, department, or known-for movies does not disqualify anyone. Apply no additional person filtering or reranking.
- Deliver real search through the full app, using the captured TMDB response for automated verification.
- Do not cache people-search results on the server at this time. Successful client responses carry exactly `Cache-Control: private, max-age=300`, permitting browser HTTP caching.
- Design and implement following separately after search.

### Goals and exclusions

Search must help distinguish people with similar names, handle incomplete display information, and show understandable loading, empty, and failure states. Preserve provider ranking rather than sorting by name, popularity, department, or completeness.

Following/unfollowing, person details, filmography hydration, timeline display, movie search, registration/login screens, AI operations, native releases, and a searchable local people index are outside F001. The Movies tab and Follow action drawn in the wireframes do not become functioning controls in this increment; omit those controls rather than ship dead interactions. Do not scaffold their future services or workers.

Avoid a technically successful feature that silently reranks results, calls the provider on every keystroke, expands to later pages, discards people without photos, or disguises provider failures as no matches.

## Authority and approaches

The [application architecture](2026-11-09-application-architecture-design.md) supplies the platform, dependency boundaries, app-owned identities, guest access, durable usage controls, and observability baseline.

Two delivery approaches were presented:

1. **Working search through the full application, selected by the owner.** Expo views call an app-owned backend contract, with TMDB behind a catalog port. More initial foundation work, but arbitrary-name search is usable at the end.
2. **Fixture-backed screen first, not selected.** Faster UI preview using the captured response, with real search deferred. It would not deliver the requested working feature.

The selected approach originally included persistent search-result caching. The owner explicitly amended it: no server-side people-search-result caching, with private browser caching for 300 seconds instead. This feature-specific exception supersedes the architecture's reusable search-cache policy for people search. It also splits the architecture's first increment into F001 search and a subsequent following feature. Catalog caching and refresh for other future capabilities remain governed by their own designs.

## Interaction and presentation

Use these supplied wireframes as the visual reference, with the scoped control omissions above:

- [Initial](../../samples/wireframes/F001-search-people-initial-wireframe.png)
- [Loading](../../samples/wireframes/F001-search-people-loading-wireframe.png)
- [Results](../../samples/wireframes/F001-search-people-results-wireframe.png)

Text sketch:

```text
Initial:  Cast & Crew
          [Search for actors, directors, or creative team   (Search)]
          Example searches: Timothée Chalamet, Hayao Miyazaki, ...

Loading:  Cast & Crew
          [Matthew                                       (Spinner)]

Results:  Cast & Crew
          [Matthew                                        (Search)]
          (Photo) Matthew Lillard
                  Acting · Scream, Scooby-Doo, Five Nights at Freddy's
          ...up to seven people, in provider order

Empty:    No people found. Try another name.
Failure:  Search is unavailable right now. Please try again.
```

The following details are **author proposals**, rather than additional owner decisions:

- Trim surrounding query whitespace on both client and server. Accept 1–200 Unicode code points after trimming; reject blank or overlong queries without a provider call. Preserve internal whitespace, case, accents, and punctuation. The limit is an application limit, not a claim about TMDB.
- Keep example names as illustrative text in this increment. Their role descriptions are explanatory and are not submitted as search text.
- Keep a draft query separately from the submitted query. Editing leaves the last completed result visible with its submitted query identified. Submitting a new query clears the previous list and error and shows the spinner. Clearing the input returns to the initial state and invalidates any in-flight result.
- Ignore duplicate submissions of the same trimmed query while it is in flight. Allow submitting another query; cancel the prior client request when possible and accept results only from the latest submission. Cancellation does not undo an already-dispatched provider call or its accounting.
- During loading, the input stays editable. Enter/Return can submit the edited query; the icon shows progress for the pending submission and becomes an enabled search action when the draft differs. Do not submit while an input-method composition is active.
- Results contain a name, profile image or silhouette, optional department, and up to three known-for **movie** titles in their existing order. Exclude TV titles from these display hints to match the application's movie scope, while retaining the person even if no movie hints remain. Do not retrieve extra credits to fill missing hints.
- Missing/blank department or movie titles are omitted, without dangling separators or invented metadata. A failed image load uses the same silhouette as a missing image. Result rows are informational in F001.
- Show no pagination, Load more, provider total count, or claim of exhaustive matches. Include a short hint to refine the name when needed.
- Use accessible input/button names, visible keyboard focus, and an announced loading/result/error status. The icon has a usable touch target. Do not move focus away from the input after submission.

An empty provider page, or a page whose individual records are all unusable, produces a successful empty result. A malformed top-level response is a provider failure, not an empty result.

## API and response contract

**Author proposal:** `GET /api/v1/people/search?query=<percent-encoded-trimmed-query>`.

No client-controlled provider, page, limit, language, ranking, or adult-content option is exposed. Fix the result limit to seven in the application use case. The TMDB adapter explicitly sends `page=1`, `language=en-US`, and `include_adult=false`, matching the provider's documented defaults. There is no additional application-level person filtering; future provider selection policies remain outside the domain.

Successful response shape:

```json
{
  "query": "Tom",
  "people": [
    {
      "id": "<app-owned UUID>",
      "name": "Tom Skerritt",
      "department": "Acting",
      "profile_image_url": "https://image.tmdb.org/t/p/w185/example.jpg",
      "known_for_movies": ["Alien", "Top Gun", "Contact"]
    }
  ]
}
```

`department` and `profile_image_url` are nullable; `known_for_movies` is a list of zero to three strings. `people` contains zero to seven items. Do not expose provider IDs, source payloads, pagination metadata, popularity scores, or followed state as this API's public contract. The response query is the submitted trimmed query.

Use app-owned error codes and messages, with an optional retry/reset timestamp. Proposed transport mapping: invalid query `422`, missing/expired guest context `401`, application throttle or quota rejection `429`, provider unavailable/invalid payload `502`, unavailable accounting/persistence `503`, and provider deadline exceeded `504`. Provider throttling becomes an unavailable-provider outcome with retry guidance rather than a leaked TMDB error. The UI distinguishes validation, session recovery, quota reset, provider failure, timeout, and network failure; retry requires another explicit submission. All non-success responses use `Cache-Control: no-store`.

Describe the API with OpenAPI. Generate transport types and runtime validators behind the client HTTP adapter, as required by the architecture. The application use case and domain do not depend on generated transport code.

## Selection and provider translation

1. Validate request and establish admission before external dispatch.
2. Fetch TMDB people search page one, once, using the submitted query. Disable automatic HTTP/SDK retries for F001; a user retry is a separate admitted attempt.
3. Validate the response envelope and inspect records in returned order. The TMDB adapter translates usable provider records into app-owned candidate DTOs, preserving order and keeping source identity metadata behind server boundaries.
4. For TMDB, a usable ID is a strictly positive integer, excluding booleans and coerced strings; a usable name is a string whose trimmed form is nonempty. Use the trimmed name for display. Discard records that fail these requirements. Extra provider fields do not break parsing; malformed optional display fields become missing values rather than disqualifying a person.
5. Select the first seven valid candidates, or all available valid candidates if fewer remain. Do not sort or deduplicate this provider sequence under a new eligibility rule. Any future duplicate policy is a separate decision.
6. Resolve selected source identities to app-owned UUIDs, preserving array order. Serialize the normalized response with the required cache headers.

The application owns the seven-result and first-page policies; the adapter owns the meaning and validation of TMDB fields. Pydantic is used at transport/provider boundaries; plain application/domain types hold the use-case rules. Do not permit validation of one bad record to invalidate an otherwise usable page.

Build image URLs within the provider adapter from a configured HTTPS image base and supported profile size. Verify the chosen configuration against TMDB documentation during implementation; no per-person detail request is needed. The client receives a complete URL and does not construct TMDB paths. Provider image caching is separate from the search-response policy.

## Cache behavior and retained data

Every `200` search response, including an empty list, carries:

```http
Cache-Control: private, max-age=300
Vary: Cookie
```

The browser HTTP cache may reuse that exact GET representation during its freshness lifetime. `private` prevents compliant shared caches from storing it. Reuse is permitted rather than guaranteed: browser settings, eviction, or reload behavior can cause another request. The HTTP adapter uses normal browser caching, without timestamps/random URL parameters, `cache: no-store`, forced revalidation, or middleware headers that negate the specified successful-response policy. Do not add an application query cache, service-worker search cache, localStorage result cache, or server/proxy result cache.

No query-to-results records, ranked page snapshots, provider search payloads, successful-fetch records for search refresh, stale-result fallback, or search-refresh worker is introduced. A valid request that reaches provider dispatch performs a new page-one search. Rate/admission rejection, validation failure, or dependency failure before dispatch can prevent a call; a browser cache hit does not reach the API or spend provider allowance. Without an application result cache, provider downtime is presented as failure for new network requests.

**Author proposal about identities:** retain only durable app UUID ↔ provider/person-ID mappings for the selected people, using a uniqueness constraint and idempotent insert-or-read under concurrency. This preserves the architecture's app-owned IDs and provides stable references for the next feature. This identity registry cannot answer a name search: do not persist names, photos, known-for lists, query strings, or ordered results in it. Mapping entries survive browser cache expiry and API restart. Search-result content remains transient on the server. The owner has not separately requested a broader person catalog store in F001.

Identity mapping and usage/session records are ordinary application state, not a response cache. Database access occurs in short transactions outside provider network calls. If identity resolution fails after provider dispatch, return an uncached dependency error and retain conservative usage accounting for the attempt.

## Application boundaries and minimum foundations

Use the approved technology baseline: Python 3.13+/uv, async FastAPI, Pydantic boundary validation, async SQLAlchemy/psycopg and Alembic for Postgres state; TypeScript/Expo/React Native for web and Expo Router for the client. Preserve ports and adapters on both sides. Logfire instrumentation belongs at composition and adapter boundaries. Do not introduce Pydantic AI or future feature dependencies for this search-only increment.

The backend search use case depends on catalog search, identity resolution, and usage admission/accounting ports. The HTTP adapter handles query transport, session context, HTTP caching, and error serialization. The TMDB adapter supplies provider data; Postgres adapters supply identity mappings, sessions, and durable admission state. Neither core code nor client views import provider/storage internals.

The client view invokes a client-owned search use case/port; the HTTP adapter performs encoding and runtime response validation. React lifecycle glue manages cancellation and current-submission state. Browser cache behavior and cookie transport stay in platform/HTTP adapters.

Guest search is available without registration. Implement the smallest guest-session bootstrap needed for the architecture's server-owned usage identity, using an opaque HttpOnly same-site cookie and durable session/profile records. Bootstrap is noncacheable and completes before the first search request; recover an expired session without repeatedly redispatching a search. Successful search responses do not create or rotate cookies. Session-dependent cache variants use `Vary: Cookie`. Login, credential storage, registration, native session transport, and follow caps belong to later features.

Before any TMDB attempt, enforce durable global and guest/session request limits plus provider daily and cumulative attempt caps through the approved usage port. Apply server-resolved IP abuse controls with trusted-proxy handling; never trust a client-supplied quota identity. Reserve at most one provider attempt per search and count dispatched failures conservatively. No hidden retry layers. Use configurable bounded deadlines, response sizes, connection pools, and concurrency. Deployment must supply documented admission limits before live dispatch is enabled; exact numeric operating thresholds are left to implementation/configuration rather than owner product decisions. Do not use per-process counters as the authoritative ledger. Database/accounting unavailability fails closed for new external dispatch.

Use one same-origin web/API ingress with HTTP/2 where available and Docker-compatible runtime packaging. No hydration or refresh process is required for F001. Supply documented local setup, migrations, and a way to run the web/API together with configured Postgres and TMDB credentials. Hosted deployment and credentials remain environment configuration, not a requirement to publish during planning.

Log correlation, provider latency/outcomes, selected/invalid counts, quota outcomes, and identity-resolution failures. Do not retain raw search payloads or full query strings in default logs/traces, including HTTP access/query-string logging. Credentials and session secrets never reach the client bundle or telemetry. Telemetry is not the usage ledger.

## Verification and acceptance

Use the captured [TMDB fixture](../../samples/api/tmdb/v3/search/person.json), plus focused malformed and incomplete variants. No live provider access is required for ordinary checks.

- For the supplied fixture, return exactly Tom Skerritt, Tom Holland, Tom Hanks, Tom Cruise, Tom Hopper, Tom Hardy, and Tom Welling, in that order. Popularity never changes this order. TV titles in hints do not exclude Tom Hopper or Tom Welling.
- Skip invalid IDs/names before applying the seven-person cap; retain people with missing/invalid optional display fields. Test a page with fewer than seven valid people and assert no page-two call. No qualifying people is a successful empty result; malformed envelope is a failure.
- Each admitted backend search dispatches exactly one page-one provider request with the fixed adapter settings; a repeated network request dispatches again. Assert no result-cache read/write or search-content persistence.
- Verify exact successful `Cache-Control` and cookie variation, including empty results, through the actual HTTP middleware/ingress path. Errors are not cacheable. A browser test against the built app with caching enabled demonstrates that a repeated identical fresh request can avoid API/provider calls; use the selected browser tooling's deterministic cache-expiry mechanism or an opt-in longer check to verify another network request after freshness expires. Do not assert browser-cache behavior using an API-only client.
- Verify stable UUID mappings under repeated and concurrent searches against compatible Postgres, with no query/name/result content stored. Verify durable admission caps and restart continuity, including no dispatch when admission storage is unavailable.
- Exercise initial, loading, populated, empty, validation, provider/network failure, and quota states. Verify both keyboard and pointer submission, no keystroke search, fallback images/text, and a maximum of seven informational rows.
- Delay and reorder responses to verify that an older submission cannot overwrite a newer result or repopulate a cleared input. Double-submit an in-flight identical query and assert no duplicate client dispatch.
- Run backend unit/adapter checks, client interaction tests, API/runtime-validation checks, dependency-boundary checks, lint/type checks, and the focused web end-to-end flow appropriate to this first feature. Do not add tests that merely mirror trivial implementation details.

## Decisions left to implementation

Choose concrete package paths, package manager, UI styling, code-generation/runtime-validation tooling, test runners, migration naming, session-bootstrap route, and deploy host consistent with the architecture. Choose and document numeric operational defaults and timeouts before enabling live calls. These choices must not change the agreed submission, eligibility, order, page, limit, or cache rules.

No product code, scaffolding, dependency installation, or implementation plan is authorized by this draft alone. After owner approval, the next step is an implementation plan.

## References

- [TMDB people search](https://developer.themoviedb.org/reference/search-person): query, page, language, and adult-content parameters.
- [TMDB image basics](https://developer.themoviedb.org/docs/image-basics): image URL composition and configuration.
- [HTTP caching specification, RFC 9111](https://httpwg.org/specs/rfc9111.html): private cache storage, freshness, and request variation.
