# Guest session validation cache

Approved in conversation on 2026-11-15: implement a bounded in-memory cache of validated guest sessions with Postgres fallback. Reduce people-search latency by avoiding repeated session queries and their transactions. Quota admission and charging remain unchanged.

## Approaches

The alternatives discussed were validating the session inside database admission, caching validated sessions, or switching to signed tokens. The user selected caching first. It preserves the opaque cookie format and existing persistent sessions without a migration or shared cache service. Each worker warms its own cache; restarts/eviction cause database fallback. Deletion/revocation can remain stale until the cache TTL expires.

## Design and implementation calls

- Cache immutable `StoredGuestSession` values keyed by the cookie digest, never raw cookie values. Never cache the request IP; build `GuestContext` from each request's server-resolved IP.
- Use a process-local least-recently-used cache, default capacity 10,000 entries and fixed TTL 60 seconds. Both are constructor parameters. A monotonic timer bounds TTL; hits update recency but do not renew TTL. Every hit also verifies the actual session expiry using the request time. TTL and capacity values are implementation defaults chosen by the implementer.
- Bootstrap continues authoritative database admission and session lookup/creation. Publish a cache entry only after its unit of work commits and exits successfully. A reused session retains its original expiry.
- Resolve rejects missing/oversized proofs before cache or database work. A cache hit opens no unit of work. A miss uses the existing Postgres lookup, populating the cache only after successful unit-of-work exit. Invalid, expired, and failed lookups never create positive cache entries.
- Database outage behavior: an already validated, unexpired cache entry can resolve until its TTL, while a cache miss fails closed. Search still needs the existing durable quota operation before provider dispatch.
- No negative caching, background refresh, shared invalidation, new infrastructure, new runtime settings, or API changes. Concurrent misses may perform duplicate reads; the cache contains only completed validations and has no tasks or locks spanning database I/O.

## Verification

Test warmed hits opening zero database units of work; database fallback after TTL, restart and eviction; actual expiry before TTL; TTL not sliding on hits; current-IP changes; bounded LRU behavior; commit/read/exit failures; revocation after TTL; and unchanged bootstrap quota enforcement. Use deterministic clocks and synthetic data. Run backend tests, real Postgres integration tests, lint/type/import checks, composed browser tests and a fresh code review. Preserve the existing uncommitted admission changes in this worktree.
