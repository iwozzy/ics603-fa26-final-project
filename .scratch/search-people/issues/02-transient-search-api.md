# Implement the transient people-search API

Type: task
Status: open
Parent: [Search people](../spec.md)
Blocked by: 01

## Outcome

Implement `GET /api/people/search?query=...` through a Python application operation and async TMDB adapter, with no search/catalog/user-activity persistence.

## Scope

- Validate and trim input at the backend boundary. Missing/blank queries fail without a provider call under the selected HTTP `500` contract.
- Request only provider page 1, leaving language/adult options unset. Use server-side credentials, one provider attempt, configured bounds, and no automatic retries or additional metadata/page calls.
- Translate the provider envelope; skip rows without usable IDs/names, deduplicate by person ID keeping the first valid occurrence, preserve provider order, and take at most seven.
- Return normalized provider references, name, portrait URL/null, department/null, and up to three usable movie/TV recognition labels in their array order. Join the requested portrait base/path with one slash.
- Return HTTP `200` and a results list for valid envelopes, including empty results. Failures, invalid envelopes and denied admission return HTTP `500` without required client error details.
- Set `Cache-Control: private, max-age=60` on successes and `Cache-Control: no-store` on failures. Do not add a server query cache or pagination metadata.
- Wire local bounds and internal timings/outcomes/usage accounting outside domain decisions. Omit raw query/result content and credentials from telemetry and request logs.

## Acceptance

Exercise the public API with a controlled provider, covering sample mapping, deliberately nonmonotonic popularity, invalid and duplicate rows, optional metadata, mixed movie/TV labels, empty results, bad envelopes, timeouts, refusal, request counts and response headers. Verify that input rejection calls no provider and searching performs no feature-data writes. Assert observable behavior rather than internal package structure.

## Comments

Created from the settled feature spec. Unstarted; public-release accounting verification is tracked separately in [05](05-public-release-prerequisites.md).
