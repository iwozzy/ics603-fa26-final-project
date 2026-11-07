# Identify the LLM Gateway and its documented capabilities

Type: task
Labels: wayfinder:task
Mode: HITL
Status: open
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03

## Question

Before committing the gateway adapter and resource-control contracts, obtain the identity and official documentation for the actual LLM Gateway referred to in the proposal. The integration research could not establish its protocol or capabilities from the repository. The prerequisite work is to supply references, not choose an extraction model or build the integration.

The human should provide the gateway/service name and official or course-provided documentation. From those references, the agent should capture the supported API/interface, authentication mechanism and configuration location, image-input and structured-output support, usage reporting, limits/retry rules, embedding availability if any, and retention/data-handling information. Record absent information explicitly and identify any separately needed compatibility check. Resolve with the references and resulting facts; later tickets make architecture choices from that evidence.
