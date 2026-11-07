# Issue tracker: Local Markdown

Issues and specs live as Markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`.
- Specs live at `.scratch/<feature-slug>/spec.md`.
- Each implementation ticket gets its own file:
  `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.
- Number tickets from `01`; never combine them into one file.
- Record state near the top with `Status: open`, `Status: claimed`,
  or `Status: resolved`.
- Append comments and conversation history under `## Comments`.

## Publishing and fetching

When a skill says "publish to the issue tracker", create the appropriate
file under `.scratch/<feature-slug>/`, creating directories as needed.

When a skill says "fetch the relevant ticket", read the referenced file.
Resolve ticket numbers within the relevant feature directory.

## Wayfinding operations

- Map: `.scratch/<effort>/map.md`, containing the destination, notes,
  decisions so far, not-yet-specified work, and out-of-scope work.
- Child ticket: `.scratch/<effort>/issues/<NN>-<slug>.md`.
  Record `Type: research`, `prototype`, `grilling`, or `task`,
  and initialize `Status: open`.
- Blocking: list ticket numbers in `Blocked by: NN, NN`.
  A ticket is unblocked when every listed ticket is resolved.
- Frontier: open, unblocked, unclaimed tickets, ordered by number.
- Claim: save `Status: claimed` before beginning work.
- Resolve: append the answer under `## Answer`, set `Status: resolved`,
  and add a brief summary and link to the map's Decisions so far.
