# Define the semantic-search boundary and indexing lifecycle

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 07, 12

## Question

What is the semantic-search contract: searchable corpus, retrieval unit, eligibility rules, user query and filters, result provenance, and freshness? Decide how embeddings, indexing/reindexing, and retrieval fit behind ports, what Postgres/Neon can support, and which technology choices require a research ticket after these requirements are settled. Separate retrieval from recommendation generation and decide what must be fixed now versus measured later; do not assume a model or vector store.

## Context

Apply [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md#answer). Refine the capability contracts needed by semantic retrieval/indexing within those dependency and responsibility boundaries; this ticket owns their feature-specific details rather than fixing a backend-wide gateway or library.

Apply [Establish permitted catalog-data use and provider strategy](17-provider-permissions-and-strategy.md#answer), updated by the user's confirmation on 2026-11-09: TMDB allows the app's use case and prohibits training AI with its data. TMDB descriptions are eligible for the semantic-search corpus; generating embeddings with an existing encoder is not excluded by the earlier unresolved-permission discussion. Do not train or fine-tune models on TMDB data, and ensure any external service processing it respects the no-training restriction.

Choose the corpus, retrieval unit, representation-generation method, model/store, quality criteria, freshness, and reindexing behavior on product and technical grounds. Keep provenance and independently removable/rebuildable derived indexes. LLM-generated descriptions remain an optional candidate; a replacement text source or provider clarification is not a prerequisite for the confirmed use case.

[Identify the LLM Gateway and its documented capabilities](18-identify-llm-gateway.md#answer) records a documented embeddings endpoint and an available embedding model. This is an option to evaluate, not a model choice or proof of quality. Embeddings may use a different gateway from extraction or suggestions under the user's gateway-independence requirement. Upstream training/retention settings and runtime compatibility remain checks before integration; maintain a replaceable embedding boundary and account for reindexing if the embedding model or representation changes. A gateway change alone does not necessarily require reindexing when the embedding space remains compatible.

## Comments

The November 6 candidate discussion below is historical; the November 9 confirmation in Context supersedes its permission concerns and any implied need to replace TMDB descriptions.

### Candidate corpus — 2026-11-06 (Pacific/Honolulu)

The user proposed generating a movie description with an LLM to avoid supplying TMDB data to AI, then using that generated description as the semantic-search text. Record this as a candidate, not a selected implementation or evidence of retrieval quality.

The user clarified that movie titles are not owned by TMDB and proposed using the title to identify the movie in the generation prompt. Evaluate title-based prompting as the candidate input design; a second catalog or independently re-sourced title is not an adopted prerequisite merely because TMDB also lists that title. Distinguish the factual title identifier from copied provider descriptions. Rights in a title and contractual conditions on API use are separate questions; this proposal does not resolve every API-use condition or create a provider-contact task. The [U.S. Copyright Office's guidance on titles](https://www.copyright.gov/circs/circ33.pdf) and [TMDB's FAQ ownership statement](https://developer.themoviedb.org/docs/faq) support that distinction without selecting an implementation.

Associate generated descriptions with the intended app-owned Movie identity, preserve their generated origin separately from provider metadata, and define quality checks for wrong-movie matches or invented plot details. Generation/model/version changes must support regeneration and reindexing behind the agreed ports and adapters. Exact disambiguation inputs, prompts, model choice, evaluation, and generation cadence remain deferred; this ticket stays open.

### Updated basis — 2026-11-09 (Pacific/Honolulu)

The user confirmed that TMDB allows our use case and disallows training AI with its data. Evaluate direct use of catalog descriptions alongside the generated-description candidate without the prior permission gate. Model selection, corpus selection, and retrieval quality remain undecided; this ticket stays open.

### Human discussion — 2026-11-09 (Pacific/Honolulu), first round

- Semantic search searches only within the acting user's Timeline.
- Start with each movie's available TMDB overview as searchable text, returning one result per app-owned Movie. Supplemental LLM-generated descriptions are a possible later addition; if needed, generation must run as a worker task, never during a live semantic search.
- The user rejected relevance-ordered presentation. Semantic search filters the Timeline while preserving its presentation and existing filters. Matching does not change Timeline membership, saved user activity, or chronological presentation. Carry this filter into the existing bounded-window and direct Timeline ruler access boundary; do not restrict semantic matching to a previously loaded page.
- Indexing/freshness, incomplete coverage and failure behavior, capability contracts, and technology/evaluation deferrals remain to discuss. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), second round

- Accepted sharing each Movie's searchable representation across users, with backend-enforced eligibility limited to the acting user's Timeline and active filters. Matching covers the eligible Timeline beyond the loaded window and preserves direct Timeline ruler navigation.
- Accepted movie embedding creation and updates outside live searches, triggered when searchable catalog text is added or changed. Live search embeds the user's query and searches already indexed movies; future supplemental LLM description generation remains a worker task.
- Accepted deferring the embedding model, vector store, and match threshold to a focused investigation before search implementation. Evaluate storyline-query matching quality, latency, cost, and Neon Postgres suitability; preserve replaceable embedding and retrieval ports. No model/store capability or quality claim is settled here.
- Incomplete coverage, failure behavior, safe index replacement, and final capability/lifecycle boundaries remain to discuss. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), third round

- Accepted omitting movies without overviews or with pending embeddings from semantic matches, with an indication of incomplete search coverage. Ordinary browsing still includes them.
- Rejected requiring a user-visible search-unavailable error when query embedding or retrieval fails. Empty results are acceptable. Log these failures internally for investigation; optional fun or high-level messages may be introduced, without technical architecture/error details. Do not silently disable the active semantic filter and show unfiltered movies. This is feature-specific presentation guidance, not a change to internal failure classification or authorization enforcement.
- Rejected requiring parallel/versioned replacement indexes now. A single atomically updated index is sufficient; search what is available. Revisit more elaborate replacement only if future evidence establishes a need. Model/representation-change mechanics remain for the deferred search investigation and implementation.
- Asked what indexing work needs restart recovery and challenged overengineering. Database-managed index maintenance is the database's responsibility. The agent clarified that the proposed application work meant obtaining movie embeddings when overview text is added/changed and storing the resulting vectors, not maintaining database indexes. Durable job recovery, bounded retries for this preparation, and stale-task protection have not been accepted; a simpler lifecycle deferral is pending human discussion.

### Human discussion — 2026-11-09 (Pacific/Honolulu), final round

- Accepted the revised preparation boundary: obtain movie embeddings outside live search and update the single index atomically. Scheduling, retries, and restart behavior follow implementation; this decision requires no durable queue or recovery framework. Missing embeddings follow the accepted incomplete-coverage behavior. Revisit stronger guarantees only if missing coverage or failed preparation becomes a practical problem.
- All questions in this decision are now settled or explicitly deferred.

## Answer

Resolved through human discussion on 2026-11-09 (Pacific/Honolulu).

### Choices and rationale

**Semantic search filters the user's Timeline.** Accept a storyline query in the user's own words and match only Movies in the acting user's Timeline, combined with its existing filters. Preserve Timeline presentation, chronology, deduplication, and direct bounded access through the Timeline ruler. Matching covers the eligible Timeline beyond the loaded window; apply semantic eligibility before selecting/paginating the displayed Timeline window. Do not return a relevance-ordered replacement list or take an arbitrary global top-k list and then filter it by user. Internal similarity scores may determine matches, but the match threshold and retrieval method remain unselected. This is retrieval over existing movies, separate from generating recommendations, and changes no saved activity or underlying Timeline membership.

**Shared movie representations, user-specific eligibility.** Start with available TMDB overviews, associated with app-owned Movie IDs, and return each matching Movie once. Reuse movie embeddings across users; backend application/domain rules retain authority over Timeline membership and active filters. Keep source provenance and derived data independently refreshable/removable under the existing catalog/provider decisions. No complete provider-catalog ingestion or per-user embedding copy is required. Supplemental LLM descriptions are optional future work, subject to quality checks; if introduced, generate them as worker tasks outside live search.

**Prepare movie embeddings outside live search.** When searchable catalog text is added or changed, preparation obtains the movie embedding and stores it for later searches. Live search embeds the user's query and searches available prepared representations; it does not generate movie descriptions or missing movie embeddings. Use a single atomically updated index and search what is available. Database-managed index maintenance belongs to the database. Application preparation does not require a durable queue, restart-recovery framework, parallel replacement indexes, or elaborate version-management machinery now. Scheduling, retries, restart behavior, and precise atomic-update mechanics follow implementation. Existing request-scoped import processing remains unchanged; its lack of an import worker does not prevent separate off-request movie preparation.

**Incomplete coverage is acceptable.** Movies without overviews or with embeddings still pending are omitted from semantic matches, with an indication that search coverage is incomplete. They remain available in ordinary browsing. The browser does not decide catalog freshness or orchestrate preparation. Exact coverage indicators and optional messaging belong to feature design.

**Search failures can appear as empty results.** Log query-embedding/retrieval failures internally for investigation; user-facing technical errors are not required. Empty results are acceptable, optionally accompanied by fun or high-level messaging. Preserve the query and active filters rather than silently dropping semantic filtering. Keep internal failure classification and observability so operational failures remain distinguishable from successful zero-match searches to maintainers. Existing authorization and content-excluding telemetry boundaries still apply.

The subsequent [operational-controls decision](15-deployment-observability-and-resource-limits.md#answer) governs admission refusals and requires an HTTP status for those cases, with client presentation deferred.

**Use the agreed capability boundaries.** Application operations coordinate preparation and live search through independently configurable embedding, representation persistence, and semantic retrieval ports. Adapters own gateway/vector-store details; domain rules own eligibility decisions. Retrieval identifies matching app-owned Movies for the existing Timeline query rather than redefining Timeline ordering or accepting a client-supplied owner as authority. Exact port signatures and whether one adapter implements multiple capabilities follow implementation. Query and movie embeddings must be compatible for comparison; the chosen technology's model-change/rebuild procedure is deferred, without requiring parallel indexes or seamless migration now. A gateway change alone does not imply a different embedding space.

### What must be fixed now

Keep semantic search a Timeline filter, shared representations separate from user eligibility, TMDB overviews as the starting text, movie preparation outside live search, and one atomically updated index. Accept incomplete coverage and the agreed empty-result failure presentation while logging failures internally. Preserve provenance, independently removable derived data, replaceable capability ports, provider no-training requirements, and the existing Timeline ruler/ownership boundaries.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary / starting direction | Revisit trigger |
| --- | --- | --- |
| Embedding model/gateway, vector storage, retrieval method, and match threshold | Replaceable embedding/retrieval ports; no selected model/store or assumed Neon capability | Focused investigation before search implementation: assess storyline-query matching quality, latency, cost, and Neon Postgres suitability |
| Quality criteria, representative queries, missing-overview coverage, and exact matching semantics | Meaning-based filtering over existing TMDB overviews; no relevance-order presentation | Search-feature specification and evaluation before shipping; later observed poor matches or coverage gaps |
| Preparation scheduling, retry policy, restart behavior, and atomic-update mechanics | Off-request preparation, one atomically updated index, search available data; no required durable queue/recovery framework | Preparation implementation; stronger guarantees only when failed preparation or missing coverage causes a practical problem |
| Model/representation changes, rebuild procedure, and more elaborate replacement | One active index; compatible query/movie representations; derived data remains rebuildable/removable | Before changing embedding space or text representation; parallel replacement only if evidence establishes a need |
| Supplemental LLM descriptions, generation model/prompts, and quality controls | Optional candidate, never part of live search; worker task if adopted | Overview-based evaluation shows a useful coverage/quality benefit sufficient to justify generation |
| Exact query interaction, coverage indicators, optional high-level failure messages, and caching | Existing debounced/abortable fetch; preserve Timeline filters/presentation; empty results acceptable on service failure | Search-feature specification and experience/latency evaluation |
| Execution topology, shared budgets/rate limits, failure telemetry, and cleanup/purge operations | Existing modular backend and operational/provider boundaries; database maintains its indexes | [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md), then concrete integration before release |

The focused technology/quality investigation belongs after this architecture map, alongside the separately deferred search-feature and database work. It is not an unresolved prerequisite to the architecture direction and creates no new research ticket in this map.

### Cost of reversal

Models, representation text, and vector stores remain replaceable behind ports, with the cost of regenerating derived embeddings and possible temporary coverage gaps. Changing the feature from a Timeline filter to global discovery or relevance-ordered results would change eligibility, queries, and client behavior, so that boundary is fixed now. Durable job infrastructure and parallel-index migration carry no demonstrated need here and remain deferred. Provider cleanup must continue to preserve app-owned identities and user activity independently of representations.
