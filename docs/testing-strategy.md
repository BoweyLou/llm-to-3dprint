# Testing Strategy

This repository uses a test-first bias: important behavior should be described by executable tests before or alongside implementation.

## Principles

- Start with observable behavior: user-visible flows, APIs, CLIs, jobs, imports/exports, and domain outcomes.
- Prefer the smallest test boundary that proves the contract.
- Add regression tests before bug fixes.
- Add characterization tests before risky refactors.
- Add contract tests for APIs, schemas, generated clients, event payloads, persisted data, and file formats.
- Use property or invariant tests where examples cannot cover the meaningful input space.
- Treat tests as executable documentation and keep them aligned with docs and ADRs.

## Prompt Support

The prompt set lives in `.codex/prompts/tdd/`.

Use:

- `test-first-feature.md` for new behavior.
- `regression-first-bugfix.md` for bugs.
- `characterization-before-refactor.md` for legacy or unclear code.
- `outside-in-acceptance-tdd.md` for user-visible workflows.
- `property-and-invariant-tests.md` for invariants and edge cases.
- `contract-test-design.md` for API, schema, event, generated-client, and file-format boundaries.
- `refactor-under-tests.md` for behavior-preserving structure changes.
- `test-quality-sentinel.md` before considering the change done.
- `tcr-micro-loop.md` only when the repo is clean, tests are fast, and the user wants strict micro-steps.

## Definition of Done

A change is complete when:

- The intended behavior is covered by meaningful tests or an explicit reason explains why not.
- Relevant tests pass locally or the blocker is documented.
- Tests prove behavior rather than only asserting mocks or implementation details.
- Docs and ADRs match the tested behavior.

## No-Test-Needed Cases

Some changes can reasonably skip tests:

- Docs-only edits.
- Comment-only edits.
- Mechanical formatting with no behavior change.
- Generated output when the generator is already tested.
- Emergency operational changes where testing is impossible in the moment.

When skipping tests, explain why in the PR.

