# Choose deployment, observability, and resource-control boundaries

Type: grilling
Labels: wayfinder:grilling
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 04, 10, 11, 13, 14

## Question

What Docker-based deployment topology and operational controls are justified by the quality targets and selected architecture? Decide where async API execution, any durable/background work, Neon connections, secrets, migrations, and external-provider budgets live. Define how Logfire spans requests/jobs/provider calls while handling sensitive content, and where global LLM usage limits, TMDB limits, timeouts, and failure recovery are enforced. Defer hosting details only where doing so preserves the architecture and records a revisit trigger.
