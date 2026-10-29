---
name: pr-diagram
description: Use when a pull request is opened, ready to open, or its description is being prepared or updated in this repository.
---

# PR diagram

Add one Mermaid diagram of the change to the pull request description. Work only on the description or its draft; never edit code, create commits, push branches, open another PR, or merge.

## Read the change

- Read the repository's `AGENTS.md` Changes section first. Preserve its description requirements, including `## Summary`, its citation to `docs/proposal.md`, and the `## Test plan` checklist. Do not change existing prose, checkbox states, or other sections to make room for a diagram.
- For an existing PR, identify the PR for the current branch and read its current body, base, head, and full diff with `gh pr view` and `gh pr diff`. Do not guess a PR number or use a different branch's PR.
- Before opening, read the intended base-to-head diff and any staged or unstaged changes intended for this PR. Use the existing description draft; if none exists, prepare a draft following Changes. This skill does not itself authorize opening a PR.
- Read the relevant files and function bodies at both revisions as needed, including deleted or moved code. The diff alone is not evidence of a call relationship.

## Choose and verify one diagram

| Change | Mermaid form |
| --- | --- |
| New request path | `sequenceDiagram`, starting at the changed route or handler |
| Module split | One `flowchart LR` with `Before` and `After` subgraphs |

If both apply, prefer the module split. Select the smallest coherent part that explains the change.

Use at most eight boxes total: sequence participants, or module nodes across both subgraphs combined. Each box must name a real file or function in the diff, with its repository path (and function name when applicable). Count before and after copies separately. Subgraph headings are labels, not boxes. Leave external users, browsers, services, and conceptual layers out of the diagram.

Check every arrow against the code at the revision depicted: caller to callee for calls, importer to imported module for imports, and actual direction for returns or data flow. Label the relationship. For a split, show the real dependencies in each revision; placement in Before/After conveys relocation without invented runtime arrows. Omit any relationship you cannot verify. Never modify code to justify a diagram.

If neither form fits, or evidence is insufficient, report why a faithful diagram cannot be produced; do not invent a request path or split.

## Update the description

Insert a `## Change diagram` section between Summary and Test plan containing exactly one fenced `mermaid` block. Replace that section on subsequent runs rather than appending duplicates; preserve everything outside it.

For an existing PR, re-read the body immediately before updating so concurrent edits are preserved. Use `gh pr edit <number> --body-file <temporary-file>` with the complete preserved body, then read it back to verify the diagram and unchanged Summary and Test plan. If access fails, retain the proposed body as a draft and report the failure; do not create a replacement PR. Before opening, add the section to the draft for the normal PR-opening workflow.
