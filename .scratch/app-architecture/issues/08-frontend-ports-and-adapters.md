# Define shared frontend boundaries and platform adapters

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 05, 07

## Question

Given the client-platform direction and backend boundaries, what frontend domain/application logic, state, contracts, and presentation can be shared, and which browser/iOS/Android concerns need adapters? Decide how validation, API access, session storage, camera/photo access, navigation, and platform lifecycle concerns relate to ports and adapters. Establish a package/dependency direction that supports future native apps without implementing them now or assuming Python Pydantic models execute on every client.

## Context

Apply [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md#answer) when locating shared client responsibilities. Backend domain decisions and workflow coordination retain their agreed owners; this ticket defines frontend responsibilities and adapters without coupling clients to backend libraries or provider SDKs.

Apply [Choose the web and native client platform direction](05-choose-client-platform-direction.md#answer). Settle logical dependency boundaries, state ownership, and platform-adapter responsibilities under that direction. Concrete libraries, workspace packages, and detailed interaction behavior may be explicitly deferred. Trace browser and native lifecycle concerns without making native delivery a prerequisite for the web app.

Apply [Choose identity and session boundaries for web and native clients](09-identity-sessions-and-client-security.md#answer) for automatic Demo selection initially, a shared personal identity across devices later, and platform-specific credential handling behind adapters. Clear private caches/review state when signing out or switching users, prevent late operations from being applied to another owner, and distinguish personal-session failure from an explicit return to Demo. Defer exact auth/storage libraries and session formats while preserving those boundaries.

## Comments

### Human discussion — 2026-11-09 (Pacific/Honolulu), first round

- Accepted shared client domain rules and workflow coordination in ordinary TypeScript independent of React, Expo, browser APIs, and native APIs. Client domain rules make client-side domain decisions; client application code coordinates through ports. React components/hooks connect presentation to that core, while simple screen-only state may stay in components.
- Accepted distinct ownership/lifetimes for backend-data caches, temporary workflow state, and screen-only state. Timeline and Watchlist data are cached backend state; extraction review is temporary workflow state; an open menu is screen state. Scope private data to its user and temporary work to its initiating workflow. Exact cache keys and state libraries remain deferred.
- Accepted client validation for interaction with backend authority for saved data and domain decisions. The backend validates every operation and enforces ownership/domain rules; client input checks provide feedback. Share useful TypeScript rules across clients without requiring a parallel TypeScript implementation of every Python backend rule.
- Platform adapters, navigation, interruption handling, and remaining implementation deferrals still need discussion. The ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), second round

- Accepted focused client ports for backend access, credential handling, photo/camera input, and platform lifecycle events, with adapters selected at startup. Transport details, runtime response validation, device APIs, and external errors stay at those boundaries. Add ports for actual workflow needs and allow capabilities to be unavailable on a platform.
- Accepted screens/navigation in presentation, sharing compatible components while allowing platform-specific implementations. Route formats, navigation libraries, and React hooks stay outside the shared core; workflows receive ordinary inputs such as Movie IDs. Layout and navigation behavior follow UI specification.
- Did not accept a fixed policy for search cancellation or obsolete result ordering. The user explicitly deferred that behavior until the search feature's interaction and feel are specified, potentially through a prototype. This ticket must not prescribe search-as-you-type, latest-request-wins, or cancellation semantics. Existing user/workflow isolation requirements from the identity and state-ownership decisions still apply; reload/resume and temporary-input persistence remain with the import-lifecycle decision.
- The question about deferring state/cache libraries, navigation libraries, client validation tooling, and exact workspace packages has not yet been answered. That is the remaining question before resolution; the ticket remains claimed.

### Human discussion — 2026-11-09 (Pacific/Honolulu), final round

- Accepted deferring state/cache libraries, navigation libraries, client validation tooling, and exact workspace packages. Fix responsibilities and dependency direction now; select concrete libraries and packages before implementing the relevant workflows.
- All questions in this decision are now settled or explicitly deferred, including search cancellation/result ordering. This resolution does not adopt the proposed obsolete-result policy.

## Answer

Resolved through human discussion on 2026-11-09 (Pacific/Honolulu).

### Choices and rationale

**Shared TypeScript core with explicit dependencies.** Keep useful client domain rules and workflow coordination in ordinary TypeScript independent of React, Expo, browser APIs, and native APIs. Client domain rules make client-side domain decisions; application code coordinates through ports. React components/hooks connect presentation to this core, and simple screen-only state may stay in components. Preserve the resolved Expo/React Native for Web direction and share compatible presentation without requiring identical screens.

| Responsibility | Dependency direction |
| --- | --- |
| Client domain rules | Ordinary TypeScript, independent of UI frameworks and platform APIs |
| Client application workflows and ports | Client domain and client-owned contracts; no concrete platform/transport adapter dependencies |
| Presentation, screens, navigation, and connecting hooks | Invoke client application workflows; own presentation behavior and screen-only state |
| Backend-access, credential, media, and lifecycle adapters | Implement focused client ports; isolate transport/platform APIs, runtime response validation, and external-error translation |
| Client startup/configuration | Select and compose concrete adapters for the target platform |

These are logical responsibilities, not required directories, packages, or a custom cross-platform framework. Introduce ports for actual workflow needs; a capability may be unavailable on a platform. Keep route formats, navigation libraries, and React hooks outside the shared core; workflows receive ordinary inputs such as Movie IDs. Allow platform-specific screens/navigation and share compatible components where useful.

**State has distinct owners and lifetimes.** Timeline and Watchlist data are cached backend state. Extraction review is temporary workflow state. An open menu is screen-only state. Scope private data to its user and temporary work to its initiating workflow, preserving the existing account-switching and temporary-input privacy boundaries. This distinction does not select a global state store, persistence mechanism, cache-key format, or restart-recovery guarantee.

**Backend authority, client interaction validation.** Client checks support immediate feedback, but the backend validates every operation and remains authoritative for saved data, ownership, and backend domain decisions. Share TypeScript rules across clients when useful without requiring a duplicate of every Python backend rule. Runtime response validation belongs at the backend-access adapter boundary. API wire contracts and their TypeScript representation/generation remain with [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md); this decision does not assume Python Pydantic models execute on clients.

**Platform capabilities stay behind adapters.** Backend access, credential handling, photo/camera input, and lifecycle events use focused ports with adapters selected at startup. Keep backend/provider SDKs and secrets outside shared client logic. Credential details follow the resolved identity/session boundary; media and lifecycle adapters support the workflows selected later without promising durable work merely because a device API exists.

**Remaining search behavior stays open.** The original discussion deferred cancellation and obsolete-result ordering. The user's later direction in [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md#answer) selects debounced, abortable fetch over HTTPS/HTTP/2 and excludes WebSockets for now. Exact UI triggers, debounce interval, obsolete-result presentation, and query caching still follow search-feature specification, potentially with a prototype; no latest-request-wins policy is selected here. Separation of search workflow state, backend access, and presentation preserves this flexibility, with existing user/workflow isolation still required. Reload/resume guarantees and temporary-input persistence remain with [Define import review and background-work lifecycles](11-imports-and-background-work.md).

### What must be fixed now

Preserve the shared framework-independent TypeScript core, domain/application responsibility split, logical dependency direction, explicit platform adapters/composition, distinct state ownership, backend authority, and platform-appropriate presentation. Carry existing account isolation and temporary-work privacy requirements into client state and integration design. Keep detailed search interaction and concrete library choices replaceable within these boundaries.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary / starting direction | Revisit trigger / owner |
| --- | --- | --- |
| State/cache libraries, navigation libraries, client validation tooling, and exact modules/workspace packages | Logical responsibilities above; use existing compatible libraries and extract packages when actual sharing warrants them | Before implementing the relevant client workflows/dependencies |
| Wire contracts, TypeScript representation/generation, transport, and client-visible error details | Backend-access adapter exposes client-owned contracts and validates responses | [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md) before transport implementation |
| Search UI triggers, debounce interval, obsolete-result presentation, and query caching | Debounced/abortable fetch per the later transport direction; search workflow state, presentation, and backend access remain separate; no latest-request-wins policy or query cache is required | Search-feature specification and experience/latency evaluation, potentially using a prototype; carry forward [Choose catalog persistence and provider-refresh boundaries](12-catalog-storage-and-refresh.md#answer) |
| Detailed layouts, screen navigation, and route formats | Presentation-owned navigation with shared compatible UI and platform-specific implementations | UI specification and before implementing the relevant screens |
| Exact interruption/expiry handling and future stronger recovery/background completion | Apply [Define import review and background-work lifecycles](11-imports-and-background-work.md#answer): initial client-held temporary review, cleanup on interaction end, no guaranteed full-reload/server-restart recovery, no progress channel | Import implementation for exact lifecycle handling; concrete need for stronger recovery/continuation before introducing persistent workflow state |
| Concrete credential/media/lifecycle libraries and native implementations | Focused capability adapters; web first, established libraries preferred | Before using the capability on web; native-specific implementation/validation when native delivery is scheduled |

### Cost of reversal

State libraries, individual adapters, and package layout remain replaceable when their dependencies stay within the agreed boundaries. Embedding browser/native APIs or routing hooks in shared core logic, mixing temporary inputs with shared cached catalog/user activity, or making clients authoritative for saved-data rules would make native sharing and later behavior changes more expensive. The selected rendering family remains the costly platform choice already resolved separately. No additional prerequisite research or prototype is needed to settle these boundaries; search behavior is explicitly deferred rather than silently assumed.
