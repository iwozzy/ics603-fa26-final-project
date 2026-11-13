# Implement the people-search screen and request workflow

Type: task
Status: open
Parent: [Search people](../spec.md)
Blocked by: 01

## Outcome

Implement the responsive Expo/React Native for Web screen and client workflow against the normalized application contract. Controlled backend responses allow this work to proceed alongside ticket 02.

## Scope

- Match the supplied initial/loading/results hierarchy, labels and examples with ordinary app typography. Include disabled Movies and Follow placeholders, without working Follow or person-detail navigation.
- Submit names only through Enter / Return, the search icon, or an example shortcut. Trim surrounding whitespace, preserve accents/internal spacing, accept single characters, and disable blank submission.
- Keep draft input separate from the latest submitted name. Draft edits/clearing retain existing rows and do not supersede pending work. New submission clears rows, starts the inline spinner and supersedes older requests.
- Use abortable requests and ignore every late result/error/loading update from superseded work. Unmount discards state and prevents late updates; remount starts with examples.
- Use ordinary browser GET caching with the trimmed, encoded query. Validate success responses at runtime; do not add application query caching/history/storage or URL restoration.
- Show zero rows and no message for empty/failure outcomes; preserve the current draft and stop loading. Examples appear only before the first submission. Missing/failed portraits use the placeholder.
- Reveal disabled Follow on hover/focus. On touch, toggle the tapped row, move reveal to a newly tapped row, and reset on new results. Maintain one touch-revealed row and usable keyboard/narrow-screen behavior.

## Acceptance

Check the rendered workflow with controlled responses: manual-only submission, example names, optional metadata, draft changes during work, A/B requests completing out of order, late errors/loading updates, empty/failure states, portrait fallback, touch toggles, disabled actions and mount lifetime. Prove user-visible state rather than component structure. Complete real browser checks in [04](04-local-integration-and-acceptance.md).

## Comments

Created from the settled feature spec. Unstarted; API development is [02](02-transient-search-api.md).
