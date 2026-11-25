# F002: Unfollow people

Date: 2026-11-23

Status: Approved by the owner in conversation on 2026-11-23, including the
builder proposals below. Implementation follows a separately reviewed plan.

## Intent and scope

Complete F002's follow lifecycle: people naturally expect to undo a follow.
Extend the [follow people design](2026-11-23-F002-follow-people-design.md)
and implement the Unfollow action from the
[Following wireframe](../../samples/wireframes/F002-following-screen-wireframe.png).
This amendment supersedes the earlier exclusion of Unfollow from F002.

Keep the existing Expo/React Native client, FastAPI backend, ports and adapters,
guest identity, three-person limit, and durable `follows` table. No migration is
needed. Account prompts, hydration, timeline work, cross-tab synchronization,
confirmation dialogs, and undo controls remain outside this change.

## Approaches

1. Extend the shared serial mutation queue with unfollow intents. Apply successful
   deletion locally after `204`, without fetching another snapshot. This keeps
   follow and unfollow ordered and preserves existing refresh behavior.
2. Remove optimistically, then refresh the list after successful deletion. This
   reconciles other-tab changes sooner but adds a request and failure case.

The owner selected option 1. Reuse the existing action interaction and styling
rather than implementing an independent version for Following.

## Owner decisions

- Unfollow belongs to F002 and is available on Following.
- Match Search's Follow + / Following styling and hover/tap behavior.
- Activating Unfollow immediately removes the person optimistically.
- Use `DELETE /api/v1/following` with `provider` and `provider_id` in the JSON body.
- Removal is idempotent and returns `204 No Content` on success.
- Extend the shared mutation queue; do not add a post-deletion refresh.

## Interaction and state

```text
photo  Matthew McConaughey                         [Unfollow]
       Acting · Interstellar, ...
```

Reuse Search's reveal behavior: mouse hover, keyboard focus with its existing
focus border and Enter/Space activation, and touch first-tap reveal followed by
button activation. Select at most one touch row. Another row replaces selection;
outside touch dismisses without consuming navigation. Scrolling/cancelled gestures
do not activate. Moving onto the revealed button keeps it visible. Clear selection
when its row disappears or the route is left. The final removed row leaves the
existing blank Following screen.

Builder proposals covered by this design approval:

- Remove immediately from the shared projected list, freeing a follow slot and
  making Search show Follow + under its existing reveal rules.
- Preserve confirmed data separately from an ordered list of outstanding follow
  and unfollow intents. Send both kinds through one serial queue. Replay later
  intents over confirmed state after each settlement, so earlier responses cannot
  resurrect a person whose removal is still pending.
- Allow unfollowing an optimistic pending follow. Its removal runs after the
  earlier follow. Allow following someone again while deletion is pending; the
  later follow runs afterward. Reject duplicate actions against the current
  projected membership. These actions must retain click order.
- A successful follow still supplies the full confirmed snapshot. A successful
  DELETE removes only its identity from confirmed data; do not parse a response
  body. Overlay later intents in either case.
- On failure, discard only the failed intent and recompute the projection. A
  failed unfollow restores the person in their previous position unless a later
  intent changes that outcome. Preserve unrelated pending actions. Restore
  keyboard access to a returned row without stealing focus from another control.
- As with follow failures, show no toast/dialog, retry automatically, or trigger
  a reconciliation read. A lost response after commit rolls back locally; another
  Unfollow is safe. Ordinary Following entry/app startup refreshes reconcile.
- If a removal fails after a replacement follow was accepted optimistically,
  restore the original person and let the queued follow settle under the server
  limit. Do not silently discard the original relationship. Hide further Follow +
  actions whenever the projected count reaches or exceeds three.
- Pending mutations survive navigation. Preserve existing stale-read and guest
  generation guards: new-guest events clear all old intents and confirmed state,
  abort old work, ignore obsolete responses, and load the new guest's list.

## API and persistence

The DELETE body is exactly `{"provider":"tmdb","provider_id":4139}`. Reuse
existing strict identity validation, safe integer bounds, guest resolution,
same-origin mutation protection, deadlines, and `Cache-Control: no-store` on
success and failure. Preserve empty `500` failures for invalid input, origin,
session, storage, or deadline errors. Document `204` with no response body and
remove the default advertised `422` for this operation in generated OpenAPI.

### Approved simplification (2026-11-23)

After reviewing the three-query implementation, the owner approved a single
joined DELETE and accepted the revised missing-profile and concurrency behavior.
This supersedes the original requirement that Unfollow lock and verify the guest
profile before looking up the person.

Use a framework-independent unfollow use case and repository removal operation.
In a fresh async transaction, delete the relationship using one parameterized
`DELETE FROM follows USING people`, filtering the resolved profile ID, the
person join, and the requested provider identity. An absent profile, person, or
relationship is a successful no-op after guest identity resolution; missing or
invalid guest credentials still fail. Await commit before acknowledging `204`.
Never call TMDB, create/update people, change other follows' timestamps, or return
internal IDs. Retain bounded cancellation and rollback cleanup.

Follow retains its profile lock around count-and-insert and the three-person cap.
Unfollow does not acquire that lock. Concurrent requests across clients resolve
according to PostgreSQL visibility and row locking: an uncommitted Follow can be
invisible to Unfollow and remain after it commits. The shared client queue still
preserves click order within one application instance. No cross-client mutation
ordering or automatic retry is added.

## Verification and documentation

Verify durable deletion and repeated deletion, profile isolation, missing person
and invalid identity behavior, commit/rollback failures, concurrent follow/delete
visibility and Follow cap enforcement, and the empty `204`/`500` contracts. Verify
optimistic removal/rollback/order, mixed queued intents, replacement at the cap,
stale responses, new guests, navigation, and no mutation-triggered list request.
Browser coverage must exercise mouse, keyboard, real touch, reload persistence,
and final-row removal using fixtures and disposable databases.

Update the original F002 design's deferral references, following architecture,
README/API documentation, generated client contracts, dependency wiring, fakes,
and sanitized HTTP/use-case telemetry. Never read or write secrets or use the
application database. Exact names, shared interaction factoring, and SQL query
shape remain builder decisions within these contracts.
