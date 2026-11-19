# Define backend ports, adapters, and deployment boundaries

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 06, 18

## Question

How should backend domain and application responsibilities be separated from API transport, persistence, movie-data providers, LLM Gateway access, semantic retrieval, and observability? Apply the user's ports-and-adapters direction, Pydantic validation at appropriate boundaries, async operation, and stated integration preferences. Decide the necessary module and process boundaries and dependency direction; assess whether any preference should be revised with an explicit rationale. Identify how provider-specific models and failures stay behind adapters without creating abstractions for hypothetical services.

## Context

Carry forward the agreed boundaries in [Define domain identity and user-data ownership](06-domain-identity-and-ownership.md#answer). The user explicitly emphasized separation of concerns and ports and adapters throughout provider validation, candidate matching, and catalog reconciliation. Establish application-owned contracts so provider-specific identities, payloads, and ranking inputs do not dictate domain or client models. This ticket fixes responsibilities and dependency direction; exact port signatures and package layout follow feature specifications and adapter implementation.

Apply [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md#answer): trusted acting-user resolution, credential verification, session handling, and application authorization have distinct responsibilities. The initial resolver selects the ordinary Demo user without requiring a login session; future username/password authentication resolves the same kind of app-owned identity. Enforce ownership independently of client-supplied user IDs or the chosen transport, with no implicit owner change after authentication failure.

Apply [Identify the LLM Gateway and its documented capabilities](18-identify-llm-gateway.md#answer). The private course gateway now has documented OpenAI-compatible interfaces and explicit feature/compatibility unknowns. Keep model/endpoint configuration and gateway errors behind the adapter; do not assume image inputs, structured outputs, provider-side durable work, or post-course availability from protocol compatibility alone. Runtime checks belong before integration; the gateway-identification prerequisite is resolved.

Apply the user's [gateway-independence requirement](18-identify-llm-gateway.md#consequences-and-handoff): application-owned ports must allow different tasks to use different gateway adapters at the same time and allow a gateway to be replaced without changing domain/application logic. Decide concrete task/capability contracts and adapter composition here; avoid assuming one application-wide gateway or requiring every adapter to implement every task. Pydantic AI remains an integration preference within the adapter boundary.

## Comments

### Human discussion — 2026-11-09 (Pacific/Honolulu), first round

- Accepted one modular Python backend, with API entry points and any later workers sharing application code. Maintain internal module boundaries; decide worker processes in the background-work ticket and revisit separate services when scaling or failure isolation requires them.
- Accepted domain objects and rules as ordinary Python independent of Pydantic, database libraries, API frameworks, and provider SDKs. Use Pydantic to validate boundary inputs/outputs, including API requests, provider payloads, and model results; adapters translate external representations.
- Accepted application-layer coordination of workflow sequencing and transaction boundaries through ports. The user explicitly clarified that application coordination must not make domain decisions: when a domain decision is needed, domain objects/rules/services own it. API handlers translate requests and adapters perform their specific I/O. Avoid holding database transactions open during provider/model calls.
- Accepted asynchronous external-I/O ports for database, provider, and gateway operations, while ordinary domain rules remain synchronous. Async execution does not imply background scheduling or durability; those remain separate decisions.
- Port contracts/composition, failure handling, instrumentation, and remaining implementation deferrals still need discussion. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), final round

- Accepted capability-oriented ports driven by actual workflows, with application-owned contracts and adapters selected in backend startup/configuration code. Extraction, suggestions, and embeddings can be configured independently. Exact method signatures follow feature specifications.
- Accepted adapters translating external failures into application-owned failure types, distinguishing unavailable services, invalid results, exhausted budgets, and other actionable failures. The application coordinates retry decisions, with one explicit policy per operation that accounts for SDK/adapter/workflow attempts. Transport adapters later map failures to client responses.
- Accepted instrumentation around application operations and adapter calls, keeping Logfire dependencies outside domain and application logic. Record timings, outcomes, usage, and correlation identifiers; exclude raw notes/photos, prompts/replies, and credentials from telemetry by default.
- Accepted deferring the API framework, database libraries, exact package layout, and worker technology. Fix responsibilities and dependency direction now; choose concrete libraries/layout before their adapters are implemented, and worker technology after the background-work lifecycle is defined.
- All questions in this decision are now settled or explicitly deferred.

## Answer

Resolved through human discussion on 2026-11-09 (Pacific/Honolulu).

### Choices and rationale

**One modular Python backend.** API entry points and any later workers share the same domain and application code. Keep internal responsibilities separate within that codebase. This does not select a worker process or durable-work mechanism. Revisit separate services when scaling or failure isolation justifies the additional operational boundary.

**Domain decisions belong to the domain; the application coordinates.** Domain objects, rules, and services make domain decisions using ordinary Python independent of Pydantic, API frameworks, database libraries, and provider SDKs. Application operations sequence work, obtain the facts those rules need through ports, apply domain decisions, and coordinate persistence and transaction boundaries. API handlers translate requests and invoke operations; adapters perform their specific I/O. For example, import coordination connects extraction, provider validation/matching, review, and saving confirmed choices without moving domain identity or Watchlist rules into a handler or provider adapter. Existing authorization and private-temporary-work boundaries remain in force.

**Dependencies point toward application-owned contracts and the domain.** The logical separation below does not prescribe directories or packages:

| Responsibility | Dependency direction |
| --- | --- |
| Domain objects/rules/services | Ordinary Python; no infrastructure or framework dependencies |
| Application operations and ports | Domain and application-owned contracts; no concrete adapter dependencies |
| API and later worker entry adapters | Application operations; translate transport/job representations at entry/exit |
| Persistence, catalog-provider, gateway, identity/session, and retrieval adapters as needed | Implement the relevant ports; translate external representations and isolate SDK/database/protocol dependencies |
| Startup/configuration and instrumentation | Compose concrete adapters and wrap operation/adapter calls; domain/application logic does not import this wiring or Logfire |

Define only ports needed by actual workflows. Use capability contracts rather than assuming a single universal gateway: extraction, suggestions, and embeddings can select different configured adapters concurrently. Pydantic AI remains the preferred gateway integration inside adapters. TMDB, Neon Postgres, and Logfire retain their existing starting roles behind the corresponding boundaries. Swapping a gateway must not require changes to domain/application logic or moving all other tasks to it; feature/model compatibility still needs checking before integration.

**Pydantic validates boundaries.** Validate API inputs/outputs, external provider payloads, model results, and other relevant external boundaries with Pydantic. Adapters translate them into the application/domain representations required by their contracts. A valid payload is not proof that a domain decision is valid or that a model-generated movie is trusted; apply the feature's established validation and confirmation boundary. The subsequent [recommendation decision](14-recommendation-architecture.md#answer) defines the initial display-only suggestion exception; import validation and confirmation remain required.

**Async I/O, short database transactions.** External-I/O ports use async operations for database, provider, and gateway access; ordinary domain rules remain synchronous. Application coordination owns transaction boundaries through persistence contracts. Avoid holding database transactions open while awaiting provider/model calls. Async I/O does not establish background execution, cancellation guarantees, restart recovery, or durability; those remain lifecycle decisions.

**Failures cross ports in application-owned terms.** Adapters translate external errors into actionable failure types such as unavailable service, invalid external result, or exhausted budget. Application operations coordinate retry decisions. Each operation has one explicit retry policy accounting for SDK, adapter, and workflow attempts, so attempts do not multiply unnoticed. Exact code catalogs, retry bounds, and HTTP response details follow the API/lifecycle decisions and endpoint specification; preserve documented gateway-specific distinctions within the adapter's translation. The later [API decision](10-api-contracts-and-transports.md#answer) excludes WebSockets for now.

**Instrument around operations and adapters.** Keep Logfire dependencies in instrumentation code wrapping application operations and external calls. Capture timings, outcomes, usage, and correlation identifiers while excluding raw notes/photos, prompts/replies, and credentials by default. Exact instrumentation and redaction configuration belong to operational planning; this decision does not authorize automatic content capture. The subsequent [recommendation decision](14-recommendation-architecture.md#answer) explicitly authorizes logging suggestion results as a feature-specific exception to that default.

### What must be fixed now

Preserve domain ownership of domain decisions, application coordination, inward dependency direction, capability-oriented ports, explicit adapter composition, independently selectable gateways, async external I/O, application-owned failures, coordinated retries, and instrumentation outside core logic. Carry the established user-ownership, catalog identity/refresh, provider-data lifecycle, and import-trust boundaries through these operations rather than letting adapters redefine them.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary / starting direction | Revisit trigger / owner |
| --- | --- | --- |
| Exact package layout, port signatures, and concrete contract representations | The logical dependencies above; ports reflect actual workflow needs | Feature specifications and before implementing the relevant adapters |
| API framework and HTTPS exposure, wire contracts, client error shapes | Transport entry adapters call the same application operations; apply the later API decision's exclusion of WebSockets | [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md#answer), then framework selection before API implementation |
| Database libraries, schema, transaction implementation, and migrations | Persistence ports preserve durable user writes and the resolved catalog boundaries | Separate database/schema investigation before persistence implementation; [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md#answer) |
| Future job/process split, queue/worker technology, and stronger restart recovery; exact cancellation/retry configuration | Apply [Define import review and background-work lifecycles](11-imports-and-background-work.md#answer): initial request-scoped processing without a separate worker/queue; future workers share application code | Before import integration for exact policy configuration; measured request-deadline or stronger-recovery need before introducing background infrastructure |
| Extraction, suggestion, and embedding models; detailed gateway settings and feature checks | Independently configured capability adapters; no single-gateway assumption | Respective feature specifications and compatibility/quality checks before integration |
| Semantic retrieval/indexing and recommendation-specific contracts | Separate retrieval, generation, validation, and domain responsibilities | [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md) and [Define recommendation inputs and trusted-result boundaries](14-recommendation-architecture.md) |
| Retry limits, deadlines, resource budgets, telemetry configuration, and Docker/hosting topology | Application-coordinated policies, adapter-specific error translation, content-excluding instrumentation | [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md) and feature implementation |
| Separate backend services | Modular backend sharing domain/application code | Demonstrated scaling or failure-isolation need |

### Cost of reversal

Changing libraries, adapter implementations, wiring, or package layout remains manageable behind the agreed boundaries, though stored data or changed embedding representations may require migrations/reindexing. Spreading domain rules into orchestration/adapters, importing provider SDK models into contracts, making clients coordinate backend workflows, or binding every task to one gateway would make replacement substantially more expensive. Those boundaries are fixed now. No new prerequisite investigation is needed to resolve this ticket; the remaining work belongs to existing tickets or the explicit implementation deferrals above.
