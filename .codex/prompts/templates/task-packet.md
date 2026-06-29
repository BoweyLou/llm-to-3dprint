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
  - `<compact report consulted first, such as make agent-context-bundle, make agent-start, make goal-check, or explicit reason unavailable>`
  - `<report omission, stale result, blocker, ambiguity, or scoped source inspection evidence>`
  - `<relevant decision, doc, ADR, Keryx note, or evidence>`
- Non-goals:
  - `<what this packet explicitly will not solve>`

## Previous Task State (`previous_task_state`)

- report_sources:
  - `<agent-context-bundle, agent-task-status, agent-state-ledger, finalizer receipt, preflight/self-heal receipt, scoped source check, or reason unavailable>`
- active_tasks:
  - id: `<task id or none>`
    state: `<active | stale | blocked | terminal | unknown | none>`
    evidence: `<report line, receipt path, or explanation>`
- unresolved_blockers:
  - `<missing finalizer, stale metadata, dirty checkout, blocked worktree, missing receipt, owner decision, or none>`
- dirty_or_stale_state:
  - `<dirty file/task state, stale task metadata, missing worktree, ambiguous sidecar state, or none>`
- finalizer_receipt_paths:
  - `<finalizer or final receipt path proving previous work is closed, or explicit unavailable reason>`
- blocker_receipt_paths:
  - `<blocker, self-heal, preflight, or owner-escalation receipt path, or none>`
- allowed_to_start: `yes | no`
- closeout_required_before_start:
  - decision: `safe-start | refuse-start | blocker-escalation`
  - reason: `<when implementation may start, must refuse, or must escalate before edits>`
  - required_next_step: `<exact finalizer, task-status, closeout preview, self-heal, blocker receipt, or owner action needed next>`
  - evidence_paths:
    - `<receipt, report, or scoped source path>`

## Goal Alignment

- repo_goal: `<concise repo goal summary, source reference, or explicit unknown>`
- area_contracts:
  - path: `<affected path, directory, glob, or not-applicable>`
    purpose: `<area purpose summary, or explicit unknown>`
    source: `<doc, ADR, packet, manual note, or unknown>`
    status: `aligned | unknown | conflict | not-applicable`
- alignment_decision: `aligned | unknown | conflict | adaptation-needed`
- adaptation_needed: `yes | no`
- stop_conditions:
  - `<unknown or conflicting repo/area goal, unapproved goal adaptation, or other reason to stop before implementation handoff>`

## Scope

- Inspect first:
  - `<compact reports to inspect before source files: agent-context-bundle, agent-start, agent-next/backlog-status, goal-check, agent-task-status, agent-token-budget>`
  - `<scoped source files to inspect only when reports are missing, stale, blocked, ambiguous, or omit required evidence>`
  - `<files, directories, docs, tests, runtime surfaces>`
- Allowed edits:
  - `<files or directories the implementer may change>`
- Protected:
  - `<files, generated artifacts, unrelated dirty work, production state>`
- Expected outputs:
  - `<files, reports, receipts, docs, tests, or commands this packet will produce>`

## Coordination

- Active task count: `<number or unknown>`
- Active sibling tasks:
  - `<task id, branch/worktree, declared scope, owner/session, lease state>`
- Overlap warnings:
  - `<scope or protected-file warning, or none>`

## Harness Metrics

- Context file count: `<number or unknown>`
- Deterministic reports:
  - `<agent-context-bundle, agent-start, agent-next, goal-check, task-status, token-budget, or explicit unavailable/stale/blocked/ambiguous result>`
  - `<omissions or scoped source inspection used when filling required fields>`
- Token budget:
  - `<budget source such as agent-context-bundle or make agent-token-budget, estimated footprint, over-budget paths, omissions, or unknown>`

## Acceptance Criteria

- `<criterion>` - verify with `<command, file check, screenshot, or review step>`
- `<criterion>` - verify with `<command, file check, screenshot, or review step>`

## Validation

- Commands:
  - `<command>` - expected `<pass/fail/output>`
- Optional commands:
  - `<command>` - run when `<condition>`
- Evidence to capture:
  - `<report paths or commands consulted, missing/stale/blocked/ambiguous report reasons, and scoped source inspection used to fill omissions>`
  - `<test output, docs-check result, diff summary, receipt path, screenshot>`

## Closeout Requirements

- Final receipt path: `<.agent-workflows/tasks/<id>/receipt.json or sidecar receipt path>`
- Readiness check:
  - Command: `<make agent-task-ready TASK=<id> TASK_READY_JSON=1 or reason unavailable>`
  - Expected result: `<ready report passes, or blocker is recorded>`
- Lifecycle action:
  - Action: `finish | block | abandon`
  - Command: `<make agent-task-finalize TASK=<id> TASK_RECEIPT=<path> TASK_FINALIZE_JSON=1 or lifecycle fallback>`
  - Expected result: `<metadata is closed and final receipt is linked>`
- Final task status:
  - Command: `<make agent-task-status TASK_STATUS_INCLUDE_CLOSED=1 TASK_STATUS_JSON=1>`
  - Expected result: `<task is terminal, receipt path is visible, active overlaps are explained>`
- Closeout preview:
  - Command: `<make agent-task-closeout TASK_CLOSEOUT_JSON=1>`
  - Expected result: `<eligible, retained, or blocked cleanup state is recorded>`
  - Apply requires explicit approval: `yes`
- Dirty-state explanation:
  - `<state whether the checkout is clean, only expected files are dirty, cleanup is blocked, or unrelated dirt is preserved>`

## Documentation Impact

- Expected: `yes | no | unknown`
- Paths:
  - `<docs, ADRs, changelog, examples, README, prompt index>`
- Documentation surfaces:
  - `<exact README, docs page, ADR, runbook, example, profile doc, or prompt doc expected to change or be checked>`
- Release metadata:
  - `<VERSION, CHANGELOG.md, release note, changelog-update command, or explicit No docs needed waiver surface>`
- Generated docs:
  - `<generated CLI reference, generated prompt adapter, generated schema docs, or explicit not-applicable>`
- Contract references:
  - `<JSON schema, OpenAPI/API reference, config reference, docs-as-tests claim file, command-map field, or explicit not-applicable>`
- Verification commands:
  - `<make docs-check, make docs-freshness, make version-check, make agent-changelog-update CHANGELOG_UPDATE_CHECK=1, make docs-as-tests, or scoped skip reason>`
- Waiver allowed: `yes | no`
- Notes: `<why docs are or are not part of done>`

## Risk And Approval

- Risk level: `low | medium | high`
- Known risks:
  - `<behavior, data, security, workflow, UX, migration, release risk>`
- Stop conditions:
  - `<condition that requires human input before continuing>`
- Human approval:
- Approval needed: `yes | no`
  - State: `not-requested | requested | approved | rejected`
  - Approver/notes: `<name or rationale>`

## Handoff

- Recommended prompt: `<task-packet, fix-implementer, tdd prompt, verification-sentinel, manual>`
- Owner: `<agent, person, or unassigned>`
- Dependencies:
  - `<task id, branch, decision, credential, external runtime>`
- Next packet hint: `<follow-up work to keep separate>`
