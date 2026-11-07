# Research HTTP and WebSocket transport trade-offs

Type: research
Labels: wayfinder:research
Status: resolved
Assignee: Codex architecture transports research
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)

## Question

For web and future iOS/Android clients using an async Python API, what should determine HTTP versus WebSocket use for search, follows/watch status, timeline queries, photo uploads, extraction progress, and semantic search? Use primary specifications and official implementation/platform docs. Examine HTTP connection reuse/multiplexing, WebSocket handshake and connection behavior, authentication, reconnect/resume, mobile suspension, backpressure, upload behavior, proxies, and Docker deployment. Evaluate the stated hypothesis that WebSockets generally avoid HTTP overhead enough to be preferred. Identify measurements needed and sensible boundaries for mixing transports without selecting the final contract.

## Answer

The cited report is complete and published on its research branch. HTTP/1.1 reuses connections and HTTP/2 multiplexes exchanges with compressed headers, so avoiding repeated connection setup does not establish a general WebSocket advantage. Frequent bidirectional messages remain a plausible socket use case; polling or SSE can cover progress-only updates. iOS background file transfers use HTTP(S), Android Doze restricts app network access, and every foreground stream needs state recovery. Async I/O, durable execution, upload transfer, and progress delivery are independent choices. The report covers authentication, retries/resume, backpressure, proxies, Docker shutdown, and measurements without selecting the final transport contract.

- Branch: `research/app-architecture-transports`.
- Commit: `d8b4e10254740ffd3cd857e6193493c5a3c08dad`.
- Committed path: `.scratch/app-architecture/research/client-transports.md`.
- Local worktree report: [Client transport research](/private/tmp/ics603-app-architecture-transports/.scratch/app-architecture/research/client-transports.md).
- Published report: [Client transports: HTTP, WebSockets, and progress notifications](https://github.com/iwozzy/ics603-fa26-final-project/blob/d8b4e10254740ffd3cd857e6193493c5a3c08dad/.scratch/app-architecture/research/client-transports.md). Branch pushed to origin; no PR or merge created.

## Comments

- Automatic approval review initially rejected the subagent's push for unverified destination/export authorization. The main session verified the project remote and report-only payload, supplied the original user-provided wayfinder instruction to push research branches, and received approval for a successful push. No publication blocker remains.
