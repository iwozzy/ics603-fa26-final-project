# F002: Follow people

Date: 2026-11-23

Status: Draft for owner review. Product decisions below were established in
conversation; the document as a whole has not been approved. Items identified as
author decisions are proposals covered by the eventual document approval.

## Intent and scope

Let guests save the actors, directors, and other creative contributors they find
through search, and return to a list of those people. These selections establish
the user-owned follows that the future movie timeline will consume. This feature
delivers following and the Following page without fetching person details or
filmographies.

Build on the existing Expo/React Native client, FastAPI application, durable guest
identity, and app-owned `people` table. Preserve the ports-and-adapters dependency
boundaries and existing search behavior.

### Owner decisions

- The sidebar is present by default and always contains Search and Following,
  regardless of follow count. Following can be empty. This supersedes the earlier
  proposal to reveal Following only after the first saved follow.
- Search result actions appear on hover or keyboard focus. With touch input, the
  first tap on a result reveals its action. Tapping outside that result, including
  another result, hides its action. Tapping another result reveals that result's
  action instead.
- Clicking `Follow +` immediately changes it to `Following`. A failed save restores
  `Follow +`. There is no unfollow action in this feature.
- Guests can follow at most three people, as established in the architecture.
  At the limit, remaining `Follow +` actions are hidden. The backend also rejects
  attempts to add further follows. Account creation prompts are a separate feature.
- A follow request contains only `provider` and `provider_id`. Resolve that pair
  against the existing `people` table and record a follow only if a matching person
  exists. A missing person returns HTTP `500`, and the client restores `Follow +`.
- Following displays the person summary information already captured during
  search: photo or fallback silhouette, name, department, and recognition titles.
- Full person details, movie credits, timeline hydration, unfollow, registration,
  and account prompts are deferred. The captured
  [details and movie credits response](../../samples/api/tmdb/v3/people/details_movie_credits.json)
  is context for a later feature, not a dependency of F002.

### Goals and anti-goals

Persist a successful follow before acknowledging success; preserve follows across
reloads and backend restarts using the existing guest profile. Display consistent
following state across search results and the Following page. Make repeats
idempotent and enforce the three-person cap under concurrent requests.

Do not create or update people through the follow request, wait for the people
writer, fetch from TMDB, or enqueue hydration. A search result can legitimately
fail to follow because best-effort person persistence has not completed or was
dropped. That is the owner's accepted behavior at this stage.

Do not add movie search, an inert Movies tab, new authentication, durable job
infrastructure, native releases, or a new catalog provider. Never infer follows
from search history or store authoritative follow state in browser persistence.

## Approaches

Three approaches were considered in conversation:

1. Send the selected summary with the follow and insert a missing person in the
   same transaction. This avoids a provider call, but accepts catalog content from
   the client and expands the request. Initially recommended by the author;
   rejected by the owner.
2. Send only provider identity and retrieve missing basic person information from
   TMDB. This keeps catalog content server-sourced, but adds provider latency,
   failures, and usage charging to following. Not selected.
3. Send only provider identity and require an existing matching person. Selected
   by the owner. This keeps the mutation small and uses previously stored catalog
   data, accepting an HTTP `500` and optimistic rollback when the person is absent.

## Existing foundations and constraints

The approved [person persistence design](2026-11-20-search-people-persistence-design.md)
adds app-owned person IDs, unique `tmdb_id`, normalized summaries, and best-effort
background writes. Search returns `provider: "tmdb"` and a positive safe-integer
`provider_id`, but does not expose database person IDs. `people` is not a search
source. Browser-cached search responses do not enqueue person writes.

The approved [durable guest identity design](2026-11-15-durable-guest-identity-design.md)
supplies a stable profile through an HttpOnly cookie. Follow ownership comes from
that resolved profile, never from client-supplied profile information. Losing the
cookie has the existing identity-loss behavior; F002 adds no recovery or merge.

