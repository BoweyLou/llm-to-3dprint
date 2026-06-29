# Task Packet

Use this template to turn a backlog item, issue, accepted review finding, or
human request into work an agent can execute without guessing.

## Task

- ID: `<backlog-id-or-local-id>`
- Title: `<short task title>`
- Priority: `P0 | P1 | P2 | P3`
- Status: `draft | approved | in-progress | blocked | done | deferred`
- Source: `<backlog item, issue, review finding, decision, or human request>`

## Context

- Repository: `<absolute repo path or repo name>`
- Mode: `bootstrap | drift | pull-request | release-gate | learning-comments | test-first | verification`
- Problem statement: `<the actual user or repo problem>`
- Background:
  - `<relevant decision, doc, ADR, Keryx note, or evidence>`
- Non-goals:
  - `<what this packet explicitly will not solve>`

## Scope

- Inspect first:
  - `<files, directories, docs, tests, runtime surfaces>`
- Allowed edits:
  - `<files or directories the implementer may change>`
- Protected:
  - `<files, generated artifacts, unrelated dirty work, production state>`
- Expected outputs:
  - `<files, reports, receipts, docs, tests, or commands this packet should produce>`

## Acceptance Criteria

- `<criterion>` - verify with `<command, file check, screenshot, or review step>`
- `<criterion>` - verify with `<command, file check, screenshot, or review step>`

## Validation

- Required commands:
  - `<command>` - expected `<pass/fail/output>`
- Optional commands:
  - `<command>` - run when `<condition>`
- Evidence to capture:
  - `<test output, docs-check result, diff summary, receipt path, screenshot>`

## Documentation Impact

- Expected: `yes | no | unknown`
- Paths:
  - `<docs, ADRs, changelog, examples, README, prompt index>`
- Waiver allowed: `yes | no`
- Notes: `<why docs are or are not part of done>`

## Risk And Approval

- Risk level: `low | medium | high`
- Known risks:
  - `<behavior, data, security, workflow, UX, migration, release risk>`
- Stop conditions:
  - `<condition that requires human input before continuing>`
- Human approval:
  - Required: `yes | no`
  - State: `not-requested | requested | approved | rejected`
  - Approver/notes: `<name or rationale>`

## Handoff

- Recommended prompt: `<task-packet, fix-implementer, tdd prompt, verification-sentinel, manual>`
- Owner: `<agent, person, or unassigned>`
- Dependencies:
  - `<task id, branch, decision, credential, external runtime>`
- Next packet hint: `<follow-up work that should stay separate>`
