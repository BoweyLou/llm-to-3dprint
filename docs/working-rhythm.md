# Working Rhythm

Use this page when the command list feels wider than the workflow.

## Stack Map

This repository has local guardrails installed by `repo-contract-kit`. The
prompts under `.codex/prompts/` are a vendored snapshot of the companion
`agent-workflow-kit` prompt library, but normal work should happen from this
checkout with local commands.

For the harness view of these commands, use `docs/harness-engineering.md`.

The stack has three layers:

- `agent-workflow-kit` owns canonical prompts, personas, schemas, research
  workflows, and generated adapter source.
- `repo-contract-kit` owns installer profiles, managed templates, update
  behavior, target-repo scripts, and the installed make target fragment.
- this target repo owns day-to-day work, local docs/version decisions, and any
  explicit local overrides, including the root `Makefile`.

When the prompt source changes, target repos receive it through a vendored
snapshot in a `repo-contract-kit` update. Target repos do not need to fetch
`agent-workflow-kit` at runtime.

## Four Moves

### 1. Orient

Use this when returning to the repo or starting a new agent session.

```bash
make agent-start
make kit-status
```

`agent-start` writes an ignored local packet with changed files, docs impact,
latest ADR context, kit/version state, review risk, recommended prompts, and a
receipt template. `kit-status` explains the installed kit version, prompt
snapshot, managed-file status, and target repo version.

### 2. Review

Use this when the goal is understanding, review, or finding risk before edits.

```bash
make agent-run-review AGENT=manual
```

Manual mode writes reviewer prompts and local JSON artifacts under
`.agent-workflows/runs/`. If the runner is not useful for the current tool, read
the prompts under `.codex/prompts/` directly.

### 3. Scope

Use this when a backlog row, issue, accepted finding, or broad human request
needs to become executable work.

```bash
make agent-task-packet
```

The packet should name scope, non-goals, docs impact, validation, risk, and
approval state before implementation starts.

### 4. Execute

Use this after the task is approved for write-capable work.

```bash
make agent-task-status
make agent-task-cleanup
make agent-task-prepare TASK=<id> SCOPE=<paths>
make agent-verify
```

`agent-task-status` shows active local tasks, registered git worktrees, dirty
task worktrees, stale or missing metadata, unknown scopes, and declared scope
overlaps. `agent-task-cleanup` audits existing flat and nested task worktrees
and can move nested worktrees into the flat pool only when
`TASK_CLEANUP_APPLY=1` is set. `agent-task-prepare` creates a task branch and
sibling worktree, writes task artifacts, and records local in-flight metadata.
The worker edits in the task worktree, checks `agent-task-status` before
handoff, then validation evidence is captured before review.

When using multiple Codex terminals, run the prepare command from the primary
checkout in each terminal, then `cd` into the worktree path printed for that
task. Do not prepare a new task from inside an existing task worktree; that
creates confusing nested pools and is rejected by the launcher. You keep using
the same Codex terminal after the `cd`; the primary checkout is only the
coordination point.

## Common Paths

For quick orientation:

```bash
make workflow-help
make agent-start
make kit-status
make kit-explain
```

For read-only review:

```bash
make agent-start MODE=drift
make agent-run-review AGENT=manual
make agent-receipt-verify
```

For approved implementation:

```bash
make agent-task-packet
make agent-task-status
make agent-task-prepare TASK=<id> SCOPE=<paths>
```

For kit maintenance:

```bash
make kit-status KIT=/path/to/repo-contract-kit
make kit-update KIT=/path/to/repo-contract-kit
make kit-refresh KIT=/path/to/repo-contract-kit
make kit-explain
```

Use `kit-update` when the local kit checkout is already at the version you want.
Use `kit-refresh` when the first step should be a clean fast-forward pull of the
kit checkout. Keep kit updates explicit. Normal validation should not update
installed guardrails automatically. Update plans and reports include a
`read_next` list; read those docs before merging proposed replacements from
`.doc-contract-kit/updates/`.

The root `Makefile` is target-owned. The kit make targets live in
`.doc-contract-kit/make/repo-contract.mk`; include that fragment from the root
`Makefile` when this repo wants `make agent-start`, `make kit-status`, and the
other installed commands. When an older repo updates, a clean old kit-managed
`Makefile` can migrate automatically to the bridge. Customized Makefiles are
preserved and receive proposed bridge files under `.doc-contract-kit/updates/`.
If the root `Makefile` already defines kit targets directly, `kit-status`
reports that as local maintenance rather than a missing command surface.

When an agent should keep run artifacts out of this repo, use the external
`repo_contract_kit.py` CLI with `--repo <path>`. `sidecar-init` creates the
external state directory, and `--write-sidecar` on `orient`, `review-plan`,
`task-packet`, or `verify` stores packets, plans, and receipts under
`${XDG_STATE_HOME:-~/.local/state}/repo-contract-kit/` without writing
`.agent-workflows/` into the target checkout.

## Change Routing

| Change | Start in |
| --- | --- |
| Prompt wording, personas, schemas, research prompts, TDD prompts, synthesis prompts | `agent-workflow-kit` |
| Installed commands, templates, scripts, manifests, update behavior, docs-contract checks, kit make fragment | `repo-contract-kit` |
| Target-specific docs, version notes, local overrides, product behavior | this target repo |
