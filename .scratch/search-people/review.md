# Search people implementation review

Date: 2026-11-12 (Pacific/Honolulu)
Fixed point: `00ab21a0a3ba6230ea0b97faa22aa895ddd052f8`
Initial implementation: `4a371ced944842eca926736b3e153b8edfe033c6`
Diff: `git diff 00ab21a0a3ba6230ea0b97faa22aa895ddd052f8...HEAD`

Independent Standards and Spec agents reviewed the committed implementation in parallel, with fresh contexts. The Spec agent then checked the correction below. Their reports follow separately.

## Standards

No actionable Standards findings.

The diff follows the documented vocabulary, Pydantic boundary contracts, async provider I/O, framework-independent client workflow, runtime response validation, and public-workflow testing direction. ADR-0001 explicitly permits the transient identities/storage behavior, manual submission, seven-result limit, status-only failures, and separate public-release gate.

No baseline smell warranted an actionable finding. The small `search_people` delegation preserves the documented application-owned capability boundary; treating it as a Middle Man would conflict with that architectural intent.

Standards: **0 documented violations, 0 actionable smell findings**. Read-only review; no tests rerun.

## Spec

One Spec finding:

- **[P2] Configurable backend deadlines can outlast the fixed browser deadline.** `backend/wayfinder/config.py` checked only that the operation timeout exceeded the provider timeout, while `client/search/backend.ts` always aborted after eight seconds. `Settings(provider_timeout=12, operation_timeout=13)` was accepted. With those documented configuration overrides, a valid provider response taking nine seconds was discarded by the UI while the backend continued working. Spec: **“Align client waiting with backend/provider deadlines.”** Reject configurations exceeding the browser budget, or supply a corresponding client deadline.

No other actionable missing requirements, incorrect behavior, or scope creep found. Default deadlines were aligned; this finding concerned supported configuration overrides.

### Correction and verification

Startup now rejects operation deadlines above seven seconds, while retaining the requirement that the provider deadline is shorter. README and implementation prerequisites document the bound. Manual verification invoked the actual runtime factory with `WAYFINDER_PROVIDER_TIMEOUT=12` and `WAYFINDER_OPERATION_TIMEOUT=13`; startup rejected the configuration with the expected safe configuration error. The final full suite passed all 25 API + 23 browser tests after this change. TypeScript/Python typechecks and Python lint passed; contract regeneration produced no diff.

The Spec reviewer confirmed: “Startup now enforces `provider_timeout < operation_timeout ≤ 7 seconds`, below the eight-second browser deadline. README and implementation prerequisites document the constraint. No remaining Spec findings.”

Standards: **0 findings**. Spec: **1 P2 deadline-configuration finding, resolved and independently rechecked**. No unresolved findings on either axis.
