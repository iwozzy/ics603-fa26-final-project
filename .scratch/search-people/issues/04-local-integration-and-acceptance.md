# Integrate and verify the locally runnable feature

Type: task
Status: open
Parent: [Search people](../spec.md)
Blocked by: 02, 03

## Outcome

Deliver a locally runnable real-TMDB web/Python feature with reproducible startup/configuration instructions and evidence for the spec's behavioral acceptance criteria.

## Scope

- Connect the actual screen and backend, checking URL encoding, runtime contract validation, error/header behavior, and server-only credentials.
- Run deterministic API/workflow checks from tickets 02 and 03. Use controlled provider timing/failure at the real application boundary to verify races and silent outcomes.
- Check the initial/loading/results layouts in a browser at wide and narrow viewports, keyboard behavior, and touch reveal behavior.
- Verify success/empty/failure cache headers and that browser fetch permits ordinary cache reuse. Where a fresh response is stored, confirm a repeat can reuse it; absence of browser storage is not itself a feature failure.
- Perform a minimal configured real-provider search and portrait check using `w180_and_h180_face`. Verify the actual transform rather than assuming it is documented; keep the supplied base unless a failing integration requires a design follow-up.
- Verify that no catalog/user data is written and that normal instrumentation/access logs omit searched names, result content and credentials.
- Document setup, commands, required configuration, checks performed and remaining limitations. Leave public hosting/native delivery to separate work.

## Acceptance

- Every behavioral criterion in the spec has passing evidence or an explicitly identified external prerequisite; do not claim a real-provider or browser check that was not performed.
- A maintainer can run the feature locally from the written instructions with their configured TMDB credential.
- Remaining public-release work links to [05](05-public-release-prerequisites.md), rather than presenting the local feature as publicly deployed or production-verified.

## Comments

Created from the settled feature spec. Unstarted; no implementation or runtime checks were performed during planning.
