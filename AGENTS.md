# Instructions for coding agents

A web app that helps people discover movies from their favorite actors, directors and creative team.

The full proposal is in docs/proposal.md.

## Layout

- app/main.py: routes and the page. No business rules.
- app/agent.py: the Pydantic AI agent and output model.
- app/rules.py: rules in plain Python. No FastAPI, no LLM client.

## Commands

```bash
uv run fastapi dev app/main.py # run the app
uv run ruff check # lint
uv run mypy # check types
uv run pytest # run the tests
```

## Rules

- Tests never call a real model. Use TestModel with override_allow_model_requests(False).
- Read LLM_API_TOKEN and LLM_API_GATEWAY from the environment. Never write a key outside .env.
- Run ruff, mypy, and pytest after every change and include their output. Never report done while one fails.
- Never weaken a check: no raised max-complexity, no # noga or # type: ignore, no skipped tests.


## Engineering Principles

- Optimize for correctness, readability, simplicity, and long-term maintainability.
- Code is read and modified more often than it is written. Favor solutions that another engineer can understand, debug, and extend without unnecessary cognitive overhead.
- Prefer the simplest implementation that clearly expresses the intended behavior.
- Follow established conventions and introduce abstractions only when they solve a demonstrated problem.
- Make the smallest coherent change, preserve unrelated behavior, and verify correctness before completion.
- Avoid unrelated refactoring or modifications outside the scope of the task.
- Make design decisions that minimize unnecessary coupling and complexity.

## Comments and Documentation

- Prefer self-explanatory code over comments that describe obvious operations.
- Explain why a decision was made, not merely what the code does.
- Document non-obvious invariants, business rules, constraints, and tradeoffs.
- Keep comments and documentation synchronized with behavior.
- Document public interfaces where their contracts are not immediately clear.


## Changes

- Never commit to main. Make each change on its own branch and open a pull request with gh pr create. The description has a ## Summary (what changed why, citing docs/proposal.md) and a ## Test plan checklist (checked items were run: unchecked items are left for the reviewer).
- After pushing, run gh pr checks --watch and report the result.
- Never merge a pull request. The person after reviewing it.

