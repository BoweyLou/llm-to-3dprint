# ADR 0001: Testing Philosophy

## Status

Accepted

## Context

Agent-heavy development can produce code that appears plausible without proving behavior. Documentation guardrails reduce drift, but behavior still needs executable evidence.

## Decision

This repository uses a test-first and executable-specification bias.

For new behavior, start with a failing behavior test when practical. For bug fixes, capture the bug with a regression test before changing production code. For refactors, add characterization tests around current behavior before restructuring. For public contracts, use contract tests. For logic with large input spaces or invariants, prefer property or invariant tests when they add value.

TDD is the default posture, not a dogma. The repository may skip tests for docs-only, comment-only, generated, emergency, or clearly mechanical changes when the PR explains why.

## Consequences

- Reviewers can ask for executable proof when behavior changes.
- Refactors should be smaller and safer.
- Tests become part of the documentation system.
- Contributors should avoid brittle tests that only assert implementation details.
- The PR should explain test coverage or why tests were not useful.

