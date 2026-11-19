# Consolidate the architecture direction and explicit deferrals

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15

## Question

Do the resolved decisions form a coherent architecture direction for the whole app and future shared web/native clients? Trace the critical workflows through client and backend ports/adapters, persistence, providers, jobs, and deployment; expose contradictions or missing consequential decisions as fresh tickets. Classify remaining choices as decide now, reversible defaults, or deferred with triggers, including migration costs. Close only when no unrecorded costly assumption is needed to begin implementation; link decision records rather than restating their detail.

## Comments

### Consolidation review — 2026-11-09 (Pacific/Honolulu), awaiting human decision

All other seventeen tickets are resolved. The checkout still contains proposal/domain/planning documents and Python metadata with no application dependencies or implementation. This review assesses the recorded architecture direction; it does not establish runtime feasibility, measured quality, cost, or readiness to deploy.

#### Workflow coverage

| Workflow / concern | Trace and governing decisions |
| --- | --- |
| People search, Follow, and Timeline browsing | Platform presentation calls the shared client core/backend adapter; the backend resolves the acting user, performs catalog access through ports, saves user-owned activity, and serves deduplicated bounded Timeline windows with direct ruler access. See [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md#answer), [Define domain identity and user-data ownership](06-domain-identity-and-ownership.md#answer), [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md#answer), and [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md#answer). |
| Note/photo import, review, and save | Platform input goes through request-scoped backend extraction and provider matching; the initiating client holds unconfirmed review; confirmed saves use established Movie identities and independent statuses. Temporary inputs and durable user activity have distinct lifecycles. See [Define import review and background-work lifecycles](11-imports-and-background-work.md#answer) and [Define domain identity and user-data ownership](06-domain-identity-and-ownership.md#answer). |
| Storyline filtering | Off-request preparation creates shared movie representations; live queries operate over the acting user's eligible Timeline while preserving presentation, other filters, and ruler access. Coverage, service-failure presentation, and rebuild boundaries have an owner. See [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md#answer). |
| Suggest a movie | The backend supplies authorized user context to its independently configured suggestion adapter; structured results are display-only and logged for observability, without catalog validation or saving. This is deliberately distinct from import review. See [Define recommendation inputs and trusted-result boundaries](14-recommendation-architecture.md#answer). |
| Provider/gateway access and resource refusal | Inward dependency direction, independent task gateways, retry coordination, and admission controls apply across feature paths. Memory-based admission and asynchronous usage persistence provide approximate global enforcement; refused admission is communicated through HTTP. See [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md#answer), [Identify the LLM Gateway and its documented capabilities](18-identify-llm-gateway.md#answer), and [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md#answer). |
| Restart, refresh, deletion, and recovery | Saved user activity, temporary inputs, provider metadata, derived representations, usage accounting, and telemetry have distinct persistence/cleanup responsibilities. See [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md#answer), [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md#answer), [Establish permitted catalog-data use and provider strategy](17-provider-permissions-and-strategy.md#answer), and [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md#answer). |
| Future native and outside-V1 features | The selected client family and platform adapters preserve native delivery; independent identity, capability/provider adapters, and entity-type-aware references preserve later auth/providers/shows. These remain stress tests rather than promised delivery. See [Choose the web and native client platform direction](05-choose-client-platform-direction.md#answer), [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md#answer), and the map's scope. |

#### Cross-decision reconciliation

- Display-only suggestions are the explicit exception to import validation-before-review and default reply-content exclusion. The backend decision already links that exception; it does not authorize unvalidated catalog/user-activity writes or general prompt logging.
- Request-scoped imports/suggestions do not rule out off-request movie embedding preparation. No decision requires an initial durable queue or a universal job/result service.
- Empty results on selected service failures do not override the later HTTP admission-refusal requirement; both search and suggestion resolutions already link the operational refinement.
- The original transport preference, earlier provider-permission uncertainty, and exact proposal note-extraction settings are historical context. Current resolutions govern transport, the user-confirmed provider strategy, and configurable per-task integration policies.
- Shared catalog reuse does not imply a complete provider catalog or required query-result caching. Freshness management remains outside browser presentation.
- Durable usage accounting does not imply exact quotas: memory-based admission, immediate in-flight accounting, asynchronous persistence, and accepted overshoot are explicitly reconciled in the operational decision.

No blocking contradiction or new unrecorded costly architecture choice was identified by this workflow review. An independent read-only local audit of the backend/workflow decisions reached the same assessment. Human agreement is still required before this ticket or the map can close.

#### Classification and handoff

The owning tickets retain the detailed choices, reversal costs, and triggers; this is an index for the handoff.

| Classification | Governing context / next boundary |
| --- | --- |
| Fixed now because reversal would affect ownership, core dependencies, or substantial UI | App-owned identities and user activity in [Define domain identity and user-data ownership](06-domain-identity-and-ownership.md#answer); client family in [Choose the web and native client platform direction](05-choose-client-platform-direction.md#answer); dependency/state/authority boundaries in [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md#answer) and [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md#answer). |
| Replaceable starting directions, with migration/rebuild costs acknowledged | Relational/Neon persistence, TMDB adapter, task-specific gateways, and one backend deployment under [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md#answer), [Establish permitted catalog-data use and provider strategy](17-provider-permissions-and-strategy.md#answer), [Identify the LLM Gateway and its documented capabilities](18-identify-llm-gateway.md#answer), and [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md#answer). Replacing storage/providers may require migrations; changing embedding space may require regeneration. |
| Separate investigation/specification before relevant implementation | Database/schema and Timeline query design in [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md#answer); search interaction and API fields/tools in [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md#answer); semantic model/store/matching evaluation in [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md#answer). These are explicit follow-up efforts beyond this map. |
| Evidence/configuration before integration or public release | Model/output/image/runtime/data-handling checks in [Identify the LLM Gateway and its documented capabilities](18-identify-llm-gateway.md#answer); extraction/suggestion quality and retry configuration in their feature decisions; actual hosting cost, HTTP/2, limiter accounting/tolerance, deadlines, telemetry retention, cleanup, and restore verification in [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md#answer). |
| Revisit only on a product/operating trigger | Personal-auth implementation and cross-release compatibility before independent clients/accounts; native delivery when scheduled; richer suggestion/validation/save behavior when needed; stronger job recovery, quota precision, or service separation only for the triggers in their owning resolutions. Offline, notifications, availability, richer discovery, and shows remain outside the current delivery commitment. |

Recommendation: accept this as a coherent architecture direction, resolve the consolidation ticket, and close the map after human confirmation. Clear the map's two generic remaining-fog entries as reviewed: no additional in-scope architecture decision was discovered, and already named post-map investigations remain explicit deferrals rather than open architecture fog. Do not begin implementation or create an implementation backlog as part of this resolution.

### Human discussion — 2026-11-09 (Pacific/Honolulu), acceptance

The user accepted the reviewed architecture direction, the classification of fixed boundaries and replaceable starting choices, and the recorded follow-up work. They confirmed resolving this consolidation ticket and closing the map. No additional architecture decision or implementation work was requested.

## Answer

Resolved through human acceptance on 2026-11-09 (Pacific/Honolulu).

### Choice and rationale

Accept the combined decisions as a coherent architecture direction for the proposed app and future shared web/native product. The [workflow review](#workflow-coverage) covers the main user paths, state/ownership boundaries, external integrations, and operational responsibilities. The [reconciliation](#cross-decision-reconciliation) accounts for the deliberate later refinements; no blocking contradiction or unrecorded costly architecture assumption remains at this map's level of detail.

Close the architecture map. All eighteen child tickets are resolved, and the generic remaining fog has been reviewed without discovering another in-scope decision. The map's destination is satisfied by the accepted direction and explicit deferrals. Implementation, native delivery, detailed specifications, and runtime verification remain the separately recorded follow-up work.

### What is fixed now

Carry the accepted resolutions and shared glossary into subsequent investigations, specifications, and implementation. The source tickets remain authoritative for their choices, exceptions, rationale, and reversal costs; the map remains their index. This consolidation does not select additional technologies or alter those decisions.

### Deferrals and handoff

Use the [classification and handoff](#classification-and-handoff) to find the owning context and triggers. In particular:

- Before persistence implementation, conduct the separate database/schema and Timeline-query investigation recorded in [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md#answer).
- Before the relevant client/API/search workflows, specify detailed interactions/contracts and choose concrete libraries within [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md#answer) and [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md#answer). Perform the focused semantic-search investigation under [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md#answer).
- Before model integration and public release, complete the feature quality/compatibility and gateway data-handling checks under [Identify the LLM Gateway and its documented capabilities](18-identify-llm-gateway.md#answer), along with the configuration, measured cost/performance, HTTP/2, cleanup, and restore checks under [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md#answer).
- Revisit native delivery, personal authentication, independent-client compatibility, stronger recovery/quotas, and outside-V1 features only at their recorded product/operating triggers.

No new decision ticket or implementation backlog is created. Follow-up efforts begin separately from this completed architecture map.

### Cost of reversal

Changing ownership, core dependency direction, or the client rendering family after implementation would carry the costs described in their source decisions. Replacing adapters, storage, models, or deployment mechanisms remains possible within those boundaries, with migrations or regeneration where recorded. Closing this map does not remove the explicit evidence requirements or revisit triggers; a materially changed destination calls for a new effort.
