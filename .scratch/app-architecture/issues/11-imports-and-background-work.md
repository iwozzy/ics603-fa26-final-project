# Define import review and background-work lifecycles

Type: grilling
Labels: wayfinder:grilling
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03, 06, 07, 09

## Question

What lifecycle should note/photo extraction, movie matching, and human review follow across request deadlines, failures, retries, reloads, server restarts, and future mobile suspension? Decide which work is synchronous versus durable/background, job/result identity, cancellation or idempotency needs, upload/result retention, and how reviewed results become user-owned movie tracking. Distinguish async I/O from durable execution and prevent model output from becoming trusted saved data without the required review. Decide architecture boundaries, not extraction prompts or models.