The [application architecture](2026-11-09-application-architecture-design.md)
requires app-owned person references, server-owned follow rules, and transactional
guest-cap enforcement. Its follow-time hydration direction is explicitly deferred
by this feature: no hydration intent or worker is added. Timeline planning will
define how to hydrate both existing and newly created follows.

## User experience

Use the three F002 wireframes, with the owner's later clarifications taking
precedence. The updated
[initial wireframe](../../samples/wireframes/F002-follow-people-initial-wireframe.png)
shows both sidebar entries before any follows. The
[success wireframe](../../samples/wireframes/F002-follow-people-success-wireframe.png)
shows the result action's changed label. The
[Following wireframe](../../samples/wireframes/F002-following-screen-wireframe.png)
supplies the list arrangement; omit its Unfollow action.

```text
Lumière              Search
  Search             [Search people                         Search]
  Following          photo  Person name          [Follow +]  <- revealed
                            Department · Recognition titles

Lumière              Following
  Search             photo  Followed person
  Following                 Department · Recognition titles
```

Both links remain visible while loading, after errors, and with an empty list.
Highlight the current route. Search remains the default landing route; following
does not navigate away from search. Author decision: use `/` for Search and
`/following` for Following, with a shared sidebar outside the route content.
Support direct entry and browser back/forward using Expo Router. Adapt spacing
for narrower web viewports while retaining both navigation destinations; exact
dimensions and styling remain builder decisions within the supplied wireframes.

### Revealing and activating result actions

Hover anywhere within a result reveals its action. Moving from the result content
onto its action does not hide it. Keyboard users can tab to the action, which
reveals on focus with a visible focus indicator; Enter/Space activates `Follow +`.
Keep hidden eligible actions keyboard reachable without exposing invisible pointer
hit targets. Hide the action after focus leaves the row unless hover or touch
selection still reveals it.

For touch, retain at most one selected result. Its first tap reveals the action
without submitting a follow, including when that tap lands where a hidden action
would be. A subsequent tap on the visible `Follow +` submits. Tapping another row
dismisses the previous action and selects the new row without submitting either.
Tapping outside the selected row dismisses it. Tapping inside an already selected
row leaves it selected. Clear touch selection on result replacement, search
clearing, or leaving Search. Distinguish touch input from synthesized mouse events
and keyboard focus so a touch dismissal does not leave the old action visible.
Do not consume the outside tap: navigation and other controls still operate.
Scrolling gestures must not select results or trigger follows.

`Following` uses the same reveal rules. It is a status with no mutation or unfollow
behavior; expose its state accessibly. While saving, prevent repeated activation
for that identity. Duplicate appearances of one provider identity reflect the
same pending or saved state.

### Optimism, limits, and failures

Author decisions for client state:

- Count unique saved plus pending provider identities toward the client limit.
  Clicking the third immediately hides all remaining `Follow +` actions, including
  for keyboard and touch input. `Following` statuses can still be revealed.
- A rejected save removes that pending identity, restoring the eligible action and
  releasing its provisional slot. Preserve search results and query. Use the
  button rollback as the failure feedback, with no added toast, dialog, or account
  prompt. A pending result stays `Following` until its request settles.
- Use current stored summaries for saved follows, rather than retaining a frozen
  per-follow copy of the search result. Catalog summary updates can change the
  Following display without altering follow ownership.
- List people in first-follow order, oldest first, with person ID as a stable tie
  breaker. Repeating a follow preserves its original position.
- An empty successful list is a blank content area. While initially loading, show
  a modest activity indicator. On an initial load failure, stop the indicator and
  leave the area blank. Retain previously confirmed data on refresh failure.
  Track failure separately from a confirmed empty list internally. Do not offer
  new follows until the initial saved-follow state is known.

