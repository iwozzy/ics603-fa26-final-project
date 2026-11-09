# Establish permitted catalog-data use and provider strategy

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 06

## Question

Given the integration research and proposed data flows, what catalog-provider permissions and constraints must be verified before committing to TMDB-backed AI features, semantic indexing, storage, or future commercial use? Distinguish facts in the official terms from unresolved applicability to this product. Decide which uses need provider clarification or permission, whether the catalog-provider strategy must change, and how attribution, provenance, retention, deletion, and replaceable provider boundaries are carried into the architecture. If external clarification is necessary, create a precise prerequisite task and leave dependent commitments open; do not assume noncommercial access settles AI-related uses or provide a definitive legal interpretation.

## Comments

The November 6 discussion below is historical. The November 9 user confirmation and current Answer supersede its unresolved-use caveats and proposed exclusions.

### Intended use — 2026-11-06 (Pacific/Honolulu)

The user states that the app is not intended for commercial use at this time and likely ever. Treat the current product as noncommercial; reconsider provider licensing if that intent changes. This records product intent and does not settle whether the planned catalog storage, AI, or semantic-indexing workflows are permitted.

### Supporting source verification — 2026-11-06 (Pacific/Honolulu)

Current official terms and documentation were checked in a separate research worktree. Findings distinguish source clauses from unresolved applicability to user-input extraction followed by catalog search, reusable catalog storage, overview embeddings, and model-assisted suggestions. The terms page explicitly states an October 20, 2023 update date, correcting the earlier report's observation that no date was visible in its inspected rendering.

- Report: [TMDB permissions: verified clauses and workflow questions](/private/tmp/ics603-app-architecture-provider-permissions/.scratch/app-architecture/research/provider-permissions.md).
- Exact context pointer: branch `research/app-architecture-provider-permissions`, commit `c5f0ceb50a18d653a8c6feb1c32c004453e9043f`, path `.scratch/app-architecture/research/provider-permissions.md`.
- Initial publication status: committed on the research branch, not pushed. Automatic approval review rejected the push because it could disclose nonpublic architecture details to an unverified external GitHub repository without sufficiently explicit authorization. No retry, PR, or merge was performed. The user subsequently declined publication and directed a local copy into the current branch, as recorded below; no publication approval remains pending.
- No provider contact or permission ruling has been made. The provider strategy and any clarification prerequisite remain human decisions; this ticket stays claimed.

### Human discussion — 2026-11-06 (Pacific/Honolulu), provider direction

- TMDB is the default provider, rather than a provisional provider awaiting external clarification. The user does not want a clarification prerequisite and states that AI will not be used on TMDB data. No provider-contact task is being created. This records the user's strategy and intended data boundary, not a legal conclusion about the terms' applicability.
- The user accepted independently refreshable/removable provider metadata and derived indexes, with provenance/lifecycle boundaries behind adapters, while preserving app-owned identities, Follows, and Watchlist choices. Exact retention and attribution obligations remain inputs to catalog/release planning.
- The user declined pushing the research branch and requested that the report be copied into `docs/wayfinder-plan` at the same relative path. The current local report is [TMDB permissions: verified clauses and workflow questions](../research/provider-permissions.md), copied verbatim from the research commit above. The separate research report's clarification recommendation is supporting evidence, not the adopted prerequisite strategy.
- The meaning of "no AI on TMDB data" still needs reconciliation with the required semantic search over movie descriptions and the proposed model inputs for suggestions. Generating embeddings from provider descriptions would process those descriptions with a model even without model training. No replacement corpus or change to feature scope has been decided; this ticket remains claimed pending that boundary clarification.

### Human discussion — 2026-11-06 (Pacific/Honolulu), final boundary and deferral

- The user accepted leaving the text sources for semantic search and suggestions open for their dedicated decisions, while TMDB remains the lookup/display provider. They also stated that they do not believe calculating a vector from a movie description constitutes AI usage, describing it as semantic search.
- Record that distinction as the user's understanding, not as a settled classification of every embedding implementation or the provider's terms. Vector comparison is arithmetic; generating embeddings with a trained model is model inference. The embedding method, corpus, and applicability of source-use constraints remain explicit questions for the semantic-search ticket. This decision neither approves nor bans TMDB-derived embeddings, and does not remove semantic search from scope.
- No external clarification prerequisite is adopted. The provider strategy and lifecycle boundaries are settled; the remaining source/method decisions have existing owners below.

### Follow-up candidate — 2026-11-06 (Pacific/Honolulu)

