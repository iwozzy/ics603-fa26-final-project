# Choose identity and session boundaries for web and native clients

Type: grilling
Labels: wayfinder:grilling
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 04, 05, 06

## Question

What identity/session strategy serves V1 and allows later real accounts across web, iOS, and Android? Determine anonymous versus registered ownership, account migration/linking needs, browser and native credential storage, restart persistence, authorization enforcement, and deletion expectations. Separate long-term ownership/authentication boundaries from a replaceable provider and UI. Resolve enough to prevent expensive data ownership and client-contract changes; do not implement authentication.

## Context

Apply [Set the architecture's quality targets and decision priorities](04-architecture-quality-targets.md#answer): the initial automatically selected user is a public demo user and requires no access restriction. Do not reopen that as a private single-user deployment. Decide how future personal users are isolated, what happens to demo activity when accounts are introduced, and how demo versus personal access is selected.

Apply [Define domain identity and user-data ownership](06-domain-identity-and-ownership.md#answer) for the boundary between the shared catalog and user-owned Follows and Watchlist. Establish session and authorization behavior without making provider identities the owners of saved activity or treating Watchlist as an unseen-only queue.

## Comments

### Human discussion — 2026-11-06 (Pacific/Honolulu), first round

- New personal users start with an empty Watchlist and no Follows. Existing demo activity remains with the Demo user; no automatic claiming or copying on signup. An explicit copy feature is deferred until a concrete need.
- The same personal user accesses the same saved activity across web, iPhone, and Android. Device sessions do not create separate owners of movie activity.
- Authentication implementation remains later than the initial public demo, but the user selected username and password as the first authentication adapter. Additional authentication features/methods will be added in the future. Keep credentials and session mechanisms separate from the stable application-owned user identity; no authentication library or storage mechanism has been selected yet.

### Human discussion — 2026-11-06 (Pacific/Honolulu), second round

- The backend determines the acting user and enforces ownership for private data; a client-supplied user ID alone cannot authorize access.
- The user accepted persistent, revocable sessions for future personal accounts, subject to expiry/logout/revocation, including continuity across ordinary client and server restarts. They emphasized deferring specifics until implementation unless changing them later would be costly. Browser cookie and native protected-storage mechanisms were proposed as starting directions, not finalized library, token-format, storage-schema, or timeout choices.
- The user clarified that the initial demo always loads the Demo user and has no signed-out state. Do not add an authenticated demo login session merely to introduce future personal-user sessions.
- The agent clarified that privacy for temporary import work is separate from authentication: sharing the Demo user's confirmed activity does not authorize one visitor to read another's inputs/results. The import-lifecycle decision owns the minimum work-access mechanism needed, without assuming a login session or anonymous personal account.
- Personal-session expiry versus explicit return to demo mode remains to be confirmed; the user's demo-stage clarification did not answer that future behavior.

### Human discussion — 2026-11-06 (Pacific/Honolulu), final round

- The user accepted that, once personal accounts exist, an expired personal session requests sign-in rather than silently redirecting subsequent edits to the Demo user. Returning to demo mode is explicit; signing out or switching users clears private cached data and review state.
- The user emphasized that the Demo user is a user like any other and there must never be leakage across user accounts. Initially everyone acts as the Demo user automatically; this does not require a credential exchange, an authenticated session mechanism, or a signed-out UI at the demo stage.
- The costly boundaries are fixed now: stable app-owned user identity independent of credentials/devices, backend-enforced ownership, durable revocable personal sessions, and platform-specific credential handling behind adapters. Session libraries, storage schemas, token formats, cookie/header details, and timeout values remain implementation choices rather than frozen contracts.

## Answer

Resolved through human discussion on 2026-11-06 (Pacific/Honolulu).

### Choices and rationale

- **An ordinary Demo user, selected automatically at first.** The Demo user owns Follows and a Watchlist through the same ownership model as any other user. All initial visitors act as that one shared user; there is no login gate or signed-out state to introduce in the initial demo. The backend may resolve that configured user directly without implementing authenticated sessions or creating an anonymous personal user per visitor. Public demo activity is an intentional sharing of one owner's activity, not a cross-account authorization exception.
- **Personal accounts remain separate owners.** A new Personal user starts with an empty Watchlist and no Follows. Signing up does not claim or copy demo activity. The same app-owned user identity owns that personal activity across web, iPhone, Android, and future authentication methods; credentials, usernames, devices, and sessions do not become the durable ownership key. An explicit demo-copy feature remains deferred until there is a concrete need.
- **Username and password first, additional authentication later.** The first authentication adapter for personal accounts will verify username/password credentials and resolve the app-owned user identity. Authentication implementation follows the initial public demo. Keep credential verification and session handling separate from domain ownership and application authorization, so additional methods can be introduced without migrating movie activity to a new owner. This selects a method, not an auth library, registration/recovery flow, or custom cryptographic implementation.
- **Backend-enforced account isolation.** The backend determines the acting user through the current trusted identity-resolution mechanism and checks ownership for reads and changes involving private data. Supplying a different user ID from a client is not proof of access. Apply that rule regardless of API transport, frontend platform, or authentication adapter. Ports and adapters carry identity into application operations; provider-specific credentials and transport details do not define the domain's user identity or authorization rules.
- **Durable, revocable personal sessions.** Future personal sessions should survive ordinary client and server restarts while valid, and support expiry, logout, and revocation under backend control. Keep session persistence out of ephemeral server-process memory as the sole source of truth. Browser and native clients need different credential-handling adapters: protected cookies with appropriate browser request protections and OS-protected native storage are starting directions, not a finalized token or library contract. Credential verification, session establishment, and saved-activity ownership remain separate responsibilities.
- **No implicit switch of account after failure.** Once personal accounts exist, an expired or invalid personal session requires sign-in rather than silently applying work as the Demo user. A user intentionally chooses a return to demo mode. Signing out or switching users clears private client caches and review state so the next user does not inherit them; in-flight work and any later completion must not be applied to a different account merely because the active user changed.
- **Temporary visitor work has its own privacy boundary.** Publicly shared confirmed demo activity does not make notes, photos, or pending import results public. The import-lifecycle decision must isolate that temporary work between visitors when it is held on the server. This may require workflow-specific access proof, but does not by itself require an authenticated demo session or a new personal user identity. Exact access, retention, cancellation, and resume mechanisms are not chosen here.
- **Deletion retains the agreed ownership boundary.** Apply the personal-record deletion and separate backup-expiry requirement from [Set the architecture's quality targets and decision priorities](04-architecture-quality-targets.md#answer). Deletion must end access through that account's credentials/sessions and prevent later work from restoring its deleted personal activity; shared catalog records are not owned by that account. The workflow, active-job handling, and backup schedule remain implementation/lifecycle decisions before deletion is offered.

### What must be fixed now

Model all saved activity with an explicit app-owned user, including the Demo user. Keep trusted user resolution and backend authorization independent of the selected login adapter, frontend, and transport. Preserve the ability to persist, expire, and revoke personal sessions across process restarts. Separate client-specific credential storage from shared client logic. Never treat an authentication failure as permission to switch an operation's owner, and never use the shared Demo user ID alone as authorization to retrieve another visitor's private temporary work.

### Deferrals, boundaries, and revisit triggers

| Deferred choice | Boundary or starting assumption | Revisit trigger / owning ticket |
| --- | --- | --- |
| Auth/session libraries, password-hashing implementation, credential records, session store, token format, lifetimes, and renewal/revocation details | Username/password first; stable app-owned identity; established security implementations; durable revocable personal sessions | Before implementing personal authentication; backend adapter and persistence planning must retain these capabilities |
| Exact browser cookies/request protections, native storage configuration, and credential exchange | Platform-specific adapters, backend enforcement, protected browser/native storage as starting directions | Before authenticated API/frontend contracts are implemented; [Define shared frontend boundaries and platform adapters](08-frontend-ports-and-adapters.md) and [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md) |
| Signup/provisioning, username policy, password change/recovery, and additional authentication features | Initial public demo has no credential flow; first personal method is username/password | When defining the first personal-account release; choose the required flows before enabling it rather than assuming an identity provider supplies them |
| Additional authentication methods and account-linking/merge rules | Credentials resolve a stable owner; no current automatic linking or account merging is specified | Before adding another method or introducing a linking/merge operation |
| Visitor-specific access to temporary inputs, jobs, and review results; account switching during work | Public confirmed demo activity, private temporary work, no forced authenticated demo session, no reassignment of pending work to another user | Before choosing import lifecycle and transport contracts; [Define import review and background-work lifecycles](11-imports-and-background-work.md) and [Choose API contracts and where persistent connections belong](10-api-contracts-and-transports.md) |
| Deletion workflow, job cancellation/discard behavior, and backup expiry schedule | End deleted-account access and do not recreate deleted personal activity; keep shared catalog separate | Before personal deletion is implemented; import-lifecycle and operational decisions own the mechanics |
| Explicit copying of selected demo activity | Personal users start empty; demo activity remains owned by Demo | A concrete product need for a copy feature |

### Cost of reversal and implementation evidence

Using usernames, login-provider identifiers, devices, or sessions as the owner of movie activity would make later credentials, multiple devices, and account changes costly. Trusting a client-supplied owner or allowing silent demo fallback would embed incorrect access behavior. These boundaries are fixed now. Exact libraries, timeout values, token formats, and storage representations are more replaceable while kept behind adapters, though changing deployed session formats may require expiring sessions and changing credential representations may require a planned migration. Revisit such changes deliberately once users exist.

Supporting implementation guidance: [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), and [Expo SecureStore](https://docs.expo.dev/versions/latest/sdk/securestore/). These support the proposed starting directions, not a frozen implementation. Verify current guidance and library behavior when personal authentication is built. No additional blocking research or prototype is needed to establish the boundaries in this resolution; the remaining sharp questions belong to existing dependent tickets or the explicitly deferred personal-account implementation.