A lost response can occur after commit, so HTTP/client failure cannot prove a
follow was not saved. First roll back the optimistic action on any failed request,
then make one bounded list refresh to reconcile. A saved follow discovered by that
refresh becomes `Following` again. Do not automatically repeat a failed mutation.
If the refresh also fails, retain confirmed state and permit a deliberate retry
subject to the known limit; the backend remains authoritative. Successful repeat
requests do not duplicate a follow, including when the guest is already at three.

## HTTP contracts

Author decisions: add `GET /api/v1/following` (`listFollowing`) and
`POST /api/v1/following` (`followPerson`). Both use existing guest bootstrap and
cookie resolution and return `Cache-Control: no-store` on success and failure.
Run the existing same-origin mutation protection for POST.

The POST JSON body has exactly these fields; reject additional fields:

```json
{"provider": "tmdb", "provider_id": 4139}
```

Validate provider against the existing application vocabulary and `provider_id`
as an integer in `1..2^53-1`, excluding booleans, strings, and fractional values.
An unsupported provider fails without a database lookup or provider call.

Both successful operations return HTTP `200` with the same snapshot shape:

```json
{
  "people": [
    {
      "provider": "tmdb",
      "provider_id": 4139,
      "name": "Tom Skerritt",
      "known_for_department": "Acting",
      "profile_image_url": "https://image.tmdb.org/t/p/w180_and_h180_face/oWFCyBLm1lsbsbT5Nmx3SPMaqFZ.jpg",
      "known_for": ["Alien", "Top Gun", "Contact"]
    }
  ],
  "limit": 3
}
```

Return `people: []` for a profile with no follows. Return the same summary fields
and image URL construction as search; do not expose database person IDs or profile
IDs. POST returns the full snapshot after recording or recognizing the follow,
and only acknowledges success after transaction commit. GET reads summaries and
membership together in one query so the list is a coherent database snapshot.
Since only guests exist and each has at most three follows, pagination is not
needed. Revisit the list contract when uncapped authenticated access is designed.

Missing people must return an empty HTTP `500` as requested. Author decision:
use the same empty `500` response for cap rejection, invalid input, unsupported
provider, failed identity/origin checks, deadlines, and storage failures, matching
the current silent failure conventions. Keep finite internal failure categories
for diagnosis. Align validation handling and OpenAPI with actual responses so the
new operations do not advertise a `422` they never return.

Do not add profile-specific flags to search responses: search remains independently
cacheable with its current private browser HTTP cache. The client combines search
summaries with the separately retrieved following snapshot by provider identity.
No new provider usage or provider quota charges occur in either new endpoint.

### Recognizing a newly created guest

Author decision: extend the existing `POST /api/v1/guest-session` success response
with `X-Lumiere-Guest-Created: true` or `false`, derived from the existing
`GuestBootstrap.is_new` result. Preserve its empty `200` body, cookie renewal, and
`no-store` behavior. This exposes no credential or profile identifier. Document
the header in OpenAPI and validate it in the shared client session adapter.

Only a successful bootstrap that creates a new profile advances the client guest
generation. Revalidating an existing guest returns `false` and preserves following
state. Marking bootstrap readiness stale after a transient search failure does
not itself signal an identity change. Publish a creation event only from the
current successful bootstrap generation, never from a superseded request.

On a new guest event, drop unsent mutations from the previous guest, invalidate
its in-flight read/mutation responses, clear its confirmed and optimistic follows,
and load following for the new guest before offering actions. An already dispatched
request might still commit for its original guest; its response must not update
the new guest's UI. Serialize bootstrap completion, generation notification, and
queue dispatch so queued work for the previous guest cannot proceed after the
creation event. Initial bootstrap creating a guest naturally uses the same path.

This covers the existing missing/unknown-cookie bootstrap behavior. Deliberately
replacing the cookie with another already valid guest's credential while the app
is open is outside this flow; reload after such manual changes. Account switching
and deliberate identity transitions remain part of authentication planning.

## Persistence and transaction rules

