# Preserve the timeline list across route focus changes

The user approved this small change with “Let's try that” after discussing
keeping the list mounted, removing the visit counter from its key, and
preserving inactive-callback guards.

## Behavior and constraints

Keep an existing timeline list mounted when its route loses focus, with its
key scoped to guest identity. Returning must show cached movies immediately
and start the existing asynchronous refresh without waiting for its response.
Inactive or obsolete callbacks must not mutate the timeline. Guest changes
must still discard the old list. Reset any gesture bookkeeping that formerly
depended on remounting so a new visit accepts fresh input.

## Approaches

The selected approach preserves the list instance with a small UI lifecycle
change. Client row reconciliation and server change tracking were discussed
but deferred because they require broader pagination changes. The existing
refresh still replaces its data window; this change targets remount flicker
and does not promise to eliminate every jump during refresh.

## Sidebar route reuse

The user subsequently approved configuring `Stack.Screen name="timeline"`
with `dangerouslySingular` so sidebar returns reuse the existing timeline
route. Keep the sidebar, URLs, asynchronous refresh, and current list-lifetime
guards. A tab navigator remains a broader alternative. Verify repeated sidebar
returns retain the actual scroll node while refresh is pending, with stable
visible rows, and exercise browser Back and Forward.

## Validation

Test retained list identity and cached content while a return refresh is
pending, inactive and obsolete callbacks, guest reset, deep restoration, and
fresh edge gestures after returning. Run the frontend suite, typecheck and
lint. Exercise repeated browser returns with delayed mock API responses.
