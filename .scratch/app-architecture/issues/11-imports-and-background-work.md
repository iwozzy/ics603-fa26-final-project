# Define import review and background-work lifecycles

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 06, 07, 09

## Question

What lifecycle should note/photo extraction, movie matching, and human review follow across request deadlines, failures, retries, reloads, server restarts, and future mobile suspension? Decide which work is synchronous versus durable/background, job/result identity, cancellation or idempotency needs, upload/result retention, and how reviewed results become user-owned movie tracking. Distinguish async I/O from durable execution and prevent model output from becoming trusted saved data without the required review. Decide architecture boundaries, not extraction prompts or models.

## Context

Apply [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md#answer): HTTPS/HTTP/2 with WebSockets excluded. This lifecycle selects initial request/response processing and progress presentation; polling/SSE and authorized status/result retrieval become relevant if future work deliberately continues beyond its originating request. Specify acceptance/commit, duplicate handling, and cancellation/recovery before automatic retries or durable execution; browser fetch abort alone does not establish those semantics.

Apply [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md#answer). Temporary review state is workflow-scoped and distinct from backend-data caches and screen-only state; media/lifecycle capabilities sit behind platform adapters. This ticket owns import interruption, reload/resume, and temporary-input persistence semantics without selecting detailed search-result ordering or requiring a particular state library.

Apply [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md#answer). API entry points and later workers share application/domain code; application operations coordinate while domain rules make domain decisions. This ticket settles lifecycle and durability needs before choosing worker technology or process boundaries, retaining the agreed transaction and retry-coordination constraints.

Apply [Set the architecture's quality targets and decision priorities](04-architecture-quality-targets.md#answer). Define when an extraction interaction ends, including cancellation, navigation, abandonment, and failures, and how discarded inputs are cleaned up. Reconcile retry/input preservation with temporary raw-input retention. In the public demo, decide how simultaneous visitors' in-progress inputs and review state remain separate even though confirmed movie activity belongs to one demo user.

Apply [Define domain identity and user-data ownership](06-domain-identity-and-ownership.md#answer) for extracted titles, candidate movies, and the Watchlist. Trace title extraction through provider validation and ranking before user review; only provider-validated movies are selectable. Initial matching searches TMDB by movie title only and must accommodate 1–3 ranked candidates per extracted title. Exact ranking and review interaction remain deferred. Confirmed selections update the user's Watchlist and its independent seen status and watch status, without inferring viewing history from DVD ownership or duplicating an existing user–movie relationship. Preserve the distinction between provider validation, user confirmation, and catalog reconciliation behind the relevant ports and adapters.

Carry forward [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md#answer): the initial demo has no login or signed-out state and need not establish an authenticated session. Decide how any server-held temporary inputs, jobs, or review results remain accessible only to the initiating visitor's workflow; the shared Demo user ID alone is not sufficient authorization for private temporary work. Choose the minimum work-access mechanism required by the lifecycle rather than assuming a login session or a separate anonymous personal user. Keep work associated with its original user; define access/cancellation/discard behavior on sign-out, user switching, and deletion without silently applying a late result to another account or recreating deleted personal activity.

## Comments

### Human discussion — 2026-11-09 (Pacific/Honolulu), first round

- Accepted temporary extraction/review without guaranteed recovery after a full reload or server restart. Preserve available input/review through ordinary interruptions while the page remains open where practical; retry if temporary state is lost. Confirmed Watchlist changes remain durable. Stronger recovery can be revisited for a concrete workflow need.
- Accepted ending the interaction on confirmation, explicit cancellation, or leaving the import workflow, triggering cleanup. Temporary connection loss or brief app backgrounding does not immediately end it. Abandoned workflows need bounded expiry; exact timeout remains for implementation.
- Accepted distinguishing retrying extraction from retrying the save of confirmed choices, while explicitly requesting configurable retries for LLM Gateway calls and suggesting Pydantic AI's retry facilities. Do not record a blanket prohibition on automatic model retries: the configuration mechanisms, retry categories, and starting policy still need clarification. After a failed attempt, preserve available input while the interaction remains active.
- Execution/progress behavior, temporary-state placement and cleanup, confirmation retries, and gateway retry configuration remain to settle. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), second round

- Accepted configurable retry policies per task/gateway, with separate transport and output-correction budgets and an overall deadline. Coordinate underlying SDK retries within those bounds; exclude terminal failures such as the current gateway's exhausted-budget 429. Counts/delays are selected before integration. Explicit user retry remains available after configured retries are exhausted.
- Accepted initial asynchronous extraction/matching within an HTTPS request, without a durable queue or separate worker. Revisit background execution when measured processing times exceed practical request deadlines or stronger recovery is required.
- Added the requirement that each API needs a global rate limit. Carry this into [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md), including the interaction between outbound calls/retry attempts and global limits. Exact scope, rates, enforcement, and coordination are not selected here.
- Accepted releasing backend copies of notes/photos as soon as extraction no longer needs them, while the initiating client may retain available input for retry until the interaction ends. Raw inputs stay out of durable application records and backups.
- Accepted ending confirmation only after saving succeeds, retaining review choices if saving fails. Retrying the save uses the same selected Movie IDs and statuses, without repeating extraction or creating duplicate Watchlist entries.
- Temporary-state placement, initial progress presentation, and cancellation/late-result behavior remain to settle. The ticket remains claimed.

### Retry capability check — 2026-11-09 (Pacific/Honolulu)

Current primary [Pydantic AI retry documentation](https://pydantic.dev/docs/ai/core-concepts/retries/) distinguishes configurable HTTP transport retries, provider-SDK retries, and tool/output correction turns. These layers can multiply attempts; model request limits do not account for hidden SDK/transport retries. [Request timeout settings](https://pydantic.dev/docs/ai/api/pydantic-ai/settings/#pydantic_ai.settings.ModelSettings.request_timeout) bound one model request across transport attempts, while an outer deadline must bound a multi-turn workflow. Generic retry defaults must be reconciled with the current gateway's terminal budget-exhaustion 429. The agreed policy is recorded below; exact counts/waits and adapter configuration remain for integration. This is a documentation check, not installed-version or gateway runtime verification; the project has no selected Pydantic AI dependency/version yet.

### Human discussion — 2026-11-09 (Pacific/Honolulu), final round

- Accepted keeping unconfirmed extracted titles, candidate movies, and selections in the initiating client, returned through that visitor's request. No backend pending-review store or retrieval endpoint initially; temporary review stays separate from shared Demo activity and catalog caches.
- Accepted an indeterminate processing indicator while awaiting the extraction/matching response, without polling or SSE initially. Revisit richer progress if workflow testing shows a need for intermediate updates or background execution.
- Accepted best-effort stopping of outstanding work on cancellation, workflow exit, or expiry, discarding late unconfirmed results and cleaning up temporary inputs. Extraction results are never saved without confirmation; cancellation does not undo an already committed save.
- All questions in this decision are now settled or explicitly deferred.

## Answer

Resolved through human discussion on 2026-11-09 (Pacific/Honolulu).

### Choices and rationale

**Temporary import workflow, durable confirmed choices.** Initially, extraction and matching run asynchronously within an HTTPS request, without a durable queue or separate worker. Unconfirmed extraction/review has no guaranteed recovery after a full reload or server restart. Preserve available input/review through ordinary interruptions while the page remains open where practical, and allow retry if temporary state is lost. Confirmed Watchlist changes remain durable. Async execution does not imply restart recovery or continued background work.

**Review belongs to the initiating client.** Return extracted titles and provider-validated candidate movies through that visitor's request; hold unconfirmed titles, candidate selections, and statuses in client workflow state. Do not add a backend pending-review store or retrieval endpoint initially. The shared Demo user owns confirmed activity, not visitors' private temporary work. Client review and raw inputs stay separate from shared backend-data caches. This design does not require a Demo login session or a workflow-access token solely to retrieve stored review, since no such retrieval is offered. A future server-held workflow would need its own authorized access design.

**Extraction, validation, confirmation, and save remain separate.** Apply the established sequence: model extraction yields titles; provider matching validates candidate Movies before review, with 1–3 ranked alternatives where ambiguous; the user chooses Movies and independent statuses. Application code coordinates the sequence while domain rules own domain decisions. Only confirmation saves choices. Save using the same selected Movie IDs and statuses when retrying, without rerunning extraction or creating duplicate Watchlist entries. Keep review choices if saving fails; end a successful confirmation only after the save commits. A lost acknowledgement requires reconciling/retrying that save, not starting model extraction again. Backend validation and trusted user/ownership checks still apply to submitted selections.

**Retry policy is configurable per task/gateway.** Allow bounded retries, with separate transport and output-correction budgets and an overall operation deadline, using the selected adapter's Pydantic AI/client facilities where appropriate. Coordinate SDK, transport, correction, and application layers so attempts do not multiply unnoticed. Exact retry counts, waits, and eligible failures are configured before integration. Exclude terminal failures such as this gateway's exhausted-budget 429; other APIs' rate-limit responses must be classified under their own contracts. After configured retries are exhausted, permit an explicit user retry with available input while the interaction remains active. A retry limit or model usage setting is not a global rate limit.

**Release raw inputs early and bound the interaction.** Remove backend copies of notes/photos as soon as extraction no longer needs them. Keep raw inputs out of durable application records, backups, and telemetry. The client may retain available input for retry until the interaction ends. Successful confirmation, explicit cancellation, or leaving the import workflow ends the interaction and triggers cleanup of temporary state. Temporary connection loss or brief app backgrounding does not immediately end it. Abandoned workflows have bounded expiry; exact timeouts, temporary-file cleanup, and crash cleanup follow implementation/operational planning.

**Cancellation is best effort; late unconfirmed results are discarded.** On cancellation, workflow exit, or expiry, stop outstanding processing where practical, discard late unconfirmed results, and clean up temporary inputs. Never publish those results into another workflow/user or automatically save them. A browser abort does not guarantee upstream cancellation, and cancellation does not undo an already committed save. Preserve the existing sign-out, account-switching, and deleted-account boundaries for in-flight work and writes.

**Initial progress needs no separate channel.** Show an indeterminate processing indicator while waiting for the extraction/matching response. No polling or SSE is needed initially, and WebSockets remain excluded. There is no initial background-job/result service to reconnect to. If later requirements introduce deliberate continuation beyond the request, define authorized status/result lookup and recovery before selecting a progress channel.

**Global rate limits are required.** The user added that each API needs a global rate limit. [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md) owns the exact inbound/outbound scopes, rates, enforcement, and shared coordination. Account for outbound retry attempts within those controls; per-request bounds and the gateway's instructor-set budget do not replace them.

### What must be fixed now

Keep processing request-scoped and unconfirmed review in the initiating client, preserve provider validation and human confirmation before saving, support retrying saves without repeating extraction, bound coordinated gateway retries, and enforce temporary-input cleanup and late-result isolation. Do not require durable workers, pending-review storage, or progress streaming for the initial workflow. Carry global API rate limits into the operational decision.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary / starting direction | Revisit trigger / owner |
| --- | --- | --- |
| Exact retry counts/waits, correction budgets, deadlines, and Pydantic AI/SDK configuration | Configurable per task/gateway, coordinated attempt budgets, terminal-failure exclusions | Before integration, verifying the selected versions and gateway behavior |
| Global API rate-limit scopes, rates, limiter state/coordination, admission behavior, and spend controls | Each API has a global rate limit; outbound attempts include retries | [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md), before public deployment |
| Workflow expiry, temporary-file/proxy cleanup, and client interruption behavior | Early backend raw-input release; no raw inputs in durable records/backups; cleanup on interaction end | Import implementation and operational configuration, with native lifecycle testing before native delivery |
| Candidate ranking, review interaction, save endpoint fields, and precise replay/conflict mechanics | Provider-validated candidates; explicit selected IDs/statuses; no duplicate Watchlist entries or repeated extraction on save retry | Import feature specification and database/API implementation |
| Durable/background processing, workflow/job identity, server-held review/results, and stronger reload/restart recovery | Request/response and client-held temporary review; confirmed choices durable | Measured processing times exceed practical request deadlines or a concrete workflow requires stronger recovery/continuation |
| Polling versus SSE and richer intermediate progress | Initial indeterminate indicator; no separate progress channel | Workflow testing establishes a need for intermediate updates or background execution; design authorized state retrieval/recovery first |

### Cost of reversal

Request-scoped processing and client-held temporary review keep the first implementation small. Adding durable continuation later requires explicit recoverable state, input retention/access, operation identity, retries, and cleanup; keeping those behind application ports preserves that option without building it now. Coupling unconfirmed work to shared Demo activity, retaining raw inputs in durable storage, automatically saving extraction output, or retrying confirmation by rerunning extraction would violate settled boundaries and become expensive to unwind. Exact stores, frameworks, timer values, and retry configuration remain implementation choices. No additional prerequisite ticket is needed for this resolution.