Author decision: add `person_follows` in the next forward Alembic migration after
the current migration head (`0007_people` at design time).

| Column | Storage and rules |
| --- | --- |
| `profile_id` | UUID, non-null FK to existing `guest_profiles.id` |
| `person_id` | bigint, non-null FK to `people.id` |
| `followed_at` | timezone-aware timestamp, non-null, assigned on insertion |

Use `(profile_id, person_id)` as the composite primary key. Follow state references
the app-owned person ID; TMDB identity remains a catalog lookup concern. The
existing profile table is sufficient for this guest-only feature; do not introduce
another profile abstraction or authentication schema. Preserve existing guest and
person data in the migration. Downgrade removes only F002 follow data/schema.

Use the existing `application` pool for synchronous follow/list operations. The
people-writer pool remains dedicated to background person writes. Use an
application-owned following unit-of-work port backed by a fresh adapter session per
operation. Domain/application layers do not import ORM, HTTP, or provider clients.

For POST, after resolving the requesting guest:

1. Begin a transaction and lock that guest profile row (`SELECT ... FOR UPDATE`).
   Reject a missing profile; cached identity resolution is not proof that the row
   still exists. This lock serializes follow changes for the same profile across
   requests and processes.
2. Resolve the supplied provider identity to the local app-owned person. For
   `tmdb`, match `people.tmdb_id`. A missing row aborts with HTTP `500` without
   creating a person or waiting for the background writer.
3. If the profile already follows that person, return success without changing
   `followed_at`, even at the cap.
4. Otherwise count existing follows under the same profile lock. At three, reject
   and roll back. Below three, insert the follow.
5. Read the resulting following snapshot, commit, then return HTTP `200`.

All F002 mutations must take the same profile lock before checking membership and
count. The composite key also prevents duplicate rows. Count and insert must never
be separate transactions. The three-follow rule belongs to the use case; locking,
lookup queries, and constraints belong to adapters behind ports. Represent the
guest limit as a named application policy value of three; no new environment
configuration or durable usage counter is needed for current follow count.

GET requires no profile write lock. Both endpoints require storage availability,
even if the guest identity is cached. Preserve bounded request deadlines and
transaction cancellation cleanup. A follow is never queued or acknowledged on a
best-effort basis. Restart persistence of follows does not depend on single-process
in-memory state, though the existing search accounting deployment remains limited
to one backend process.

## Client architecture and synchronization

Add application use cases and ports for listing and following, with HTTP adapters
responsible for generated transport definitions, runtime validation, guest session
bootstrap, response mapping, and deadlines. Keep generated types out of UI and
domain modules. Reuse the existing guest-session adapter instance for search and
following so bootstrap requests are shared.

Keep one following state owner above both routes. Its confirmed snapshot, pending
identities, load state, and mutation lifecycle survive navigation. A pending follow
must settle even if its originating search row unmounts. Reuse PersonRow display
content for Following without attaching search selection behavior there.

Author decisions for bounded synchronization:

- Load following on application entry, and refresh when either route is entered
  again or the browser returns to the foreground. Deduplicate equivalent in-flight
  reads. Failure handling follows the rules above; no polling or cross-tab event
  infrastructure is added.
- Optimistically register each accepted click immediately, but send follow
  mutations sequentially from the shared state owner. At most the three available
  identities can be pending. This keeps mutation response snapshots ordered while
  still allowing users to select several people quickly.
- Overlay remaining pending identities on each confirmed server snapshot. Never
  lose another pending follow when one request succeeds or fails. For optimistic
  Following rows, use the selected search summary until the server supplies its
  stored summary. Remove that optimistic row if saving fails.
- Guard list responses against obsolete state: a read begun before a mutation may
  not overwrite that mutation's result. Invalidate superseded reads and schedule a
  fresh read when needed; completion ordering must not restore an older snapshot.
  Apply the guest-generation rules above when bootstrap reports a newly created
  profile. A transient search failure must not discard confirmed follows merely
  because the existing session adapter marks its bootstrap readiness stale.
