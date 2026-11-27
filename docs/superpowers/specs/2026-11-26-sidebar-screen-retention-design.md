# Reuse sidebar screens and retain Search

The user requested committing the current timeline fixes before extending
route reuse to Search and Following, and prefers retaining Search's query
and results. The timeline fixes were committed first as `f487282`.

## Approach and behavior

Extend the existing stack's singular-screen configuration to `index` and
`following`. Remove Search's reset-on-blur handler; keep its state local to
the retained route. Completed results and draft edits survive sidebar visits.
A pending search may finish while another destination is visible. Clearing
the input still resets results and cancels pending work; unmounting still
cancels work; a browser reload starts fresh. Following keeps its asynchronous
focus refresh and shared membership state. Timeline behavior stays intact.

Using a tab navigator or adding an application-level search cache would be
broader changes; neither is needed for this behavior. Keep existing URLs,
sidebar presentation, dependencies, and API contracts.

## Validation

Unit tests cover completed and pending searches across blur/refocus. Browser
tests cover retained Search and Following DOM nodes, drafts and results,
mixed sidebar/Back/Forward navigation, input clearing, and reload. Run the
existing timeline browser regression, frontend suite, both typechecks,
frontend lint, and web export.
