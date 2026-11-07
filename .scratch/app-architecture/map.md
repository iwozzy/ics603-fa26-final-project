# Architecture for a shared web and native movie-discovery app

Labels: wayfinder:map
Status: open

## Destination

Establish a coherent architecture direction for the whole app in [the proposal](../../docs/proposal/proposal.md) and a future shared web/iOS/Android product. Identify the expensive decisions to make before implementation, reversible starting choices, and explicit deferrals with revisit triggers; a complete implementation specification is not required.

## Notes

- This is a planning effort. Produce decisions and supporting investigations; application implementation and native app delivery are outside this map.
- The app is intended to be a small, deployed, multiuser product maintained beyond the course.
- Primary future concern: web, native iPhone, and native Android clients should share one repository and as much code as practical, without unnecessary initial overhead. What “native” requires and the actual sharing boundaries remain decisions.
- Use the proposal's outside-V1 features as architectural stress tests, not delivery commitments: mobile access, OAuth/email authentication, notifications, viewing availability, richer discovery, people suggestions, and shows. Digital-collection screenshots are another possible future input.
- User's strong starting preferences, revisable with a stated reason: ports and adapters in backend and frontend; Pydantic models for boundary validation; Pydantic AI for LLM Gateway access; Pydantic Logfire; Neon Postgres; TMDB with room for other movie-data providers; Docker deployments; async operation. Python >=3.13 is existing project metadata, not an irreversible requirement.
- AI photo extraction uses the LLM Gateway; model selection follows a separate quality investigation. Semantic search is required, with technologies undecided.
- User prefers WebSockets where possible to reduce overhead. Treat the proposed performance benefit as a hypothesis to investigate before committing transport contracts. Clarify async I/O, background work, and durable execution separately.
- The proposal's detailed titles-only note-extraction increment and gpt-4.1-nano choice are historical proposal context, not proof of existing implementation or final architectural decisions. The current checkout contains no app source.
- Every decision resolution should state the choice and rationale, cost of reversal, what must be fixed now, and what can wait with a trigger. Existing preferences are inputs, not resolved decision tickets.
- A decision ticket may resolve as an explicit deferral when the human agrees that implementation can proceed safely: record the assumption or replaceable default, the boundary that preserves reversibility, and the event that requires revisiting it. Ticket coverage does not mean every technology must be selected now.
- Consult wayfinder, grilling, and domain-modeling each decision session; research and prototype tickets also use their respective skills. Update the root glossary only when domain terms are actually resolved; create ADRs sparingly for consequential trade-offs.
- Local tracker: [conventions](../../docs/agents/issue-tracker.md). Child tickets live in issues/. Query their Type, Status, and Blocked by metadata; the frontier is open, unblocked, unclaimed tickets ordered by number. Research claims are saved before investigation.
- Research assets belong on separate research/app-architecture-* branches, pushed without a PR or merge. Each research ticket links its exact context pointer. Source findings do not settle human architecture choices.
- Scope and starting preferences were agreed in the wayfinder conversation on 2026-11-06 (Pacific/Honolulu).

## Decisions so far

<!-- One named link and a short gist per resolved decision. Detail belongs in the ticket. -->

- [Research approaches to sharing web, iOS, and Android code](issues/01-research-shared-mobile-approaches.md): viable sharing approaches depend on the meaning of native; the client platform remains a human decision.
- [Research HTTP and WebSocket transport trade-offs](issues/02-research-client-transports.md): connection overhead alone does not establish a WebSocket advantage; transport selection remains open.
- [Research feasibility of the proposed backend integrations](issues/03-research-backend-integrations.md): plausible integration paths exist, with gateway capability and catalog-data permission prerequisites still unresolved.

## Not yet specified

- Platform-specific behavior and migration details may emerge once “native,” code-sharing expectations, and the initial platform sequence are settled.
- Additional provider, retrieval, or workflow investigations may become necessary when the relevant human decisions make their evidence requirements precise.
- The exact consequences of the quality targets for operational thresholds, deployment sizing, and failure recovery remain unclear until that discussion.
- Cross-cutting gaps exposed while tracing complete workflows should become new decision tickets when they can be stated precisely.

## Out of scope

- Building the app, production deployment, or delivering native apps during this map.
- A complete endpoint catalog, physical schema, UI specification, or implementation backlog unless a small detail is necessary to settle a costly architectural boundary.
- Selecting/tuning extraction or embedding models, building a benchmark, and running photo-quality experiments; this map identifies the boundaries and evidence those later efforts need.
- Implementing every outside-V1 feature or designing for an unagreed large-scale commercial workload.
