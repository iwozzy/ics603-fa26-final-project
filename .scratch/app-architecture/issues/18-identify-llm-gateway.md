# Identify the LLM Gateway and its documented capabilities

Type: task
Labels: wayfinder:task
Mode: HITL
Status: resolved
Assignee: Codex
Parent: [Architecture for a shared web and native movie-discovery app](../map.md)
Blocked by: 03

## Question

Before committing the gateway adapter and resource-control contracts, obtain the identity and official documentation for the actual LLM Gateway referred to in the proposal. The integration research could not establish its protocol or capabilities from the repository. The prerequisite work is to supply references, not choose an extraction model or build the integration.

The human should provide the gateway/service name and official or course-provided documentation. From those references, the agent should capture the supported API/interface, authentication mechanism and configuration location, image-input and structured-output support, usage reporting, limits/retry rules, embedding availability if any, and retention/data-handling information. Record absent information explicitly and identify any separately needed compatibility check. Resolve with the references and resulting facts; later tickets make architecture choices from that evidence.

## Context

Apply the user's TMDB confirmation in [Establish permitted catalog-data use and provider strategy](17-provider-permissions-and-strategy.md#answer): the app's use case is allowed and training AI with TMDB data is prohibited. Capture whether the gateway and underlying model services use submitted content for training and which configuration or agreement supports keeping TMDB content out of such reuse. This is part of the integration's data-handling check, not a new provider-permission prerequisite or a model selection.

## Comments

### Prerequisite check — 2026-11-09 (Pacific/Honolulu)

- Claimed the first open, unblocked ticket after the catalog-persistence decision.
- Checked the proposal, project metadata, and local architecture documents. They refer to an LLM Gateway and a historical extraction model, but do not identify the service, its API base URL, or its official/course documentation. The existing integration research likewise records the gateway as unidentified.
- Awaiting the human's gateway/service name and documentation URL or course-provided excerpt. Once identified, check its documented capabilities and data handling; do not infer a particular gateway or protocol from the model name. The ticket remains claimed and unresolved.

### Gateway supplied — 2026-11-09 (Pacific/Honolulu)

- The user identified the gateway as private and supplied [its capability document](https://128.171.10.83:9443/llms.txt).
- Retrieved that document over HTTPS with default certificate verification. No credentials, authenticated endpoint calls, model requests, or integration tests were used.
- The supplied reference and the facts/unknowns below complete this prerequisite task. Model selection and architecture decisions remain with their owning tickets.

### Architecture clarification — 2026-11-09 (Pacific/Honolulu)

The user requires ports and adapters for gateway access. The gateway may change, and different tasks may use different gateways concurrently. This clarification is incorporated into the Answer below; identifying the current service does not make it an exclusive application dependency.

## Answer

Resolved on 2026-11-09 (Pacific/Honolulu). The gateway is the private, course-provided **LLM API Gateway**, documented at [llms.txt](https://128.171.10.83:9443/llms.txt). Its documented API base URL is `https://128.171.10.83:9443/v1`.

### Documented capabilities

The following are claims from the supplied gateway document, not runtime verification. The document has no visible version/date; this retrieval's SHA-256 is `b564d55d3279ea6a89ca05abef85260385ed69bb5aabab55756b016943f32615`.

| Area | Finding |
| --- | --- |
| Interface | OpenAI-compatible Chat Completions across chat models, including streaming. Responses support varies by model; the document recommends Chat Completions. |
| Authentication/configuration | Personal bearer key from the dashboard's student API portal; regeneration invalidates the previous key. Environment-variable configuration is documented as `LLM_API_KEY`; the client also needs the base URL. No project secret location is configured by this task. |
| Models/embeddings | Authenticated `GET /v1/models` supplies available models. `POST /v1/embeddings` lists `text-embedding-3-small`; availability does not select it for this app. |
| Usage/budget | Instructor-set dollar budget; portal shows spending and remaining balance. Gateway records model, token counts, cost, and time. No programmatic remaining-budget endpoint is documented. |
| Limits/errors | Requests up to 10 MB. Documented `429` means exhausted budget; do not retry it. `401` requires key/account correction; `400` requires request correction; model/endpoint mismatch may return `405`. Upstream `500/503` may be retried after a delay. Numerical rate/concurrency limits and timeout guarantees are absent. |
| Response storage | Only a listed subset supports stored Responses, retrieval/deletion/cancellation, input-item access, and prior-response chaining. Other models may ignore background execution or discard prior-response context. Do not assume gateway-backed durable jobs or conversation memory across all models. |
| Privacy | Gateway says it retains usage metadata, not prompt/reply content. Upstream providers apply their own policies. This does not establish a no-training guarantee or resolve optional stored-Response retention upstream. |

### Unspecified capabilities and compatibility checks

- **Image inputs:** no vision capability matrix, accepted image formats, or image request examples. Verify image support and practical payload limits for the eventual extraction model before photo integration.
- **Structured outputs:** no JSON-schema response format or tool-calling guarantees. Verify the selected model and endpoint's behavior through the intended Pydantic AI adapter; do not infer it from OpenAI compatibility.
- **Async/client integration:** protocol documentation supports investigating a custom-base-URL adapter, but no Pydantic AI or async integration was tested. Before integration, check authenticated model discovery, a minimal request, output validation, usage fields, error mapping, and cancellation/timeout behavior for the selected operations.
- **Data handling:** upstream training reuse, retention, and optional stored-response handling are not established here. Check the actual selected model route and applicable settings/agreement before sending TMDB content or personal extraction inputs; preserve the existing prohibition on AI training with TMDB data. This is not a new TMDB-permission investigation.
- **Service lifetime:** coursework access is documented; availability, funding, and key validity beyond the course are unspecified. Revisit before relying on it for the maintained product beyond course access.

### Consequences and handoff

**Gateway independence and selection by task.** Application operations depend on application-owned ports, with gateway-specific protocols, SDKs, payloads, authentication, models, and failures handled by adapters. Allow different tasks, such as extraction, suggestions, and embeddings, to use independently configured gateway adapters. Replacing one gateway must not require changing domain or application logic or moving every other task to that gateway. The private course gateway is one available adapter target; its API and limits do not define all gateway contracts. Concrete port interfaces and configuration/composition belong to [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md).

The service identity, protocol, authentication, embeddings endpoint, and budget/error semantics are now documented. Missing feature guarantees are explicit checks before those features are integrated, rather than reasons to leave the gateway unidentified. Backend port design can proceed without assuming vision, structured outputs, stored Responses, or a particular model.

- [Define backend ports, adapters, and deployment boundaries](07-backend-ports-and-adapters.md) owns replaceable gateway configuration, adapter contracts, and failure boundaries.
- [Define import review and background-work lifecycles](11-imports-and-background-work.md) owns extraction lifecycle and cancellation; selected-model photo/output compatibility is checked before implementation.
- [Define the semantic-search boundary and indexing lifecycle](13-semantic-search-architecture.md) evaluates the documented embeddings option without presuming it meets quality or lifecycle requirements.
- [Choose deployment, observability, and resource-control boundaries](15-deployment-observability-and-resource-limits.md) owns server-side secrets, application-wide budgets, retry policy, data-handling verification, and the post-course access assumption.

Keep each task's gateway/model and endpoint configuration behind its configured adapter. Switching later may require model evaluation and, if the embedding model or representation changes, reindexing; changing the gateway alone does not necessarily change the embedding space. This task commits to neither a model nor a client library. No glossary change, standalone research asset, implementation, or publication is needed to record this task's resolution.
