---
status: accepted
date: 2026-11-09
---

# Shared web and native movie-discovery architecture

Use one repository containing an Expo/React Native for Web client and a modular Python backend, with ports and adapters on both sides. Deliver web first while preserving future iOS and Android support, stable application-owned identities, user-owned activity, and replaceable integrations. This accepts some cross-platform setup and explicit boundary design now to avoid expensive changes to ownership, presentation, and provider coupling later.

## Context and decision basis

The app helps people discover movies through the combined filmographies of people they follow, import movies from notes or collection photos, filter their Timeline by storyline meaning, and request Movie suggestions. It is intended to remain a small, deployed, multiuser product maintained beyond the course.

This record consolidates the accepted [architecture map](../../.scratch/app-architecture/map.md) and its eighteen resolved tickets. The user accepted the combined direction on **2026-11-09, Pacific/Honolulu**, in the [consolidation decision](../../.scratch/app-architecture/issues/16-architecture-direction-and-deferrals.md#answer). This ADR records those decisions without selecting additional technologies. The linked ticket answers retain the detailed discussion, exceptions, evidence, and reversal costs; earlier proposals in their comments are historical context.

The checkout contains proposal and planning documents and Python project metadata, with no application source, dependencies, or test suite. These are accepted architectural constraints, not evidence of implemented behavior, measured quality, integration compatibility, or deployment readiness. Use the [glossary](../../GLOSSARY.md) for domain vocabulary. The [project proposal](../proposal/proposal.md) supplies product context; its titles-only increment, exact extraction limits, and `gpt-4.1-nano` selection do not establish the final import architecture or a selected model.

The operating priorities are:

- A public Demo user initially, with later private personal accounts and no social features planned.
- A provisional **$25/month total operating ceiling**, explicit paid-AI limits, solo maintenance, and occasional maintenance downtime.
- Ordinary browsing reads within roughly **one second under normal conditions**, as a target to validate. Longer AI operations show processing state.
- Durable confirmed activity, useful stored catalog data during provider outages, and saved browsing independent of AI availability.
- Online operation initially; preserve work through ordinary interruptions where practical. Offline browsing, writes, and synchronization need a separate product requirement.
- Web delivery before native delivery. Future mobile support shapes boundaries without making native releases or maximum code sharing prerequisites for web.

The expected later audience is initially tens of regular users with occasional simultaneous use. Public demo access can attract more traffic, so this estimate does not replace admission controls. These priorities come from [quality targets](../../.scratch/app-architecture/issues/04-architecture-quality-targets.md#answer).

## Decisions

### Client platform and repository

Use **Expo, React Native for Web, and TypeScript from the start**. Future iOS and Android clients use React Native's native platform views, with deliberate platform-appropriate interactions. Keep client and Python backend in one repository; introduce ordinary modules and workspace packages when actual sharing warrants them.

Share compatible presentation, client rules, workflows, and contracts. Allow platform-specific components, screens, navigation, accessibility behavior, and device integrations. Browser-only components can serve web-specific needs without becoming portable native UI. Use established compatible libraries rather than constructing a cross-platform framework. Expo hosted build/update services are optional and are not selected here.

This trades earlier adoption of React Native styling/component conventions, compatibility checks, and coordinated Expo upgrades for a common client development approach and potential UI reuse. Changing renderer families after substantial UI work would require replacing components, styling, navigation, and integrations. Framework-independent TypeScript logic should be easier to retain. Native feel, accessibility, performance, and actual reuse require later device validation.

Source: [client platform direction](../../.scratch/app-architecture/issues/05-choose-client-platform-direction.md#answer), informed by [sharing research](../../.scratch/app-architecture/issues/01-research-shared-mobile-approaches.md#answer).

### Domain identity, ownership, and Timeline membership

Movies and people have **stable application-owned IDs**. Provider mappings include provider and entity type; titles, names, credentials, and devices are not durable identity keys. One Person retains one identity across cast and crew work, and Credits describe participation and roles in a Movie. A Follow initially covers all that Person's movie credits; role-specific following is deferred.

Shared catalog records describe Movies, People, and Credits. Follows and Watchlist entries belong to an explicit app-owned user, including the Demo user. A Watchlist entry is one user's saved relationship with one Movie, with independent **seen status** and **watch status**. Seen movies and repeat-viewing intentions remain in the Watchlist until explicitly removed. Changing either status does not implicitly change the other or remove the entry.

The **Timeline** is the chronological, deduplicated union of movies contributed by followed people's Credits and the user's Watchlist. A Movie appears once regardless of how many contributions exist. A saved Movie needs no followed person to appear; a followed Movie needs no Watchlist entry. Removing one contribution removes the Movie only when no other contribution remains. Storyline search filters this list without changing its underlying membership or presentation.

Provider validation, user confirmation, and identity reconciliation are different responsibilities. Reuse known provider-ID mappings; conflicting mappings remain unresolved rather than automatically merging established records. Provider changes must preserve existing app identities and user activity. Keep provider references aware of entity type now, while show/season/episode structures wait until shows become a delivery requirement.

Source: [domain identity and ownership](../../.scratch/app-architecture/issues/06-domain-identity-and-ownership.md#answer).

### Backend boundaries and dependency direction

Start with **one modular Python backend**. API entry points and any future workers share domain and application code. Internal boundaries provide separation without requiring separate services.

| Responsibility | Ownership and dependencies |
| --- | --- |
| Domain objects, rules, and services | Make domain decisions in ordinary Python, independent of Pydantic, API frameworks, database libraries, and provider SDKs. |
| Application operations and ports | Obtain facts, invoke domain decisions, sequence workflows, and coordinate transactions through application-owned contracts; do not depend on concrete adapters. |
| API and future worker entry adapters | Translate incoming representations and invoke application operations. |
| Persistence, provider, gateway, identity/session, and retrieval adapters | Implement capability ports and translate external data and failures into application-owned representations. |
| Startup/configuration and instrumentation | Compose adapters and wrap operations/calls; core logic does not import wiring or Logfire. |

Introduce ports for real workflow capabilities. Extraction, suggestions, and embeddings can use independently configured gateways concurrently; replacing one must not force domain/application changes or replacement of every other task's gateway. Pydantic AI is the preferred gateway integration inside adapters and supplies the required suggestion-output format.

Use **Pydantic at boundaries**, including API schemas, provider payloads, and model results. Structural validation does not prove domain validity or establish a trusted movie identity. Keep domain rules separate from orchestration and adapters.

Use **async external I/O** for persistence, provider, and gateway ports; ordinary domain rules remain synchronous. Application operations own transaction boundaries through persistence contracts and avoid keeping database transactions open during provider/model calls. Async execution alone provides neither background scheduling nor durable execution.

Adapters classify external failures in application-owned terms, including unavailable service, invalid output, and exhausted budget. One explicit operation policy coordinates SDK, transport, correction, and workflow attempts to avoid multiplying retries. Transport adapters map those failures to client responses.

Source: [backend ports and adapters](../../.scratch/app-architecture/issues/07-backend-ports-and-adapters.md#answer), with feasibility context from [backend integration research](../../.scratch/app-architecture/issues/03-research-backend-integrations.md#answer).

### Shared frontend boundaries and state

Keep useful client domain rules and workflow coordination in an **ordinary TypeScript core**, independent of React, Expo, routing, browser APIs, and native APIs. Client application workflows depend on client-owned ports and domain rules. Presentation and connecting hooks invoke that core; startup selects the platform adapters. These are logical responsibilities rather than prescribed packages.

Backend access, credential handling, media input, and lifecycle events use focused adapters. Backend-access adapters translate transport errors and validate responses at runtime. Navigation, route formats, hooks, and platform SDKs stay outside the shared core; workflows receive ordinary inputs such as Movie IDs. A capability may be unavailable on a platform.

Keep state ownership explicit: Timeline and Watchlist data are cached backend state; extraction review is temporary workflow state; an open menu is screen-only state. Scope private state to its user and temporary state to its initiating workflow. Simple screen state can remain in components; no global store or cache library is selected.

Client validation supports interaction feedback. The **backend remains authoritative** for saved data, ownership, and backend domain decisions. Shared TypeScript rules do not require duplicating every Python rule, and Python Pydantic models do not execute on clients. Provider/backend credentials stay server-side; client session credentials use their platform adapters.

Source: [frontend boundaries](../../.scratch/app-architecture/issues/08-frontend-ports-and-adapters.md#answer).

### Acting user, personal accounts, and sessions

Initially the backend automatically selects the **ordinary Demo user**, with no login gate, credential exchange, or signed-out state. Visitors share that user's confirmed activity. This does not make their raw inputs or pending review public.

Future personal users start with no Follows and an empty Watchlist; signup does not claim or copy Demo activity. The same app-owned identity owns activity across devices and authentication methods. **Username/password** is the first personal authentication method; implementation follows the public demo. Credential verification, session handling, and activity ownership remain separate.

The backend resolves the acting user through a trusted mechanism and enforces account ownership on reads and changes. A client-supplied user ID does not authorize access. Future personal sessions must be durable across ordinary client/server restarts, revocable, and subject to expiry/logout. Protected browser cookies with appropriate request protections and OS-protected native credential storage are starting directions; exact libraries, formats, stores, and timeouts are deferred.

An invalid personal session requires sign-in and must not silently redirect edits or retries to Demo. Returning to demo mode is explicit. Sign-out/account switching clears private cached data and review state; late work cannot be applied to another account. Personal deletion must end account access and prevent later work from recreating deleted activity, with backup expiry handled separately from live deletion. Shared catalog records are not owned by the deleted account.

Source: [identity, sessions, and client security](../../.scratch/app-architecture/issues/09-identity-sessions-and-client-security.md#answer).

### API contracts and transport

Use **HTTPS request/response with HTTP/2 on the client-facing service** for searches, browsing, writes, and uploads. Use debounced, abortable fetch for search requests. WebSockets are excluded for the current architecture, superseding the initial preference. Verify actual HTTP/2 negotiation through the deployed client-facing path and document proxy/backend hops; selecting fetch or an async framework does not establish protocol support.

API-specific Pydantic schemas are the wire-contract source, separate from domain and provider models. Derive TypeScript types and runtime validators where practical. Exact endpoint fields, code generation, and the API framework remain deferred. Use consistent HTTP statuses and machine-readable codes, safe messages, and useful validation details; clients do not parse prose or receive provider exception internals.

Distinguish accepted work from committed changes. Prefer desired-state writes, such as setting a status, over toggles. Define duplicate handling before automatically retrying nonrepeatable or billable operations. A lost acknowledgement can leave a committed outcome uncertain; request IDs and browser abort do not establish exactly-once execution, cancellation, or rollback.

Potentially large Timeline, Watchlist, and search responses are bounded with explicit pagination metadata. The **Timeline ruler** directly requests a bounded window at a chosen time, with active filters and earlier/later navigation. Sequential traversal of intervening pages or downloading the whole Timeline does not satisfy this requirement. Date semantics, ties, empty periods, page sizes, and indexing follow feature/database design.

Breaking API changes are acceptable while backend and clients develop together. Compatibility/versioning and a supported-client window must be addressed before independently released clients or deployments require cross-version operation.

Source: [API contracts and transports](../../.scratch/app-architecture/issues/10-api-contracts-and-transports.md#answer), informed by [transport research](../../.scratch/app-architecture/issues/02-research-client-transports.md#answer).

### Catalog providers, persistence, and refresh

Use **TMDB as the default provider** and a relational persistence direction with **Neon Postgres as the starting preference**. Physical schema, database libraries, and migration tools require a separate investigation. Separate shared catalog/provider data from user-owned activity and preserve one Watchlist relationship per user–movie pair.

Retain workflow-discovered provider data in a shared catalog and reuse it across users while fresh. Do not assume complete provider-catalog coverage. People search and workflows needing provider coverage perform provider lookups; other workflows can use stored entities and fetch missing information. Stored entities do not require query-result caching or imply that a partial local catalog can reproduce provider search.

Application-side retrieval/refresh manages provenance, freshness, permitted retention, and provider access behind adapters. The browser displays available data without deciding refresh policy. Stored data remains useful during outages within retention limits; failed refresh does not reset freshness or extend allowed retention.

Confirmed Follow/Watchlist changes are durable and visible on the next Timeline read. Provider corrections become visible after successful refresh. Failed or incomplete Credit refresh must not remove existing Credits; removals require successful refresh complete for the relevant collection. Refresh may change Follow-derived Timeline membership while preserving Watchlist entries and statuses.

Provider metadata and derived representations must be independently refreshable, rebuildable, and removable while preserving application identities and user activity. Preserve provenance rather than tying the lifecycle of user choices to a provider record.

For planning, use the user's **November 9 confirmation** that TMDB permits this app's use case and prohibits training AI on its data. Runtime inference and embeddings with existing encoders are eligible within that confirmed use case. This is a recorded user-supplied basis, not new independent permission verification. Earlier blanket exclusions of TMDB content from prompts and generic provider-clarification prerequisites are superseded. Do not train or fine-tune on TMDB content or allow training reuse by receiving services. Attribution, purge, retention, and backup details still need release configuration. Revisit licensing if the noncommercial purpose or intended use changes.

Sources: [catalog storage and refresh](../../.scratch/app-architecture/issues/12-catalog-storage-and-refresh.md#answer) and [provider permissions and strategy](../../.scratch/app-architecture/issues/17-provider-permissions-and-strategy.md#answer).

### Note/photo imports and temporary work

Initially extraction and matching run asynchronously **within the originating HTTPS request**, without a durable queue, separate import worker, or server-side pending-review store. Return extracted titles and validated candidates to the initiating client, which owns unconfirmed review state. Show an indeterminate processing indicator; no polling, SSE, or job-result retrieval service is required.

The trust sequence is extraction → provider matching → user review → confirmed save. Initial TMDB matching searches by title, presents only provider-validated Candidate movies, and offers 1–3 ranked alternatives when ambiguous. Titles without validated matches are excluded from the selectable list. The user chooses the Movie and independent statuses; DVD ownership does not establish seen status.

Only confirmation persists activity. Reimporting updates the existing user–movie relationship. If saving fails, retain choices and retry the same Movie IDs/statuses without rerunning extraction or duplicating entries. Successful confirmation ends only after commit; uncertain acknowledgement requires save reconciliation/retry. Backend validation and ownership enforcement still apply to submitted selections.

Release backend copies of raw notes/photos as soon as extraction no longer needs them. Keep raw inputs out of durable records, backups, and telemetry. The client may retain input for retry until the interaction ends through successful confirmation, cancellation, or workflow exit. Brief connection loss/backgrounding does not itself end the interaction. Bound abandonment by expiry and implement temporary-file/crash cleanup.

Cancellation is best effort. Discard late unconfirmed results on cancellation, expiry, or exit; never automatically save or publish them into another workflow/account. A browser abort does not guarantee upstream cancellation or undo committed changes. Preserve input/review through ordinary interruptions while the page remains open where practical, but full reload/server-restart recovery is not guaranteed.

Configure bounded retries per task/gateway, with separate transport and output-correction budgets and an overall deadline. Coordinate all retry layers. Terminal failures such as the documented course gateway's exhausted-budget `429` are not retried; other services' errors require their own classification. Per-request bounds do not replace global rate/usage limits.

Client-held review keeps visitors' private temporary work separate despite shared Demo ownership, without requiring a Demo session or a token solely for pending-review retrieval. If stronger continuation or server-held review becomes necessary, design workflow identity, authorized status/result retrieval, retention, recovery, and cleanup before choosing polling versus SSE. WebSockets remain excluded.

Source: [imports and background-work lifecycles](../../.scratch/app-architecture/issues/11-imports-and-background-work.md#answer).

### Semantic search

Semantic search is a **storyline filter over the acting user's eligible Timeline**, combined with other active filters. Match beyond the loaded window and apply eligibility before selecting/paginating the displayed window. Preserve chronology, deduplication, presentation, and direct ruler navigation. Do not substitute relevance-ordered global discovery or filter an arbitrary global top-k list after retrieval. Search does not change saved activity or underlying Timeline membership.

Start with available **TMDB overviews** associated with app-owned Movie IDs. Share movie embeddings across users while keeping user-specific eligibility authoritative on the backend. Prepare movie embeddings outside live search when text is added/changed. Live queries embed the user's query and search prepared representations; they do not create missing movie embeddings or generate descriptions.

Use **one atomically updated index** and search available data. Let the database manage its indexes. No durable queue, parallel replacement indexes, or elaborate version machinery is required initially. Missing overviews/pending embeddings may omit movies from semantic matches, with an indication of incomplete coverage; ordinary browsing still includes them. Optional supplemental generated descriptions would run as off-request worker tasks if later justified by quality/coverage evidence.

Embedding and retrieval failures are logged internally and may appear as empty results, optionally with high-level messaging. Preserve the query and other filters instead of silently disabling semantic filtering. Admission refusal remains an HTTP failure under the operational decision below.

Embedding, representation persistence, and retrieval use replaceable capability ports. Query/movie representations must be compatible. The model, gateway, vector store, matching threshold, retrieval method, preparation scheduling, and rebuild mechanics remain unselected. In particular, selecting Neon for relational storage does not settle semantic storage suitability. Evaluate quality, latency, cost, and Neon suitability before search implementation. Changing embedding space can require regeneration and temporary coverage gaps; changing only a gateway need not change that space.

Source: [semantic-search architecture](../../.scratch/app-architecture/issues/13-semantic-search-architecture.md#answer).

### Movie suggestions

Initial Movie suggestions are **display-only structured LLM output**, with no catalog lookup, identity resolution, or save action. They may be outside the Timeline. They are not Candidate movies, established catalog identities, or Watchlist entries. Validation and an explicit save workflow must be introduced before suggestions can be saved; import validation remains unchanged.

The backend supplies the acting user's Follows and Watchlist, including independent statuses, as context. Additional user text is not required. Viewing history is not a positive rating. Unseen movies already saved remain eligible. Instruct the model to avoid seen movies, accepting this as best effort rather than guaranteed identity-based exclusion.

Use the independently configured suggestion adapter and Pydantic AI's required output format with boundary validation. Target three suggestions, accepting fewer or none after configured attempts without a loop solely to fill slots. Structural validity does not prove that a movie exists. Run within the HTTPS request; the client holds results, with no initial suggestion-history store or background/recovery service. No semantic-retrieval step is required.

Log failures internally; partial/empty results and optional high-level messaging are acceptable. **Log suggestion results for observability** as the explicit exception to default reply-content exclusion. This does not authorize full prompt/history logging or make telemetry trusted catalog data or a saved-suggestion feature. Admission refusals still require an HTTP status.

Source: [recommendation architecture](../../.scratch/app-architecture/issues/14-recommendation-architecture.md#answer).

### Gateway integration

The private course **LLM API Gateway** is one available adapter target, not an exclusive dependency. Its [identification ticket](../../.scratch/app-architecture/issues/18-identify-llm-gateway.md#answer) records supplied documentation for OpenAI-compatible interfaces, bearer authentication, usage metadata, an embeddings endpoint, and gateway-specific errors. Those are documented capabilities rather than runtime verification or a model selection.

Before integration, verify the selected model/endpoint through the intended async Pydantic AI adapter: discovery, minimal requests, image inputs where needed, structured output, usage fields, errors, deadlines, and cancellation. Do not infer vision, schema support, durable jobs, or conversation recovery from protocol compatibility. Verify upstream retention/training-reuse settings before sending personal inputs or TMDB content. Recheck access, funding, and key validity before relying on the course gateway beyond the course.

### Deployment, resource controls, and observability

Start with **one Dockerized backend deployment**, managed Neon persistence, and Logfire instrumentation. Containers are replaceable; durable data resides outside them. Supply secrets through deployment configuration and run migrations as a controlled release step. Hosting, web serving, process count, pools, and placement of off-request preparation remain implementation choices.

Every API needs **global rate and cumulative usage limits**, covering incoming requests and outgoing provider/gateway calls across visitors, tasks, and processes. Outgoing attempts include retries and background preparation. When a cumulative limit is exhausted, start no new usage of that API until the limit is raised; do not assume automatic periodic replenishment. App-owned limits supplement upstream quotas and do not depend on a gateway remaining-budget endpoint. Keep unrelated available workflows usable under their own limits.

Expose admission as whether a request is permitted now through an application-owned port. Entry adapters enforce incoming limits; integration adapters enforce outgoing admission before calls. Domain/feature logic does not inspect counters or synchronization policy.

Admission decisions use **memory**, accounting for admitted/in-flight work immediately, with **asynchronous durable usage updates**. Initialize from durable totals after restart. Shared totals include all serving/preparation processes; separate process-local allowances must not multiply the global allowance. Approximate enforcement is accepted for abuse protection: in-flight calls, delayed synchronization, and unpersisted recent usage after a crash can cause overshoot. Choose tolerances/delays before release; this is not an exact spend guarantee. Stronger coordination needs observed justification.

Bound expensive concurrency and interactive waiting. Refuse denied admission promptly with an **HTTP status**; exact status/code and presentation follow implementation. This requirement refines the otherwise permitted empty-result behavior for semantic-search/suggestion service failures. Background preparation can wait for a later opportunity under its scheduling policy. Align operation/retry bounds and proxy deadlines; do not introduce unbounded waiting.

Instrument around operations and adapters, keeping Logfire outside domain/application logic. Capture timings, outcomes, usage, and correlation IDs, including failures presented as empty results. Restrict logs to maintainers and finite retention. Exclude raw notes/photos, prompts, credentials, and unauthorized content; the suggestion-result exception is narrow. Verify actual redaction and content-capture settings before release.

Use the simplest adequate backup arrangement, preferably managed facilities, and **perform a restore check before release**. Raw extraction inputs must not enter backups. Restoration must respect user deletion, revoked access, and provider-data cleanup while preserving app-owned identities/activity independently of provider metadata/derived representations. Select retention and recovery targets during deployment implementation.

Source: [deployment, observability, and limits](../../.scratch/app-architecture/issues/15-deployment-observability-and-resource-limits.md#answer).

## Alternatives and trade-offs

| Alternative | Accepted direction and reason |
| --- | --- |
| Separate React DOM web app followed by a mobile app | Expo/React Native for Web from the start accepts earlier framework constraints in exchange for shared development and possible UI reuse. Platform-specific presentation remains allowed. |
| Provider IDs or names as durable identities | App-owned identities and qualified mappings preserve activity across provider changes and avoid name-based merges. This requires explicit reconciliation and provenance. |
| Domain behavior in handlers, UI, or SDK wrappers | Inward dependencies and domain-owned decisions preserve replaceability at the cost of explicit contracts and translation. Avoid speculative ports/packages. |
| WebSockets as the general transport | HTTPS/HTTP/2 follows the user's revised direction; transport research did not justify a general socket-overhead advantage. Initial workflows need no persistent progress channel. |
| Durable import workers and stored review immediately | Request-scoped processing and client-held review reduce infrastructure and retention complexity while accepting loss of unconfirmed state after reload/restart. Off-request movie preparation remains separate. |
| Global relevance search or live embedding preparation | Timeline filtering and prepared shared representations preserve product semantics and bound live work, accepting incomplete coverage and deferred retrieval-quality choices. |
| Catalog-validated, saveable suggestions initially | Display-only output keeps the first feature small while accepting inaccurate/seen suggestions and postponing deterministic exclusion and saving. |
| Exact synchronous durable quota enforcement | Memory admission plus asynchronous persistence avoids durable-store latency on admission while accepting overshoot and requiring later tolerance validation. |
| Separate backend services from the start | One modular deployment fits solo maintenance and the provisional budget; service separation waits for demonstrated scaling or failure-isolation needs. |

## Deferred decisions and revisit triggers

The architecture direction is complete at the map's scope. The following are explicit follow-up work rather than selected implementation details or unresolved architecture tickets.

| Follow-up | Trigger and constraints |
| --- | --- |
| Physical schema, IDs, constraints/indexes, database libraries, migrations, and Timeline queries/materialization | Separate database/schema investigation before persistence implementation. Preserve identity/ownership, next-read user-write visibility, safe complete refresh, and direct filtered ruler windows. |
| API framework, endpoint fields/error catalog, schema generation, client libraries, state/cache/navigation tools, and package layout | Choose before implementing the relevant boundaries; keep dependencies and contract ownership above. |
| Search triggers/timing, obsolete-result handling, query-result caching, and detailed Timeline behavior | Search/Timeline feature specification and latency evaluation, potentially a prototype. Debounced abortable fetch does not select a latest-request-wins policy, cache, or exact debounce interval. |
| Semantic model/gateway/store, threshold/retrieval method, representative queries, and quality criteria | Focused investigation before search implementation. Assess storyline quality, coverage, latency, cost, and Neon suitability. |
| Preparation scheduling/retries, atomic publication, restart behavior, and rebuild procedure | Define during preparation implementation and before changing embedding space/text representation. Stronger durability, parallel indexes, or generated descriptions require demonstrated benefit. |
| Extraction/suggestion models, prompts, output fields, ranking, context bounds, retries, and deadlines | Feature specification and compatibility/quality checks before integration. Photo/model benchmarking remains a separate investigation. |
| Personal authentication/session details, provisioning/recovery, deletion, extra methods/linking, and demo-copy features | Before enabling the relevant personal-account feature. Keep backend isolation, durable revocable sessions, explicit demo transitions, and empty initial personal activity. |
| Durable workflows, authorized server-held review/results, polling/SSE, richer progress, and stronger recovery | Measured request times exceed practical deadlines or a concrete continuation/recovery requirement arises. Design state access/recovery before choosing notification delivery. |
| Validated suggestions, strict seen exclusion, saving, history, or richer recommendation strategies | Before saving is enabled or inaccurate/repeated seen suggestions justify stronger behavior; history/richer strategies require a product need. |
| Hosting/proxy topology, serving/preparation processes, pools, release tooling, and secret delivery | Deployment implementation. Verify actual HTTP/2, total cost, and normal browsing latency before release and after topology changes. |
| Limit keys/units/values, accounting store, synchronization/startup, overshoot tolerance, HTTP refusal codes, and operator controls | Before public API/provider integration and release. Strengthen coordination if observed overshoot becomes unacceptable; no implicit replenishment. |
| Telemetry retention/redaction/access, alerts/sampling, input expiry/crash cleanup, attribution, backups, and restore-time deletion handling | Configure and verify before release; personal deletion mechanics before offering deletion. Perform a restore check. |
| Compatibility guarantees and supported-client/version window | Before clients or deployments release independently, including native releases. |
| Native build/signing, navigation/capability details, accessibility, and device acceptance | When native delivery is scheduled, or earlier if a required capability cannot be supported. Hosted Expo services remain optional. |
| More services, higher availability, or larger capacity | Demonstrated scaling/failure-isolation need, changed operating goals, persistent ordinary-browse latency above the rough target, forecast cost beyond $25/month, or sustained rejections/preparation failures. |
| Provider changes, identity conflicts, licensing, or post-course gateway reliance | Actual conflicts/new providers, a changed use/purpose/terms, or continued gateway use beyond coursework. Preserve user activity; recheck integration/data handling and service access. |

## Validation and implementation handoff

This documentation change is validated against resolved ticket answers, glossary vocabulary, and local references. It does not introduce a runtime test seam or claim runtime acceptance. No application test prior art exists in this checkout.

When implementation is specified, prefer the highest useful behavioral seam: the public application workflow through its API/client contract, with controlled external adapters. Add a real persistence/integration check where substitutes cannot establish durability, refresh atomicity, or shared accounting behavior. Exact test tooling follows the relevant implementation specifications.

Behavioral evidence should cover these boundaries rather than internal class/package structure:

- Multiple Follows and Watchlist contributions produce one chronological Movie; independent statuses and removal rules persist correctly. Confirmed writes survive restart and appear on the next Timeline read; incomplete refresh preserves Credits.
- Demo visitors share confirmed activity while temporary inputs/review remain isolated. Future private users cannot access another owner's data; session expiry, switching, late work, and deletion preserve ownership.
- Imports expose only provider-validated candidates and save only confirmation; save retry does not rerun extraction or duplicate activity. Cancellation/expiry discards late unconfirmed output and cleans temporary inputs.
- Semantic filtering covers the eligible Timeline beyond the loaded window, preserves ruler access/order/other filters, reports incomplete coverage, and keeps ordinary browsing usable when AI fails. Service failure and admission refusal retain their distinct contracts.
- Suggestions remain display-only without catalog/activity writes, permit partial/empty output, and use only the acting user's context. Logging respects the explicit result-only exception and broader content exclusions.
- Limits account for retries/preparation and all processes, survive restart within accepted approximation, block exhausted APIs until limits rise, and return HTTP refusal without unbounded waiting.
- Integration/release checks establish actual gateway features/data handling, client-facing HTTP/2, cleanup/redaction, budget/latency feasibility, and backup restoration. Native behavior requires device checks when native delivery begins.

## Consequences and scope

The costly commitments are the client renderer family, stable identity/ownership model, Timeline/Watchlist semantics, dependency direction, and the trust/lifecycle boundaries between imports, search, suggestions, and saved activity. Changing them after substantial UI or data accumulation can require UI replacement, reconciliation, migrations, or revised contracts.

Adapters keep libraries, hosting, gateways, persistence mechanisms, and retrieval technology replaceable, but replacement is not free: stored data may need migration, provider conflicts need reconciliation, and changed embedding representations need regeneration. A session-format change may expire deployed sessions. Broader continuation/recovery would add workflow state, access, retention, and cleanup responsibilities that the initial request-scoped design intentionally postpones.

Accepted limitations include shared public demo edits, no guaranteed temporary-review recovery after reload/restart, incomplete semantic coverage, empty results on selected service failures, unverified display-only suggestions, approximate usage caps, and maintenance downtime. These are deliberate starting boundaries with the revisit triggers above.

This ADR does not build the app, create an implementation backlog, specify every endpoint/table/screen, select models or vector technology, run extraction benchmarks, deploy production, or deliver native clients. Offline synchronization, notifications, viewing availability, richer discovery, people suggestions, role-specific following, and television tracking remain future product work. Future decisions that change this direction should explicitly identify the affected part of ADR-0001 and record why it is superseded.
