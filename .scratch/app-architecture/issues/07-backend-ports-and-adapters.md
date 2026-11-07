# Define backend ports, adapters, and deployment boundaries

Type: grilling
Labels: wayfinder:grilling
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 06, 18

## Question

How should backend domain and application responsibilities be separated from API transport, persistence, movie-data providers, LLM Gateway access, semantic retrieval, and observability? Apply the user's ports-and-adapters direction, Pydantic validation at appropriate boundaries, async operation, and stated integration preferences. Decide the necessary module and process boundaries and dependency direction; assess whether any preference should be revised with an explicit rationale. Identify how provider-specific models and failures stay behind adapters without creating abstractions for hypothetical services.
