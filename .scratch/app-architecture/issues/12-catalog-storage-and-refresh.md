# Choose catalog persistence and provider-refresh boundaries

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 06, 09, 17

## Question

Which persistence and provider-refresh boundaries should guide shared catalog records, credits, external identities, and per-user tracking while supporting Timeline queries and future data providers? Decide sources of truth, refresh/reuse boundaries, identity reconciliation, consistency expectations, and preservation of user activity. Use TMDB usage constraints and the domain model. Preserve an explicit strategy for possible TV support without designing a complete future schema. The user accepts the relational direction with Neon as the starting preference; detailed database and schema design require a separate investigation.

## Context

Apply [Set the architecture's quality targets and decision priorities](04-architecture-quality-targets.md#answer). Trace provider API data through application storage to browsing, including how repeated equivalent queries reuse stored information. Distinguish optional cached query results from stored catalog entities. Establish refresh responsibilities and failure behavior here; exact freshness windows and scheduling mechanisms remain for later investigation. Apply the resolved provider decision below when designing the reusable copy.

Apply [Define domain identity and user-data ownership](06-domain-identity-and-ownership.md#answer) for application-owned movie/person IDs, provider mappings, Person/Credit/Follow distinctions, the Watchlist, and deduplicated Timeline membership. Keep physical data structures and database/schema design for the separate investigation requested below; the lightweight user–movie Watchlist relationship is an accepted direction, not a finalized schema. Decide how provider conflicts and duplicate catalog records are reconciled while preserving existing identities and user activity. Provider validation alone does not authorize merging established app identities; keep provider integration and reconciliation responsibilities separated through ports and adapters. Provider references must distinguish entity types now; show/season/episode structures and tracking are deferred until shows become a delivery requirement.

Carry forward [Establish permitted catalog-data use and provider strategy](17-provider-permissions-and-strategy.md#answer), updated on 2026-11-09: the user confirmed TMDB allows our use case and prohibits training AI with its data. Provider metadata and derived indexes must remain independently refreshable and removable while preserving app-owned identities and user activity. Retain provenance and lifecycle information, and plan against the documented cache/purge and attribution requirements. There is no unresolved provider-permission prerequisite for the confirmed search/suggestion workflows; exact corpus, model, and input decisions remain with their owning tickets.

## Comments

### Human discussion — 2026-11-09 (Pacific/Honolulu), first round

- Accepted a relational starting direction for shared catalog records and user-owned activity, including one Watchlist relationship per user–movie pair. Database and schema design must be a separate investigation; this ticket does not settle physical tables, columns, database libraries, or migration tooling.
- Accepted workflow-driven catalog growth. The app will never hold the complete provider catalog. Some actions, such as people search, need a direct provider lookup; other actions should use the stored catalog first and look up provider data when necessary. Determine lookup behavior per workflow rather than assuming local data can answer every provider search.
- The architecture should minimize unnecessary provider API calls across users and repeated usage while previously retrieved data remains fresh. Shared provider data and private user activity must retain their separate ownership boundaries.
- Search-result caching is an option, not an accepted requirement. Search is a hot path and caching must not introduce noticeable delay or worsen the user experience. Decide whether and how to cache queries when specifying search behavior, including search-as-you-type versus explicit submission, potentially with a prototype. Reusable stored catalog entities do not depend on adopting query-result caching.
- Freshness policy, conflict/reconciliation behavior, and consistency boundaries still need discussion. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), final round

- Accepted displaying available stored data while refresh is handled separately, with an explicit responsibility boundary: the browser neither knows nor cares about data freshness. It displays available catalog data; freshness checks and refresh decisions belong outside browser presentation. This does not authorize retaining data beyond applicable retention limits.
- Accepted ID-based identity matching. Reuse established provider-to-app mappings; do not match or automatically merge identities on titles or names. Ambiguous or conflicting mappings remain unresolved rather than silently changing established identities or user activity.
- Accepted that saved Follow and Watchlist changes appear on the next Timeline read, while provider credit discoveries/corrections appear after successful refresh. Failed or incomplete refreshes must not remove existing Credits. A successful, complete refresh may change the movies contributed by a Follow without removing explicitly saved Watchlist entries or changing their statuses.
- These answers settle the remaining architecture boundaries. Detailed database/schema design and search-result caching remain explicitly deferred as discussed above.

## Answer

Resolved through human discussion on 2026-11-09 (Pacific/Honolulu).

### Choices and rationale

- **Relational direction, separate database/schema investigation.** Use the accepted relational starting direction with Neon Postgres as the existing preference. Separate shared Movie, Person, Credit, and provider data from user-owned Follows and Watchlist activity, with one Watchlist relationship per user–movie pair. This establishes logical relationships, not a final physical schema or database access stack.
- **Workflow-driven, shared catalog reuse.** Provider lookups supply data that is retained in the shared application catalog and reused across users while fresh. The app never assumes it has the complete provider catalog. People search and other workflows requiring provider coverage use a provider lookup; other workflows may use stored catalog data first and fetch missing information as necessary. Minimize unnecessary repeat provider calls across users and repeated usage without making every workflow follow the same lookup sequence.
- **Browser presentation and refresh are separate responsibilities.** The browser displays whatever catalog data is available through the application. It does not inspect freshness or choose when to refresh. Application-side retrieval/refresh responsibilities manage provenance, freshness, provider access, and permitted retention behind ports and adapters. Available stored data remains useful during refresh and provider outages; failure must not reset its freshness or extend retention limits. Exact orchestration and scheduling remain deferred.
- **Stored entities do not require query-result caching.** Reusing catalog records is accepted. Caching the results of a particular search query is optional and deferred until search behavior is specified and its latency can be assessed. Do not assume a partial local catalog can reproduce a provider search. Search-as-you-type versus explicit submission and a possible prototype should inform whether caching improves the experience without noticeable delay.
- **Match identities by IDs.** Stable app-owned Movie/Person identities use provider mappings qualified by provider and entity type. Reuse known mappings; titles and names are not identity-match or merge keys. Names/title searches may discover candidates, but those candidates are identified by IDs. Conflicting mappings remain unresolved rather than automatically merging established app records. Keep reconciliation separate from provider lookup/validation; future merge tooling must preserve user activity.
- **User changes and catalog refresh have distinct consistency boundaries.** Confirmed Follow and Watchlist writes are durable and appear on the next Timeline read. Provider discoveries and corrections become visible after successful refresh. A failed or incomplete credit refresh must not remove existing Credits; removals require a successful refresh complete for the relevant credit collection. Follow-derived Timeline membership may then change, while Watchlist entries and their independent statuses remain intact. The Timeline continues to deduplicate by app-owned Movie identity.
- **Preserve independent data lifecycles.** Carry forward the resolved provider strategy: provenance and lifecycle information allow provider metadata and derived indexes to be refreshed, rebuilt, or removed independently of app-owned identities and user choices. Retention/cleanup is a separate responsibility from browser freshness behavior. Entity-type-aware provider references preserve the future television boundary; show/season/episode structures remain deferred.

### What must be fixed now

Keep catalog reuse shared across users and personal activity owned by its user. Preserve stable app IDs, scoped provider mappings, ID-based reconciliation, browser-independent refresh, durable user writes, and safe handling of incomplete refreshes. Do not make query-result caching or a complete local provider catalog an architectural prerequisite.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary / starting direction | Revisit trigger |
| --- | --- | --- |
| Database and physical schema design, identifier formats, constraints, indexes, database libraries, and migration tooling | Relational direction with Neon as the starting preference; stable identities and the agreed logical relationships | A separate database/schema investigation before committing persistence implementation; beyond this map's architecture-direction destination |
| Exact freshness windows by data type, refresh scheduling, duplicate-call suppression, and retry mechanisms | Shared reuse while fresh; refresh managed outside the browser; retain freshness/provenance information and honor retention limits | Before implementing provider retrieval/refresh, then when observed freshness needs, traffic, or provider-call volume change |
| Query-result caching and expiry, search-as-you-type versus submission | No query cache required by this decision; provider search remains available for catalog coverage | Search-feature specification and latency evaluation, potentially using a prototype |
| Merge tooling, provider-conflict resolution details, and field precedence across providers | Known ID mappings only; preserve unresolved conflicts and established identities/activity | An actual identity conflict or addition of another provider |
| Timeline query/materialization strategy and refresh publication mechanics | Next-read visibility of saved user changes; safe complete-credit refresh; deduplicated Timeline; support the later Timeline ruler direct filtered-window requirement recorded in [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md#answer) | Database/schema investigation and measured query/refresh needs, including direct access to a chosen time position and earlier/later windows |
| Derived-index freshness, rebuild, and deletion mechanics | Provider-derived data remains independently removable and rebuildable | [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md) |
| Purge/backup operations and attribution presentation | Carry forward provider lifecycle obligations without involving browser freshness logic | [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md) before release |
| Television structures and tracking | Provider references distinguish entity types | Shows become a delivery requirement |

### Cost of reversal

Changing physical storage or refresh mechanisms remains feasible behind the persistence/provider boundaries, although accumulated data may require migrations or rebuilds. Provider-owned durable identities, name-based merges, user activity coupled to provider metadata, or browser-owned refresh policy would make later changes substantially more expensive. Those boundaries are settled now; the separate investigations refine implementation within them. No additional prerequisite decision ticket is needed for this resolution.
