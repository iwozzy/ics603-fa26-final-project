# Define recommendation inputs and trusted-result boundaries

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 07, 12

## Question

How should the proposed three movie suggestions use follows, seen movies, watch list, and any additional input? Decide how candidates are grounded in real movie identities, permissions and user-data boundaries, deterministic filtering versus LLM responsibility, and failure/fallback behavior. Locate recommendation responsibilities within the backend ports and adapters, and identify any evaluation or research required before choosing a model.

## Context

Apply [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md#answer). Define recommendation coordination, domain decisions, and external generation/retrieval capabilities under the resolved owners. Refine feature-specific inputs, validation, failures, and independently configured gateway use here.

Apply [Establish permitted catalog-data use and provider strategy](17-provider-permissions-and-strategy.md#answer), updated by the user's confirmation on 2026-11-09. TMDB allows the app's use case; training AI with its data is prohibited. Relevant catalog fields, including titles, names, and descriptions, may be considered for the planned runtime suggestion workflow. The previous blanket exclusion of provider content from LLM prompts is superseded; no second title source, replacement-description source, or external clarification is required for the confirmed use case.

This ticket still owns exact model inputs, grounding in real Movie identities, user-data authorization, deterministic filtering, quality/fallback behavior, and cost. Keep provenance explicit and ensure the gateway/model handling respects the no-training restriction. No model or final input set is selected by the provider confirmation.

## Comments

### Human discussion — 2026-11-09 (Pacific/Honolulu), first round

- Accepted suggestions outside the user's Timeline. Timeline membership does not limit the recommendation corpus.
- Accepted using the acting user's Follows and Watchlist, including independent seen and watch statuses, as personalization context. Viewing history does not imply a positive rating. Exact fields and input-size limits follow feature specification.
- Added a firm eligibility rule: the app does not recommend a movie the user has already marked seen. Enforce this in application/domain rules rather than relying only on model instructions.
- Accepted that Suggest a movie works without additional user text. Optional mood, genre, or other preferences remain a reversible choice for later feature specification. The target remains the proposal's three suggestions.
- Candidate generation/validation, other eligibility rules, confirmed saves, lifecycle/fallback behavior, and model/evaluation deferrals remain to discuss. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), second round

- Rejected provider/catalog validation for the initial feature. Present the LLM's suggestions directly without resolving Movie identities. They are unvalidated suggestions, not provider-validated Candidate movies or trusted catalog records. This narrows the backend decision's general validation-before-review guidance for this display-only feature; import validation remains unchanged.
- Accepted unseen Watchlist movies as eligible, explicitly without checking/filtering suggestions against the Watchlist merely because they are already saved.
- Accepted that displaying suggestions does not change Watchlist entries or statuses. For the initial feature there is no save action, because saving would first require validation. The earlier assumed candidate-validation workflow is not adopted.
- The no-seen-movies intent remains, but deterministic identity-based exclusion cannot be promised without identity resolution. Whether the initial feature treats this as a best-effort model instruction remains to confirm. The first-round instruction to enforce this by established Movie identity is superseded as an implementation assumption by the user's no-validation direction.
- Lifecycle, partial/failure behavior, and model/input/evaluation deferrals remain to discuss. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), final round

- Accepted avoiding seen movies as a best-effort model instruction informed by the user's viewing history, without guaranteed identity-based exclusion in the unvalidated initial feature.
- Accepted request/response execution and results held in the current client view, without saved suggestion history or background jobs. Added an explicit requirement to log suggestion results for observability; this is telemetry, not application suggestion history. It is a feature-specific exception to the earlier default exclusion of model replies from telemetry.
- Accepted three suggestions as a target, with fewer or none acceptable after configured attempts and failures logged internally. Optional high-level messaging is allowed; technical error details need not be shown. Added that the required output format will be supplied through Pydantic AI. Output-shape validation is distinct from the catalog validation the user declined.
- Accepted deferring the model, prompt, exact input/output fields, context-size limits, and retry settings until suggestion implementation, with a small quality and compatibility check before release.
- All questions in this decision are now settled or explicitly deferred.

## Answer

Resolved through human discussion on 2026-11-09 (Pacific/Honolulu).

### Choices and rationale

**Initial suggestions are display-only LLM output.** Suggest a movie may propose movies outside the user's Timeline. Present the model's suggestions without catalog/provider lookup or identity resolution. They remain Movie suggestions, distinct from provider-validated Candidate movies and established catalog Movie identities. Do not create catalog records or infer trusted identities from the response. There is no initial save action; validation must be introduced before suggestions can be saved. Displaying a suggestion changes no Watchlist entries, statuses, or Timeline membership. This deliberately keeps the first feature small; import provider validation and confirmation remain unchanged.

