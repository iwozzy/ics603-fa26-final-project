# Choose catalog persistence and provider-refresh boundaries

Type: grilling
Labels: wayfinder:grilling
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 06, 09, 17

## Question

How should Neon Postgres hold shared catalog records, credits, external identities, and per-user tracking while supporting timeline queries and future data providers? Decide sources of truth, refresh/cache boundaries, deduplication, consistency expectations, migrations, and any durable identifiers or schema choices that would be expensive to reverse. Use TMDB usage constraints and the domain model. Preserve an explicit strategy for possible TV support without designing a complete future schema.
