# Set the architecture's quality targets and decision priorities

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)

## Question

What operational envelope and priorities should guide costly architecture decisions for a small maintained multiuser app? Establish the expected audience, deployment/operating budget, latency and availability expectations, privacy/retention needs, offline expectations, and web/native delivery sequence through human discussion. For each significant unknown, determine whether it needs an answer now or a revisit trigger. Turn these priorities into a consistent test for deciding now versus deferring, without choosing the whole stack.

## Comments

### Human discussion — 2026-11-06 (Pacific/Honolulu)

The user accepted the first round of recommendations, with these clarifications:

- Start with a single user automatically assumed when the web app opens. Implement with multiple users and future authentication in mind from the start. The small invited-group envelope remains a future starting point rather than a requirement to expose multiple accounts immediately.
- Accept a provisional $25/month total operating ceiling, explicit paid-AI usage limits, solo maintenance, and occasional maintenance downtime.
- Aim for ordinary browsing reads within roughly one second under normal conditions; longer imports and AI operations need visible progress. Preserve confirmed user changes through restarts. AI failures should not prevent saved browsing; previously fetched catalog information should remain useful during provider outages.
- Keep an application copy of provider data so repeated equivalent queries do not always fetch it again. Refresh on a cadence appropriate to the data type. The data flow, stored representation, permitted use, and refresh strategy belong to [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md), subject to [Establish permitted catalog-data use and provider strategy](17-provider-permissions-and-strategy.md).
- Personal movie activity is private by default; no social features are currently planned. Uploaded notes and photos are solely title-extraction inputs, discarded after the user interaction ends. The user accepted retaining confirmed selections, excluding raw personal inputs from logs, and deleting personal records on account deletion with backup expiry handled separately. Interaction-end and abandonment cleanup semantics belong to [Define import review and background-work lifecycles](11-imports-and-background-work.md).
- Assume an internet connection initially; preserve in-progress input through ordinary interruptions where practical. Offline browsing, editing, and synchronization are deferred until a concrete use case requires them.
- Deliver the deployed web app before iOS and Android. Prioritize protection of saved user data, useful web workflows, and manageable operations; preserve sharing boundaries without making native delivery or maximum sharing a prerequisite for the web product.

The agent asked whether access to the default single user should be restricted. The user explicitly declined: the initial user is a demo user intended for public availability. Authentication and restrictions for personal users come later. This clarification supersedes the first round's assumption that the initial user's movie activity is private.

## Answer

Resolved through human discussion on 2026-11-06 (Pacific/Honolulu).

### Choices and rationale

- **Public demo first, multiple users by design.** Opening the initial web app automatically selects one shared demo user, with no access restriction required. Visitors share that demo user's saved movie activity. Model personal activity as belonging to a user from the start so later authenticated users can have separate private data. The public demo is an explicit exception to private-by-default personal activity; no social features are planned.
- **Small operating envelope.** Start with one demo identity and later a small invited group, initially tens of regular users with occasional simultaneous use. One demo identity does not imply only one visitor at a time or a limit on public traffic. Use a provisional $25/month total operating ceiling, explicit paid-AI usage limits, solo maintenance, and occasional maintenance downtime. Public availability does not waive resource limits; their implementation belongs to the operational-controls decision.
- **Responsive browsing and recoverable work.** Aim for ordinary browsing reads within roughly one second under normal conditions, as a design target rather than a measured guarantee. Imports and AI operations may take longer with visible progress. Confirmed saved changes survive server restarts. AI failure should not prevent browsing saved data, and provider outages should allow use of previously fetched catalog information. Exact availability percentages and recovery thresholds remain deferred.
- **Application-held catalog data.** Keep a copy of provider data so repeated equivalent queries do not always require another provider request. Refresh on a cadence appropriate to each data type. The catalog decision must trace provider-to-app data flow, persistence, reuse, and refresh; permitted storage/use remains a prerequisite, and exact cadences are not selected here.
- **Temporary extraction inputs.** Uploaded notes and photos are used only to extract movie titles and are discarded when the user interaction ends. Retain confirmed movie selections rather than the original inputs. Exclude raw personal inputs from logs; personal-record deletion and backup expiry must be supported for future personal users. The public demo identity does not make raw uploads shared catalog or demo content. Completion, cancellation, abandonment, and cleanup timing remain questions for the import-lifecycle decision.
- **Online use initially.** Assume an internet connection. Preserve in-progress input through ordinary connection interruptions where practical; defer offline browsing, editing, and synchronization until a concrete use case requires them.
- **Web before native.** Deliver the deployed web app first, then iOS and Android. Prioritize protection of saved user data, useful web workflows, and manageable operations. Preserve clear sharing boundaries without making native delivery or maximum code sharing a prerequisite for the web product.

### What must be fixed now

- Keep user ownership explicit from the first version; selecting the demo user automatically must not erase the ownership boundary needed by future personal users.
- Distinguish publicly shared demo activity from future private personal activity. Authentication technology and the fate of demo data when personal accounts arrive remain open.
- Carry durable confirmed changes, temporary extraction inputs, catalog reuse/refresh, failure isolation, and paid-usage controls into the dependent architecture decisions.
- Treat the initial budget, audience, and latency target as constraints to validate, not proof that a particular deployment or provider can satisfy them.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary or starting assumption | Revisit trigger / owning ticket |
| --- | --- | --- |
| Authentication, authorization mechanics, and demo-to-personal transition | Public demo initially; explicit user ownership from the start | Before introducing personal accounts or private data; [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md), informed by [Define domain identity and user-data ownership](06-domain-identity-and-ownership.md) |
| Provider data representation, query reuse, refresh cadences, and permissions | Application-held catalog copy with freshness varying by data type, subject to permitted use | Before committing storage/refresh behavior; [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md) and [Establish permitted catalog-data use and provider strategy](17-provider-permissions-and-strategy.md) |
| Exact interaction-end and abandoned-input cleanup rules | Extraction inputs remain temporary; confirmed selections may persist | Before designing imports and background processing; [Define import review and background-work lifecycles](11-imports-and-background-work.md) |
| Capacity, availability, recovery, hosting, and enforcement details | Small initial audience, $25/month ceiling, rough one-second browsing target, restart-persistent saved changes | While choosing deployment and limits, then when usage, cost, or observed failures exceed assumptions; [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md) |
| Offline support | Online workflows, with interruption recovery where practical | A concrete offline workflow becomes a product requirement |
| Native delivery and exact sharing strategy | Web first; retain sharing boundaries | [Choose the web and native client platform direction](05-choose-client-platform-direction.md) settles the direction; native implementation waits for a delivery commitment |

### Cost of reversal and decision test

Audience estimates, the budget, rough latency targets, and delivery timing are inexpensive to revise while the app is small. Adding private users becomes costly if data was saved without ownership; catalog/provider coupling and raw-input retention become costly to undo after data accumulates. Offline writes and synchronization can also become a substantial new architecture effort, so the online assumption must remain explicit.

Decide now when postponement would embed the wrong ownership, durable-data, retention, provider, or client boundary, or make the accepted operating envelope implausible. Otherwise use a replaceable starting choice, name the boundary that keeps replacement practical, and record the event that requires revisiting it. Later tickets select mechanisms under these constraints; this resolution does not select the whole stack.
