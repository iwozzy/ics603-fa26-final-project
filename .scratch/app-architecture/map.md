# Architecture for a shared web and native movie-discovery app

Labels: wayfinder:map
Status: resolved

## Destination

Establish a coherent architecture direction for the whole app in [the proposal](../../docs/proposal/proposal.md) and a future shared web/iOS/Android product. Identify the expensive decisions to make before implementation, reversible starting choices, and explicit deferrals with revisit triggers; a complete implementation specification is not required.

## Notes

- This is a planning effort. Produce decisions and supporting investigations; application implementation and native app delivery are outside this map.
- The app is intended to be a small, deployed, multiuser product maintained beyond the course.
- Primary future concern: web, native iPhone, and native Android clients should share one repository and as much code as practical, without unnecessary initial overhead. The platform direction is resolved in [Choose the web and native client platform direction](issues/05-choose-client-platform-direction.md); sharing boundaries and frontend implementation deferrals are resolved in [Define shared frontend boundaries and platform adapters](issues/08-frontend-ports-and-adapters.md).
- Use the proposal's outside-V1 features as architectural stress tests, not delivery commitments: mobile access, OAuth/email authentication, notifications, viewing availability, richer discovery, people suggestions, and shows. Digital-collection screenshots are another possible future input.
- User's strong starting preferences, revisable with a stated reason: ports and adapters in backend and frontend; Pydantic models for boundary validation; Pydantic AI for LLM Gateway access; Pydantic Logfire; Neon Postgres; TMDB with room for other movie-data providers; Docker deployments; async operation. Python >=3.13 is existing project metadata, not an irreversible requirement.
- AI photo extraction uses gateway access behind ports and adapters; gateways are replaceable and may differ by task, as required in [Identify the LLM Gateway and its documented capabilities](issues/18-identify-llm-gateway.md#consequences-and-handoff). Model selection follows a separate quality investigation. Semantic search is required, with technologies undecided.
- The current transport direction is resolved in [Choose API contracts and where persistent connections belong](issues/10-api-contracts-and-transports.md#answer), superseding the original WebSocket preference. Keep async I/O, background work, and durable execution distinct.
- The proposal's detailed titles-only note-extraction increment and gpt-4.1-nano choice are historical proposal context, not proof of existing implementation or final architectural decisions. The current checkout contains no app source.
- Every decision resolution should state the choice and rationale, cost of reversal, what must be fixed now, and what can wait with a trigger. Existing preferences are inputs, not resolved decision tickets.
- A decision ticket may resolve as an explicit deferral when the human agrees that implementation can proceed safely: record the assumption or replaceable default, the boundary that preserves reversibility, and the event that requires revisiting it. Ticket coverage does not mean every technology must be selected now.
- Consult wayfinder, grilling, and domain-modeling each decision session; research and prototype tickets also use their respective skills. Update the root glossary only when domain terms are actually resolved; create ADRs sparingly for consequential trade-offs.
- Local tracker: [conventions](../../docs/agents/issue-tracker.md). Child tickets live in issues/. Query their Type, Status, and Blocked by metadata; the frontier is open, unblocked, unclaimed tickets ordered by number. Research claims are saved before investigation.
- Research assets belong on separate research/app-architecture-* branches, pushed without a PR or merge. Each research ticket links its exact context pointer. Source findings do not settle human architecture choices.
- User-directed exception: [TMDB permissions: verified clauses and workflow questions](research/provider-permissions.md) is copied into the current `docs/wayfinder-plan` branch at its original relative path; do not push its research branch. The report's recommendations do not override the human provider strategy.
- Scope and starting preferences were agreed in the wayfinder conversation on 2026-11-06 (Pacific/Honolulu).

## Decisions so far

<!-- One named link and a short gist per resolved decision. Detail belongs in the ticket. -->

The accepted direction is consolidated in [ADR-0001: Shared web and native movie-discovery architecture](../../docs/adr/0001-app-architecture.md), including rationale, trade-offs, explicit deferrals, and implementation validation boundaries. The resolved tickets below retain the detailed decision history.

- [Research approaches to sharing web, iOS, and Android code](issues/01-research-shared-mobile-approaches.md): viable sharing approaches depend on the meaning of native; the client platform remains a human decision.
- [Research HTTP and WebSocket transport trade-offs](issues/02-research-client-transports.md): connection reuse undermines a general socket-overhead advantage; the findings inform the later human transport decision.
- [Research feasibility of the proposed backend integrations](issues/03-research-backend-integrations.md): plausible integration paths exist; later provider and gateway tickets supply the permission basis and private-service documentation missing from the original research.
- [Set the architecture's quality targets and decision priorities](issues/04-architecture-quality-targets.md): public demo and web first, with future user ownership, a small operating budget, reusable refreshed catalog data, and temporary extraction inputs guiding later choices.
- [Choose the web and native client platform direction](issues/05-choose-client-platform-direction.md): Expo with React Native for Web from the start, delivering web first and sharing compatible logic/UI with future native clients while allowing platform-specific presentation.
- [Define domain identity and user-data ownership](issues/06-domain-identity-and-ownership.md): app-owned identities, user-owned Watchlist with independent statuses, deduplicated Timeline, and provider-validated import candidates; detailed structures and television tracking remain deferred.
- [Choose identity and session boundaries for web and native clients](issues/09-identity-sessions-and-client-security.md): ordinary Demo user selected initially; strict backend-enforced account isolation, username/password first for future personal accounts, and durable revocable sessions with implementation details deferred.
- [Establish permitted catalog-data use and provider strategy](issues/17-provider-permissions-and-strategy.md): user confirmed TMDB permits our use case and prohibits AI training on its data; runtime search/suggestion design proceeds with independent provider-data lifecycle.
- [Choose catalog persistence and provider-refresh boundaries](issues/12-catalog-storage-and-refresh.md): shared catalog reuse, browser-independent refresh, ID-based matching, and durable user activity; database/schema design and search-result caching remain deferred.
- [Identify the LLM Gateway and its documented capabilities](issues/18-identify-llm-gateway.md): private course gateway documented as one replaceable adapter target; different tasks may use different gateways, with feature/data-handling checks before integration.
- [Define backend ports, adapters, and deployment boundaries](issues/07-backend-ports-and-adapters.md): modular Python backend with domain-owned decisions, application coordination, async capability ports, independent gateway adapters, and external instrumentation; concrete libraries/processes remain deferred.
- [Define shared frontend boundaries and platform adapters](issues/08-frontend-ports-and-adapters.md): shared TypeScript core, distinct state ownership, backend authority, and platform/presentation adapters; remaining search behavior and concrete libraries/packages stay deferred.
- [Choose API contracts and where persistent connections belong](issues/10-api-contracts-and-transports.md): HTTPS/HTTP/2 with debounced/abortable search fetch, no WebSockets, shared wire schemas, and direct bounded Timeline ruler access; later compatibility guarantees remain deferred.
- [Define import review and background-work lifecycles](issues/11-imports-and-background-work.md): request-scoped processing and client-held review, configurable bounded retries, early raw-input cleanup, and durable confirmed saves; no initial import worker or progress channel, with global API rate limits required.
- [Define the semantic-search boundary and indexing lifecycle](issues/13-semantic-search-architecture.md): shared overview embeddings filter each user's Timeline without changing presentation; off-request preparation, one atomically updated index, incomplete coverage, and internally logged failures with empty results accepted; technology selection deferred.
- [Define recommendation inputs and trusted-result boundaries](issues/14-recommendation-architecture.md): initial structured LLM suggestions are display-only without catalog validation or saving; use existing user interests/history, avoid seen movies best effort, accept partial/empty results, and log results for observability.
- [Choose deployment, observability, and resource-control boundaries](issues/15-deployment-observability-and-resource-limits.md): one Dockerized backend, global per-API rate/usage limits behind memory-based admission with asynchronous durability and accepted approximation, HTTP refusal, restricted logs, and verified recovery; concrete deployment settings deferred.
- [Consolidate the architecture direction and explicit deferrals](issues/16-architecture-direction-and-deferrals.md): human accepted the reviewed direction and linked handoff; all architecture decisions are resolved, with implementation investigations and release checks explicitly deferred to separate work.

## Not yet specified

None. The human accepted the completed workflow review on 2026-11-09 (Pacific/Honolulu); follow-up work and revisit triggers are indexed in [Consolidate the architecture direction and explicit deferrals](issues/16-architecture-direction-and-deferrals.md#answer).

## Out of scope

- Building the app, production deployment, or delivering native apps during this map.
- A complete endpoint catalog, physical schema, UI specification, or implementation backlog unless a small detail is necessary to settle a costly architectural boundary.
- The separate database/schema investigation and search-feature specification, potentially including a caching prototype, follow this map; their boundaries and revisit triggers are recorded in [Choose catalog persistence and provider-refresh boundaries](issues/12-catalog-storage-and-refresh.md#answer).
- Selecting/tuning extraction or embedding models, building a benchmark, and running photo-quality experiments; this map identifies the boundaries and evidence those later efforts need.
- The focused semantic-search technology/quality investigation follows this map before search implementation; its scope and triggers are recorded in [Define the semantic-search boundary and indexing lifecycle](issues/13-semantic-search-architecture.md#answer).
- Implementing every outside-V1 feature or designing for an unagreed large-scale commercial workload.
