# Domain Docs

This repo uses a single-context layout.

## Before exploring

- Read `GLOSSARY.md` at the repo root.
- Read decisions in `docs/adr/` relevant to the area being explored.

If these files or directories do not exist, proceed silently.
Do not suggest creating them upfront. The domain-modeling skill creates
them as terms and decisions are resolved.

## File structure

- `GLOSSARY.md`: shared domain vocabulary.
- `docs/adr/`: architectural decision records.

## Use the glossary's vocabulary

Use defined terms when naming domain concepts in issues, proposals,
hypotheses, tests, and code. Avoid synonyms the glossary excludes.

If a needed concept is missing, reconsider the terminology or note
the gap for domain-modeling.

## Flag ADR conflicts

Explicitly identify any proposal that contradicts an existing ADR,
including the decision identifier and why it should be reconsidered.
