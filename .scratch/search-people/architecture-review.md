# Ports and adapters refinement review

Date: 2026-11-12 (Pacific/Honolulu)
Fixed point: `48af2ab056c3cb3c1df44f17fe97ebbb81a1e9da`
Implementation: `74817467aed976b552c1e22d0d476438d342d255`
Diff: `git diff 48af2ab056c3cb3c1df44f17fe97ebbb81a1e9da...HEAD`
Commit reviewed: `7481746 Separate search application policy from adapter composition`

Independent Standards and Spec agents reviewed the committed diff in parallel with fresh contexts, following the code-review skill. Standards sources were AGENTS.md, the tracker/domain instructions, GLOSSARY.md, ADR-0001, and the codebase-design skill. Spec source was the current [Search people spec](spec.md), including the approved ports-and-adapters refinement.

## Standards

No findings.

The diff follows ADR-0001's backend dependency direction, startup composition, application-owned admission port, and frontend core/adapter separation. Provider-independent selection now belongs to the application operation; generated transport types stay in the HTTP adapter.

No actionable baseline smells found. The new injection interfaces and client model implement explicitly approved seams, so they do not warrant Speculative Generality or Middle Man findings. Name validation is shared, with both calls justified by pre-admission rejection and independent application-operation use.

Standards: **0 hard violations; 0 actionable smell findings.**

## Spec

No Spec findings.

The diff satisfies the approved ports-and-adapters refinement: runtime composition selects backend adapters, the API receives an injected search capability, application code owns deduplication and result/title limits, and frontend startup injects the HTTP adapter into a workflow using client-owned types.

Source review found no missing requirements, scope creep, or incorrect implementation introduced by this change. Existing API, workflow, deadlines, admission, cache, and logging behavior appear preserved. Tests were not rerun by the reviewer.

Standards: **0 findings**. Spec: **0 findings**. Neither axis has an unresolved issue.

## Verification evidence

- All 27 API and 27 Chromium browser tests passed.
- Backend coverage used the configured branch option: 85% combined coverage, with 100% reported for the search application module.
- Python and TypeScript typechecks, Ruff lint/format checks, ESLint, and Prettier passed.
- Regenerating the public API schema and TypeScript types produced no diff.
- Real-TMDB smoke passed through the refactored startup: one provider attempt and one result, a 180×180 portrait, browser cache transfer bytes `[594, 0]`, and runtime output excluding searched/returned content and credentials.
