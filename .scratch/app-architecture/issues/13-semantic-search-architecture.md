# Define the semantic-search boundary and indexing lifecycle

Type: grilling
Labels: wayfinder:grilling
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 07, 12

## Question

What is the semantic-search contract: searchable corpus, retrieval unit, eligibility rules, user query and filters, result provenance, and freshness? Decide how embeddings, indexing/reindexing, and retrieval fit behind ports, what Postgres/Neon can support, and which technology choices require a research ticket after these requirements are settled. Separate retrieval from recommendation generation and decide what must be fixed now versus measured later; do not assume a model or vector store.
