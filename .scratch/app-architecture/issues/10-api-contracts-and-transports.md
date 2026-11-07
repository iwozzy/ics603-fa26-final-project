# Choose API contracts and where persistent connections belong

Type: grilling
Labels: wayfinder:grilling
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 02, 07, 08, 09

## Question

Which interactions use HTTP, WebSockets, or another justified mechanism, and how are transport-independent application operations exposed to all clients? Use transport research, platform requirements, session boundaries, and ports/adapters. Decide validation ownership and contract generation/versioning, structured errors, authorization, duplicate/retried commands, pagination, and reconnect/resume where applicable. Address the user's WebSocket preference with evidence; defer optimizations that need measurements.