**Use existing interests and activity as context.** The backend obtains the acting user's Follows and Watchlist, including independent seen and watch statuses, under the established ownership boundary. Do not use another user's private activity or treat viewing history as a positive rating. Additional text is not required; optional mood/genre/preferences can follow feature specification. Exact fields and context-size limits remain deferred. Unseen movies already saved in the Watchlist remain eligible, with no output-membership check needed to exclude already-saved movies.

**Avoid seen movies through model instructions initially.** Supply viewing history and instruct the model not to recommend already-seen movies. This is best effort, not a guaranteed identity-based exclusion. The user's later no-validation direction and explicit acceptance of this limitation supersede the first-round assumption that backend identity rules would strictly enforce it. Revisit identity resolution and deterministic filtering if repeated seen-movie suggestions become a practical problem or saving is introduced.

**Structured output, separate from catalog validation.** Supply the required output format through Pydantic AI inside the suggestion adapter and retain Pydantic boundary validation. Target three suggestions, accepting fewer or none after configured attempts. A response matching its required structure does not establish that a suggested movie exists or corresponds to a catalog identity. Exact fields, prompt, and model remain deferred; verify output-format compatibility with the selected gateway/model before integration rather than assuming protocol compatibility provides it.

**Ordinary request/response lifecycle.** Run generation asynchronously within the originating HTTPS request through an independently configurable suggestion capability adapter. The client holds the displayed results; there is no initial application suggestion-history store, background job, or recovery/status service. Application operations coordinate authorized context retrieval and generation; domain rules retain activity ownership, while adapters isolate gateway, Pydantic AI, and transport details. No catalog retrieval or semantic-retrieval step is required for this feature. Retry policies remain configurable and bounded under the existing application-wide coordination of attempts and deadlines; exact counts/settings follow integration. Global API limits and shared usage budgets remain operational responsibilities.

**Accept partial/empty results and log outcomes.** Fewer than three suggestions or none are acceptable after configured attempts; no extra generation loop is required solely to fill three slots. Log failures internally and allow optional high-level messaging without technical error details. Log suggestion results for observability as explicitly requested. This is a scoped exception to the backend's default exclusion of model replies from telemetry, not authorization to capture full prompts, private input histories, credentials, or all other task outputs. Results in telemetry do not become saved suggestions or trusted catalog data. Keep timings, outcomes, usage, and correlation information under the existing instrumentation boundary; retention/access/redaction configuration belongs to deployment planning.

The subsequent [operational-controls decision](15-deployment-observability-and-resource-limits.md#answer) governs admission refusals and requires an HTTP status for those cases, with client presentation deferred.

### What must be fixed now

Keep the first feature display-only, unvalidated against the catalog, and unable to save suggestions. Use the acting user's existing interests/activity, allow proposals outside the Timeline and already-saved unseen movies, and treat avoiding seen movies as best effort. Require Pydantic AI output formatting, target three with partial/empty results acceptable, use request/response execution, and log results plus failures for observability. Keep suggestion output separate from catalog records, validated import candidates, and saved user activity.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary / starting direction | Revisit trigger |
| --- | --- | --- |
| Model/gateway, prompt, exact fields, and input/context-size limits | Independently configurable suggestion adapter; authorized Follows/Watchlist context; required output format through Pydantic AI | Suggestion implementation, with a small quality and compatibility check before release |
| Retry counts, delays, deadlines, and exact failure presentation | Existing configurable, coordinated retry policies; three is a target; fewer/none acceptable; internal failure logging | Before integration; measured latency, cost, or failure frequency justifies adjustment |
| Catalog validation, identity resolution, strict seen-movie exclusion, and save actions | Initial direct display without lookup or saving; seen avoidance through model instructions | Before enabling saving, or if inaccurate/repeated seen-movie suggestions justify stronger guarantees |
| Optional mood/genre input and richer recommendation strategies | No additional text required; no required retrieval/ranking system | Feature specification or observed user/quality needs |
| Saved suggestion history, background execution, and stronger recovery | Current client view and ordinary request/response; observability results are separate telemetry | Concrete history/resume needs or measured request-deadline problems |
| Result-log retention/access/redaction and shared generation budgets/rate limits | Explicit result logging; preserve the existing instrumentation, user-ownership, and provider-data boundaries | [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md), then configuration before release |

No new prerequisite research ticket is required for this architecture direction. Detailed suggestion implementation and its small quality/compatibility check follow the map.

### Cost of reversal

Models, prompts, output fields, and retry settings remain replaceable behind the suggestion adapter. Adding catalog validation later requires a matching/identity workflow, and saving additionally needs an explicit user action using validated identities. Keeping unvalidated output out of catalog/user-activity records avoids a data cleanup migration. Strict seen-movie exclusion would add identity-based checking that the initial feature intentionally defers. Result logs need their own operational retention policy; they do not establish a suggestion-history product feature.
