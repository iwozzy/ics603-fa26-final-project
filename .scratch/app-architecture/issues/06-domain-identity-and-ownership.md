# Define domain identity and user-data ownership

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 04

## Question

Which core concepts and ownership boundaries must be stable before choosing schemas and API contracts? Clarify people and their cast/crew credits, movies and potential future shows, provider identities versus application identities, follows, seen status, watch list, imported titles, matched records, and timeline membership. Stress-test one movie from several followed people, an imported movie with no followed people, duplicate/provider-conflicting records, and a future provider change. Decide the durable identity and ownership rules now; defer detailed schemas where possible and record resolved vocabulary in the glossary.

## Context

Apply [Set the architecture's quality targets and decision priorities](04-architecture-quality-targets.md#answer). Define ownership for the public demo user and future private personal users; distinguish shared catalog records from each user's movie activity. Use the resolved **Demo user** term in the root glossary.

## Comments

### Human discussion — 2026-11-06 (Pacific/Honolulu), first round

- Use application-owned IDs for movies and people, with mappings to provider IDs. The user explicitly deferred detailed data structures to a later discussion.
- A person has one identity across cast and crew roles. Initially, following a person includes all their movie credits; role-specific following/filtering can wait for a concrete need.
- Seen status and intention to watch are independent, including repeat viewing. The user suggested that a single lightweight Watchlist record linking User and Movie could hold seen status and watch status; separate concepts do not require separate storage records. This is a possible data structure, not a finalized schema.
- The broader record's name versus the watch-list subset, timeline membership, import confirmation, and identity-conflict behavior still need discussion. This ticket remains claimed.

### Human discussion — 2026-11-06 (Pacific/Honolulu), second round

- The user prefers **Watchlist** as the broader concept covering saved movies with both seen status and watch status. This supersedes the agent's proposed distinction between Movie tracking and an intended-viewing-only Watch list. The possible lightweight User–Movie record remains a structure to discuss later, not a finalized schema.
- The Timeline contains unique movies from all followed people's credits and the user's Watchlist. The user accepted one entry per movie regardless of how many follows contribute it, inclusion of explicitly saved movies with no followed people, retention of saved movies regardless of their two statuses, and removal from the Timeline only when no contributing follow or Watchlist entry remains.
- The user accepted confirming matched movies and choosing their statuses without inferring seen status from DVD ownership. Reimporting an existing movie updates its existing user relationship rather than making another copy.
- Before user review, titles extracted from notes or photos must be validated against the provider. Only provider-validated movies are presented to the user. Ambiguous validated alternatives and zero-match handling need clarification; provider validation alone was not accepted as a rule for merging conflicting existing app identities.

### Human discussion — 2026-11-06 (Pacific/Honolulu), third round

- The user accepted ambiguous provider-validated candidates. Initial TMDB matching searches by movie title only; multiple plausible results are expected. Rank those results and present 1–3 most likely candidate movies for the user to choose from. Titles without validated matches are excluded from the selectable movie list. Exact ranking rules, confidence thresholds, UI, and interaction are deferred; the architecture must retain the distinction between an extracted title and candidate movies.
- The user accepted preserving existing app identities and user activity when providers disagree, with detailed reconciliation and merge rules deferred to the catalog decision. They emphasized separation of concerns and applying ports and adapters throughout.
- The proposed deferral of show/season/episode structures, with entity-type-aware provider references, has not yet received an answer. This is the remaining question before resolution.

### Human discussion — 2026-11-06 (Pacific/Honolulu), final round

- The user accepted deferring show, season, and episode structures until shows become a delivery requirement, while ensuring provider references distinguish movies, people, and shows. All questions in this decision are now settled or explicitly deferred.

## Answer

Resolved through human discussion on 2026-11-06 (Pacific/Honolulu).

### Choices and rationale

- **Application-owned identities.** Movies and people have stable application IDs, mapped to provider IDs. A title or name alone does not establish identity. Provider references must distinguish the provider and entity type so, for example, a provider's movie and show IDs cannot be confused. Adding or replacing a provider should preserve established app identities and user activity. Exact identifier formats and mapping structures remain deferred.
- **One Person across roles, with Credits describing participation.** An individual retains one identity across cast and crew work. A Credit relates that Person to a Movie and retains their role. A Follow belongs to a user and initially includes all that Person's movie credits. This preserves role information without requiring role-specific following in the first version.
- **Shared catalog, user-owned activity.** Movies, people, and credits belong to the shared catalog; Follows and the Watchlist belong to a user. Apply the public Demo user and future private-personal-user boundary from [Set the architecture's quality targets and decision priorities](04-architecture-quality-targets.md#answer). Multiple visitors to the demo share its confirmed activity; that does not make their raw extraction inputs shared catalog data. Authentication and demo-to-personal transition remain separate decisions.
- **Watchlist covers all explicitly saved movies.** The user's chosen term is Watchlist, including seen movies, intended viewing, and repeat viewing. A Watchlist entry associates a user with a Movie and captures independent seen status and watch status. Changing either status does not automatically change the other or remove the entry. One lightweight user–movie record may capture both; this resolution fixes the meaning rather than the physical schema.
- **Timeline is the deduplicated combination of follows and Watchlist.** Include movies from followed people's credits and explicitly saved Watchlist movies, with each Movie appearing once. Several contributing follows do not create several Timeline items. An imported movie appears without any followed people when saved to the Watchlist. Removing a Follow or Watchlist entry removes the movie from the Timeline only if no other contribution remains. A followed movie need not have a Watchlist entry merely to appear in the Timeline.
- **Provider validation precedes import review.** Note/photo extraction produces extracted titles used to search the provider; initial TMDB matching uses movie titles only. Only provider-validated candidate movies are presented for selection. When several candidates are plausible, rank them and present 1–3 most likely matches with identifying information. The user confirms the intended movie and its statuses; DVD ownership does not establish seen status. Confirmed imports update the existing user–movie relationship rather than creating duplicates. Titles with no validated match are excluded from the selectable movie list; exact feedback and recovery interaction remain deferred.
- **Validation, confirmation, and reconciliation have separate responsibilities.** Provider validation establishes a provider record as a candidate, user confirmation chooses the intended movie, and catalog reconciliation decides whether provider records represent an established app identity. Provider disagreement must not silently replace established identities or discard user activity. Keep provider-facing details behind adapters and application/domain contracts independent of them. The user explicitly emphasized ports and adapters throughout; detailed interfaces and reconciliation rules belong to their owning tickets.
- **Movies now, television structures later.** Keep provider references aware of entity type now, but defer show/season/episode structures and tracking semantics until shows are scheduled. A movie-only first product does not justify treating every provider ID as a movie ID.

### What must be fixed now

The identity and ownership boundaries, Person/Credit/Follow distinctions, broad Watchlist meaning, independent statuses, deduplicated Timeline membership, and provider-validation-before-review sequence must inform later schemas and contracts. Keep provider records, extracted title strings, candidate movies, and user-confirmed selections distinct. Preserve separation of concerns through ports and adapters rather than allowing provider payloads or UI choices to define the domain model.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary or starting assumption | Revisit trigger / owning ticket |
| --- | --- | --- |
| Detailed movie/person/credit, provider-mapping, and Watchlist structures; identifier formats; reconciliation and merge mechanics | Stable app identities, provider/entity-type-aware references, independent statuses, and preservation of user activity | Before committing catalog persistence structures; [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md) |
| Concrete ports, adapters, and module dependencies | Separate provider validation, user confirmation, reconciliation, persistence, and presentation responsibilities | Before defining backend/frontend interfaces; [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md) and [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md) |
| Candidate-ranking rules, confidence thresholds, review UI, zero-match feedback, and repeat-import update interaction | Provider-validated candidates only; ranked 1–3 alternatives when ambiguous; user-confirmed statuses; one user relationship per movie | When specifying import review and lifecycle behavior; [Define import review and background-work lifecycles](11-imports-and-background-work.md); extraction/model evaluation remains outside this map |
| Authentication, authorization mechanics, and demo-to-personal migration | Activity has an explicit user owner even when the Demo user is automatically selected | Before defining identity/session contracts; [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md) |
| Role-specific following or filtering | Retain Credit roles; initially follow the whole Person | A concrete product need for following/filtering a subset of that Person's work |
| Show, season, and episode structures | Provider identity includes entity-type context; current tracking concerns movies | Shows become a delivery requirement; the catalog decision must preserve the identity boundary without designing television tracking now |

### Cost of reversal

Using provider IDs as the app's durable identity, collapsing a Person into separate role identities, or saving activity without a user owner would make later provider changes, role changes, and personal accounts expensive to introduce. Treating Watchlist as an unseen-only queue would also encode the wrong product meaning. Those boundaries are decided now. Exact table shapes, library choices, ranking algorithms, and review UI remain more replaceable when kept behind the agreed boundaries; reversing an established identity model after data accumulates would require careful reconciliation and migration.

Resolved domain vocabulary is recorded in [GLOSSARY.md](../../../GLOSSARY.md). The remaining sharp questions belong to the existing dependent tickets; no additional prerequisite investigation or prototype is identified by this resolution.