The user proposed generating movie descriptions with an LLM and then using those descriptions for semantic search. They clarified that movie titles are not owned by TMDB and can serve as factual identifying inputs. [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md#comments) records this candidate. Do not read the starting exclusion of provider content from LLM prompts as a blanket ban on factual title identifiers or a requirement to obtain a second title source. The generation pipeline is not yet selected; title ownership and conditions on API use remain distinct, and no provider-contact task is adopted.

### User confirmation — 2026-11-09 (Pacific/Honolulu)

The user confirmed that TMDB allows the app's use case and prohibits training AI with TMDB data. Use that confirmation as the basis for current architecture planning. The agent has not independently obtained this confirmation or contacted TMDB. The earlier broad exclusion of TMDB content from model inputs and unresolved permission caveats for the described inference/semantic-search workflows are superseded. No additional provider-clarification task is required.

## Answer

Resolved through human discussion on 2026-11-06; updated by the user's confirmation on 2026-11-09 (Pacific/Honolulu).

### Choices and rationale

- **TMDB is the default provider for the confirmed use case.** The user has confirmed that TMDB allows our use case. Proceed with the planned catalog, inference, and semantic-search architecture on that basis. No provider-contact or alternative-source prerequisite is needed for those uses. This confirmation is user-supplied; it is not a claim of a separate agent verification or blanket permission for unrelated future uses.
- **Do not train AI with TMDB data.** The user's confirmation identifies training as prohibited. Keep training and fine-tuning on TMDB content out of scope, including training reuse by a gateway or model provider handling that content. Runtime inference and generating search embeddings with an existing encoder are distinct from training; no new permission gate is imposed on the confirmed workflows.
- **Choose model inputs and the search corpus on product and technical grounds.** TMDB descriptions and other relevant catalog fields may be considered for semantic search and model inputs within the confirmed use case. The previous restriction excluding copied TMDB descriptions from LLM prompts is removed. Exact retrieval units, input fields, models, quality checks, cost, freshness, and indexing behavior still belong to [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md) and [Define recommendation inputs and trusted-result boundaries](14-recommendation-architecture.md). LLM-generated descriptions remain an optional candidate, not a workaround required for permission.
- **Noncommercial intent remains.** The app is not intended for commercial use now and likely ever. Revisit licensing if the product purpose changes beyond the confirmed use case.
- **Preserve provenance and independent lifecycle behind adapters.** Provider metadata and derived indexes must be independently refreshable, rebuildable, and removable while preserving app-owned Movie/Person identities, Follows, and Watchlist choices. The confirmation does not change those agreed architecture boundaries or resolve detailed storage structures.
- **Carry attribution and data-lifecycle requirements into implementation.** The earlier report's cache, purge, and attribution observations remain inputs to [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md) and release planning. The user confirmation addresses the AI-use question; it does not select a refresh cadence, backup policy, or branding presentation. Do not reopen a generic provider-permission gate while settling those details.
- **Keep the research local as directed.** The [source report](../research/provider-permissions.md) remains in the current worktree at its original relative path. Its research branch must not be pushed. Preserve the dated source observations as history, with the current user confirmation clearly superseding its unresolved-use conclusions and clarification recommendation.

### What must be fixed now

Use TMDB as the default provider. Permit the confirmed runtime inference and semantic-search uses in planning, and exclude AI training on TMDB data. Maintain ports and adapters, app-owned identities, provenance, and independent provider/derived-data lifecycle. Select downstream corpus/model/input details without the earlier blanket exclusion of TMDB content or a mandatory generated-description replacement.

### Deferrals and revisit triggers

| Deferred choice | Boundary or starting assumption | Revisit trigger / owning ticket |
| --- | --- | --- |
| Semantic-search corpus, embedding method, and indexing lifecycle | TMDB data is eligible within the user-confirmed use case; no training on it | Before implementation; [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md) |
| Exact LLM suggestion inputs, grounding, and quality controls | Relevant TMDB fields may be considered for confirmed runtime inference; training reuse is prohibited | When defining recommendation inputs; [Define recommendation inputs and trusted-result boundaries](14-recommendation-architecture.md) |
| Provider/model training-reuse settings and data handling | Any service receiving TMDB data must respect the no-training restriction | Before integration; [Identify the LLM Gateway and its documented capabilities](18-identify-llm-gateway.md) and the selected model/embedding adapters |
| Persistence, refresh, expiry, purge, and derived-artifact cleanup | Provenance and independently removable provider/derived data; preserve user choices | Before storage/refresh contracts; [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md) |
| Attribution presentation and operational cleanup/backup handling | Carry applicable source requirements into release planning | Before deployment; [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md) |
| Different provider, agreement, or commercial purpose | TMDB default for the confirmed noncommercial use case | Product purpose, provider terms, availability, or intended data use changes beyond that use case |

### Cost of reversal and evidence

Provider IDs, payloads, or source-retention assumptions must not define domain ownership or leak into application/client contracts. Provenance is needed to remove or rebuild source-dependent artifacts selectively. Those boundaries are fixed; exact adapters, corpora, models, and refresh cadences remain replaceable, with reconciliation or reindexing costs where appropriate.

The current permission basis is the user's November 9 confirmation recorded above. The [local report](../research/provider-permissions.md) remains a dated source snapshot, with its prior permission uncertainty superseded for this use case. No additional prerequisite ticket is created.
