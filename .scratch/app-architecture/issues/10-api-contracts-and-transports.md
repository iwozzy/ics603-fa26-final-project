# Choose API contracts and where persistent connections belong

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 02, 07, 08, 09

## Question

How should HTTPS request/response contracts expose transport-independent application operations to all clients? The user now requires HTTPS with HTTP/2, debounced/abortable fetch, and exclusion of WebSockets for the current architecture. Use transport research, platform requirements, session boundaries, and ports/adapters. Decide validation ownership and contract generation/versioning, structured errors, authorization, duplicate/retried commands, pagination, and reconnect/resume where applicable. Defer progress polling versus SSE until the import lifecycle establishes requirements.

## Context

Apply [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md#answer). Client backend-access adapters own runtime response validation and transport translation; define wire-contract representation/generation here. Preserve user/workflow-scoped state. The later user direction recorded below selects debounced, abortable fetch for search requests; remaining search interaction, obsolete-result presentation, and caching behavior stay deferred to feature specification.

Apply [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md#answer). Expose transport-independent application operations and map their application-owned failures into client contracts here. Concrete API framework selection remains deferred until implementation; preserve the resolved validation, dependency, and retry-coordination boundaries.

Apply [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md#answer). Carry a backend-verified acting user into application operations and enforce ownership consistently across transports. Initial demo access requires no login session. Future personal-session expiry or revocation must not reconnect/retry an operation as the Demo user or another account. Choose browser/native credential exchange and any ongoing connection authorization checks without leaking transport/session representations into domain ownership. Keep private temporary-work access distinct from the shared Demo user identity.

## Comments

### Human discussion — 2026-11-09 (Pacific/Honolulu), first round

- Accepted HTTPS request/response for ordinary searches, browsing, saved changes, and uploads. The user explicitly requires HTTP/2 and debounced, abortable fetch and excludes WebSockets entirely for now. Apply debouncing to search requests without assuming all writes/uploads should be delayed. Debounce timing and remaining search UX stay with feature specification. This supersedes the original preference for WebSockets and narrows the earlier search-behavior deferral.
- Accepted API-specific Pydantic schemas as the wire-contract source, separate from domain objects and provider payloads, with TypeScript types and runtime validators derived where practical. Exact generation tools remain deferred until implementation.
- Accepted explicit acceptance/commit/repetition semantics: prefer desired-state writes such as setting seen status over toggles, and define duplicate handling for nonrepeatable or billable operations before automatic retries. Lost acknowledgements can leave a committed outcome uncertain.
- Accepted deferring progress delivery until the import lifecycle specifies continuation/recovery and acceptable update delay. The remaining options are polling and SSE; WebSockets are excluded. Work that outlives its connection needs authorized status/result retrieval independently of notifications.
- Browser request abort does not itself establish backend-work cancellation or undo committed changes. Explicit backend cancellation and retry/recovery semantics remain lifecycle responsibilities.
- Structured client errors, compatibility/versioning, and collection-response boundaries remain to discuss. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), second round

- Accepted consistent HTTP statuses and machine-readable error codes, safe messages, and useful validation details. Clients use stable codes rather than parsing message text; provider exceptions/internal details stay behind adapters. Exact response fields follow endpoint specification.
- Qualified the proposed compatibility policy: breaking API changes are acceptable for now because clients and backend are developed simultaneously. Compatibility/versioning becomes a requirement later, when independently released clients or deployments need it; no current multi-version support or compatibility window is selected.
- Accepted bounded responses and explicit pagination metadata for potentially large Timeline, Watchlist, and search collections. Ordering/continuation are specified per collection; exact page sizes and cursor-versus-page mechanics remain for feature/database design.
- Added a product requirement: the user can jump directly to any part of the Timeline using a Timeline ruler, also visible in the proposal's existing Timeline wireframe. Sequential next-page access alone is insufficient. The remaining architecture question is the access boundary supporting that direct jump while retaining bounded results; detailed date/order/filter behavior and ruler UI need not be settled here.

### Human discussion — 2026-11-09 (Pacific/Honolulu), final round

- Accepted fetching a bounded Timeline window at the time chosen through the Timeline ruler, with navigation to earlier and later results. Apply active filters and support direct access without traversing intervening pages. Exact date semantics, window sizes, empty-period behavior, and indexing follow Timeline feature/database design.
- All questions in this decision are now settled or explicitly deferred.

## Answer

Resolved through human discussion on 2026-11-09 (Pacific/Honolulu).

### Choices and rationale

**HTTPS request/response with HTTP/2; WebSockets excluded for now.** Use HTTPS for ordinary searches, browsing, saved changes, and uploads, with HTTP/2 required on the client-facing service. The user explicitly dropped WebSocket options, superseding the original preference. Transport adapters expose the existing application operations without binding domain/application logic to HTTP objects. Deployment must verify negotiated HTTP/2 through the actual client-facing path and document proxy/backend hops; choosing fetch or an async framework does not verify that requirement.

**Debounced, abortable fetch for search requests.** This user direction narrows the earlier frontend search deferral. Keep timing, UI triggers, obsolete-result presentation, and query caching with search-feature specification, potentially using a prototype. Do not assume every write/upload should be debounced. Browser abort is not a guarantee of backend-work cancellation or rollback of a committed write; explicit backend cancellation belongs to the workflow lifecycle.

**One API wire-contract source.** API-specific Pydantic schemas define the wire contract, separately from domain objects and provider payloads. Derive TypeScript types and runtime validators where practical, retaining client boundary validation. Exact schema publication/generation tools and endpoint fields follow implementation. The backend remains authoritative for validation, ownership, and saved-data rules, while adapters translate transport and provider representations.

**Explicit write outcomes and repetition semantics.** Distinguish accepted work from completed/committed changes. Prefer desired-state operations, such as setting seen status, over toggles. A lost acknowledgement can leave the outcome uncertain even when a write committed. Define duplicate handling for nonrepeatable or billable operations before enabling automatic retries, coordinated with the existing application retry policy; a connection or request ID alone does not establish exactly-once execution. Exact keys, retention windows, acceptance durability, and recovery behavior belong to lifecycle/feature design.

**Structured failures.** Use consistent HTTP statuses and machine-readable codes with safe messages and useful validation details. Clients act on codes rather than parsing prose. Translate application-owned failures at the HTTP boundary and keep provider exceptions/internal details behind adapters. Exact response fields and code catalog remain part of endpoint specification.

**Bounded collections with direct Timeline access.** Potentially large Timeline, Watchlist, and search collections have bounded responses and explicit pagination metadata, with ordering/continuation specified per collection. The Timeline also supports a bounded window at a chosen time, applying active filters, with navigation to earlier/later results. The Timeline ruler must jump directly without walking intervening pages. Cursor/page mechanics and physical database design remain deferred; neither a sequential-only API nor requiring the full Timeline to be downloaded satisfies this access boundary.

**Progress notifications are separate from work recovery.** The later [Define import review and background-work lifecycles](11-imports-and-background-work.md#answer) resolution selects initial request-scoped processing and an indeterminate indicator, without polling, SSE, a durable worker, or a pending-review retrieval endpoint. If future work deliberately continues beyond its originating request, define authorized status/result retrieval and recovery independently of notifications before selecting polling versus SSE. WebSockets remain excluded; a channel alone does not establish durability or replay semantics.

**Breaking contracts are acceptable during coordinated development.** Clients and backend are currently developed together, so the user accepts breaking API changes without a current multi-version compatibility obligation. Revisit additive evolution, versioning/migration, and a supported-client window before independently released clients or deployments must keep working across backend changes, including a native release.

**Identity and authorization retain their resolved boundary.** The backend resolves the acting user and enforces ownership; client-supplied owner IDs are not authorization. Initial Demo access requires no login session. Future personal-session failure must not retry work as Demo or another account. Private temporary-work access remains distinct from shared confirmed Demo activity. Exact credential exchange/cookie/header settings remain implementation decisions under [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md#answer), before personal authentication is exposed.

### What must be fixed now

Carry HTTPS/HTTP/2, the current exclusion of WebSockets, debounced/abortable search fetch, API-specific shared schemas, structured failure semantics, explicit write/retry outcomes, bounded lists, direct filtered Timeline windows, and the established ownership boundaries into implementation planning. Apply the resolved initial import lifecycle and preserve future progress/recovery and compatibility revisit triggers instead of assuming connection lifetime, request abort, or generated types provide those guarantees.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary / starting direction | Revisit trigger / owner |
| --- | --- | --- |
| API framework, endpoint catalog, exact fields/error codes, schema publication/generation tools | HTTPS operations with API-specific Pydantic schemas and derived TypeScript contracts where practical | Endpoint specification and before API/client adapter implementation |
| Proxy/server topology and protocol configuration | Client-facing HTTPS with HTTP/2; document internal hops; no WebSockets | [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md), with negotiation verified before deployment |
| Future progress polling versus SSE and server-held status/results; exact retry/save replay mechanics | Apply the [initial import lifecycle](11-imports-and-background-work.md#answer): request-scoped processing and client-held review, coordinated retries, no progress channel; design authorized state retrieval for future deliberate continuation | Import implementation for exact retry/replay details; measured need for richer progress or stronger continuation/recovery before background execution |
| Search timing/triggers, obsolete-result presentation, and query caching | Debounced/abortable fetch; preserve user/workflow state ownership | Search-feature specification and experience/latency evaluation, potentially a prototype |
| Timeline date semantics, filtered window shape, ties/empty periods, page sizes, cursors/pages, and indexes | Direct bounded access at the ruler's chosen time plus earlier/later navigation; other large lists also bounded | Timeline feature specification and separate database/schema investigation before queries are implemented |
| Compatibility guarantees, versioning strategy, and supported-client window | Breaking changes allowed while clients/backend develop together | Before independently released clients/deployments need cross-version compatibility |
| Credential exchange, concrete browser/native session settings, and temporary-work access proof | Resolved trusted user/ownership boundary; no forced Demo login | Personal-authentication implementation and import-lifecycle decisions before those features are exposed |

### Cost of reversal and evidence

Transport adapters and API-specific models keep framework/tool changes manageable. Missing write-outcome/duplicate semantics or coupling recovery to a live connection would make failures costly to repair after real use. A sequential-only Timeline contract would conflict with the ruler requirement. Compatibility becomes costly once clients release independently, so revisit it before that transition. Concrete pagination/indexing, schema tools, and detailed endpoints remain replaceable within the agreed boundaries.

The [transport research](02-research-client-transports.md#answer) informs this decision. Primary specifications support connection reuse/multiplexing ([HTTP/1.1 persistence](https://www.rfc-editor.org/rfc/rfc9112.html#section-9.3), [HTTP/2 overview](https://www.rfc-editor.org/rfc/rfc9113.html#section-2)), retry ambiguity ([idempotent methods](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)), and acceptance distinct from completion ([202 Accepted](https://www.rfc-editor.org/rfc/rfc9110.html#section-15.3.3)). These are protocol facts, not project benchmarks or proof of deployment behavior. No additional prerequisite ticket is needed; remaining details have existing owners or explicit post-map implementation triggers.
