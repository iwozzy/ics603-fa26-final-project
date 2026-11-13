# Define and verify public-release operations

Type: task
Status: open
Parent: [Search people](../spec.md)

## Outcome

Resolve and verify the operational prerequisites before exposing this feature publicly. This is a separate release gate, not a blocker for completing the locally runnable feature. Planning can proceed independently; final verification uses the integrated application.

## Scope

- Select hosting, Docker/web serving, credential delivery and release configuration. Verify the client-facing HTTPS/HTTP/2 path rather than inferring it from the application framework.
- Implement and verify incoming/outgoing global rate and cumulative usage admission across serving processes. Choose keys/units/values, immediate in-memory accounting, durable totals, startup/synchronization behavior, accepted overshoot and operator controls under ADR-0001. Exhaustion does not implicitly replenish; denied search admission uses the feature's HTTP `500`/`no-store` contract.
- Bound expensive concurrency and align application/provider/client/proxy deadlines. Verify prompt refusal, no automatic search retries, and unchanged successful-response cache semantics.
- Configure maintainer-only finite-retention telemetry, including request/URL capture settings, so searched names, returned person content and credentials are absent. Keep internal timing/outcome/usage visibility despite silent UI failures.
- Supply the required TMDB attribution and applicable provider-data handling. Check operating cost/latency, configured provider access, and the actual portrait transform before release.
- Select recovery/backup handling and perform the applicable restore check for durable operational accounting. No search/catalog data storage is introduced by this ticket.

## Acceptance

Record configuration and evidence for deployment transport, global admission and restart behavior, bounded failure/refusal, telemetry exclusions/access/retention, attribution, recovery and operating feasibility. Public exposure waits for these checks; local feature acceptance alone is insufficient.

## Comments

Created from Q24/Q26 and ADR-0001's explicit release obligations. Unstarted. This ticket does not expand scope to Follow, personal accounts, native delivery, or catalog persistence.
