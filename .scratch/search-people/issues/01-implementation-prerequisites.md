# Choose minimum implementation tools and runtime bounds

Type: task
Status: open
Parent: [Search people](../spec.md)

## Outcome

Record the concrete tools and settings needed to implement the agreed locally runnable web/Python feature. This is the explicit implementation prerequisite deferred by Q26, not an unresolved product-behavior question.

## Scope

- Choose the async Python API framework, HTTP client, dependency/runtime commands, and backend entry point within the existing Python project.
- Choose the Expo/React Native for Web TypeScript workspace setup, package manager, and local client/backend connection arrangement. Preserve future native boundaries without requiring native builds.
- Select API-specific Pydantic schemas and matching TypeScript types/runtime validation, plus API/workflow/browser verification tools. Use the normalized contract in the spec; record concrete field/type details before dependent work.
- Set numeric backend provider timeout, client waiting bound, input/request size bounds, incoming/outgoing admission and expensive-concurrency bounds. Preserve one provider attempt, no automatic retries, and prompt HTTP failure. Ensure the client does not normally time out before the backend can report its bounded outcome.
- Record local TMDB credential/API-base configuration with secrets kept outside source/client bundles. Select instrumentation settings that omit searched names and returned content, including URL query capture.
- Set the minimum package/module seams and local startup/test commands. Introduce ports for the actual workflow; do not create speculative persistence or gateway modules.

## Acceptance

- Every dependent implementation choice above has a recorded selection or concrete configuration, with commands sufficient to bootstrap the local feature.
- The selections preserve the spec's wire behavior, ordinary browser caching, ports/adapters, async I/O, and no feature-data persistence.
- Public hosting, durable global accounting, deployment and native delivery remain separate from local completion; see [05](05-public-release-prerequisites.md).

## Comments

Created from the settled Q2–Q26 planning interview. Unstarted.

### Planning acceptance — 2026-11-12 (Pacific/Honolulu)

The user accepted the consolidated handoff in Q27. This prerequisite ticket remains open; implementation has not started.