- Other tabs can temporarily display stale counts. Backend cap rejection followed
  by the one bounded refresh reconciles them. Immediate real-time synchronization
  between tabs is outside scope.

Keep search input/results when switching between Search and Following during the
same app session. Author decision: lift search interaction state above route
unmounts or retain its screen instance; the builder chooses the mechanism. This
avoids requiring another charged search just to return to the results. Existing
query validation, cancellation of superseded searches, response ordering, and
silent search failures remain intact.

## Observability and verification

Extend the existing sanitized HTTP/use-case telemetry for follow/list operations,
latency, and finite categories such as missing person, cap reached, invalid identity,
origin, deadline, and storage. Do not log names, request bodies, cookie values,
profile IDs, provider IDs, or raw exceptions. Reuse parameterized queries and the
existing SQL parameter-hiding behavior. No external provider telemetry is expected
for F002. Do not read or write secrets or connect to the application database.

Verification must cover:

- Use cases: matching person follow, missing person failure, cap rejection,
  existing-follow success at the cap, transaction rollback, and no catalog calls or
  people writes. Test with fake ports independently of frameworks and databases.
- Disposable PostgreSQL: migration upgrade/downgrade, FK and uniqueness constraints,
  stable first-follow ordering, same-person concurrent requests, and distinct-person
  concurrent requests starting from two follows. Exactly one new distinct follow
  can succeed from two, regardless of request timing. A failed transaction leaves
  count unchanged; a committed follow survives a new session/process.
- API/contract: exact request shape, safe integer bounds, extra field rejection,
  cookie ownership, cross-origin rejection, empty `500` and no-store headers,
  successful empty list, current summary mapping, and commit-before-success.
  Check the bootstrap creation header for new and returning guests while retaining
  the existing empty body and cookie behavior.
- Client: optimism, rollback, duplicate identities, hidden actions at three including
  pending slots, initial unknown state, sequential queued mutations, response/read
  races, ambiguous commit reconciliation, navigation during saves, and search
  state preservation. Failed refresh must not erase confirmed follows.
  Prove new-guest events clear old state, discard unsent old-guest mutations, and
  ignore old in-flight responses, while ordinary readiness invalidation and
  returning-guest bootstrap preserve confirmed follows.
- Browser: persistent sidebar and empty Following; follow and reload; search status
  overlay over browser-cached results; mouse hover into the button; keyboard focus
  and activation; touch first-tap reveal, second-tap activation, switching rows,
  outside dismissal, and scrolling without activation. Verify touch dismissal is
  not defeated by synthesized hover/focus. No Unfollow or Movies action appears.
- Contract generation, affected tests, lint, type checks, and existing architecture
  import checks. Use the disposable integration/e2e harnesses and fixture provider;
  do not use live TMDB or the application database. Browser checks must accommodate
  the accepted race where a follow precedes best-effort person persistence.

During implementation, update README and architecture documentation with the new
endpoints, follow storage, accepted missing-person behavior, input interactions,
and deferral of hydration. Add a dated amendment linking this approved feature
design from the architecture so prior follow-time hydration text is not mistaken
for the F002 delivery contract.

## Decisions left to the builder

Choose module/class names, port granularity, SQL query factoring, shared-state
mechanism, and input-event handling within the contracts above. Choose exact
sidebar dimensions, responsive spacing, and loading-indicator styling consistent
with the existing app and wireframes. Keep these as local decisions rather than
introducing a generic state framework, scheduler, or future feature scaffolding.

Changes to request identity fields, missing-person behavior, optimistic rollback,
guest cap, persistence guarantees, touch interaction, or deferred scope require an
explicit design revision. The author's proposed ordering, endpoint/response shape,
error conventions, loading behavior, and synchronization defaults are subject to
the owner's review of this draft.
