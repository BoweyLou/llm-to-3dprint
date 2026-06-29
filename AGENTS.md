# AGENTS.md

## Purpose

This repository uses docs-as-code. Documentation is part of the definition of done.

If you change code, you must consider whether documentation also needs to change.

## Agent self-start

If asked to review, understand, clean up, or formalize this repo, start here:

1. Read `AGENTS.md`, `REVIEW.md`, and `.agent-workflows/README.md`.
2. Run `kit start --json` to choose the route from current repo state and apply
   any already-local, local-safe kit update. Use `kit start --no-update --json`
   when a no-write startup payload is required.
3. Run `make agent-start` to create a local startup packet under
   `.agent-workflows/runs/`.
4. Run `make goal-check` to map changed files to declared area contracts before
   inferring scope from broad docs.
5. Inspect `make kit-status` and `make version-status` output when available so
   you know the installed kit version, workflow prompt snapshot, and target repo
   version.
6. Inspect `docs/ops/agent-tool-network-allowlist.md` and the selected trust
   profile in `.agent-workflows/agent-permission-policy.json` before running
   review agents, browser research, or CI adapters.
7. Inspect `docs/ops/agent-instruction-hygiene.md` before adding new
   agent-facing rules so `AGENTS.md` stays an index instead of a context dump.
8. Follow `.agent-workflows/repo-review.md` in the requested mode. Use
   `bootstrap` for the first review of an inherited or newly instrumented repo.
9. Use the installed personas and prompts under `.codex/prompts/` where useful.
10. Run `make agent-verify` and `make agent-docs-localize` before proposing code
   changes.
11. Produce a findings backlog before editing code.
12. If work starts from a backlog item, issue, accepted finding, or broad human
   request, run `make agent-task-packet` and convert one selected item into
   scoped executable work before implementation.
13. For write-capable implementation, run
    `make agent-task-prepare TASK=<id> SCOPE=<paths>` before editing.

`kit start --json` decides the route and reports `local_update` status.
`make agent-start` is the installed target-repo packet lane, and
`make agent-context-bundle` is the compact handoff context lane.
`kit status --json` separates `git_worktree_state` from `kit_managed_state`;
use the first for real Git dirt and the second for managed template/proposal
review. Run `kit closeout-plan --json` before claiming write work is done.

The prompts under `.codex/prompts/` are local copies installed by
`repo-contract-kit`. Do not fetch prompts from another repo during normal work
unless the user explicitly asks you to refresh the kit.

## Where documentation lives

- `README.md` — high-level overview and getting started
- `docs/working-rhythm.md` — human-facing operator rhythm and mental model
- `docs/` — project documentation
- `docs/adr/` — architecture decision records
- `doc-contract.json` — repository-specific documentation impact rules
- `.github/pull_request_template.md` — PR checklist and change classification

## Documentation contract

If you change any of the following, update the relevant docs in the same change:

- public behavior
- API
- CLI commands or flags
- config or environment variables
- schema or data contracts
- deployment or operations workflow
- architecture or major design decisions

If no documentation update is needed, explicitly say why in the PR summary.
Use the exact marker `No docs needed: <reason>`.

## Versioning contract

If this repo has `VERSION`, `CHANGELOG.md`, and `docs/versioning.md`, treat
`VERSION` as the local SemVer source of truth. Run `make version-check` when a
change affects behavior, APIs, CLI, configuration, schemas, operations, or
user-visible output. Use `make version-bump BUMP=patch|minor|major` only when a
version bump is part of the accepted change scope, then replace the changelog
TODO with a useful summary.

`VERSION` and `CHANGELOG.md` are target-owned files. Do not overwrite them from
kit templates during updates.

## Kit updates

Use `make kit-status` to inspect installed kit, prompt snapshot, profiles,
manifest cleanliness, and target repo version. `kit start` may apply only
local-safe managed-file updates from the already-local tool checkout; it does
not fetch remote/global updates. Prefer the global CLI for explicit update
management:

```bash
kit setup
kit status
kit update --dry-run
kit update
kit target import --root /path/to/repos --dry-run
kit target list --json
kit update --all --dry-run
kit worktree audit --root /path/to/repos --json
kit worktree prune --root /path/to/repos --dry-run
kit doctor
```

If the user asks to set up, inspect, update, or diagnose the kit, check
`command -v kit` and run the requested `kit` subcommand from the target repo;
do not search for a workspace script named `kit-setup`.

Use `make kit-update KIT=/path/to/kit` or
`make kit-refresh KIT=/path/to/kit` only when the global CLI is
unavailable or a specific local checkout is required. Preserve customized
managed files and review `.doc-contract-kit/updates/` before accepting proposed
replacements. Use `kit update --all --apply` only after reviewing the batch
dry-run; dirty registered targets are skipped. Use `kit target import` only for
primary repos, with agent-worktree and archive paths excluded by default. Use
`kit worktree audit` and `kit worktree prune --dry-run` for disposable task
worktrees instead of enrolling them globally. Use `make kit-explain` when
ownership is unclear.

For external agent artifacts, use the source kit CLI with `--repo <path>`;
`sidecar-init` and `--write-sidecar` store packets, plans, and receipts outside
the target repo.
For recurring automation that edits backlog or research files from a disposable
worktree, run `make agent-automation-handoff` before cleanup. It preserves
accepted edits as a sidecar patch and receipt and blocks primary-checkout runs
by default.
Use the review-risk tier from `make agent-start` to choose the smallest safe
reviewer set. High-risk or critical changes should stay read-only until a human
accepts a scoped implementation task.

Use `make agent-task-prepare TASK=<id>` for accepted write-capable tasks from
the primary checkout, not inside an existing task worktree. Use
`make agent-task-status` before parallel work, `make agent-task-ready` before PR
or merge handoff, and preview `agent-task-cleanup` / `agent-task-closeout`
before setting their apply flags.
If `DIRTY_PRIMARY_BASELINE=1` is intentional, commit or park untracked files in
the task scope first; the task worktree is created from HEAD.

## Instruction hygiene

Keep `AGENTS.md` as a short route map. Put detailed rules in scoped contracts,
runbooks, ADRs, or checker config. `make agent-docs-lint` reads
`.agent-workflows/instruction-budgets.json` and warns when agent instruction
files become too large or too rule-heavy.

## ADR rules

Create or update an ADR when the change affects:

- architecture
- major dependencies
- service boundaries
- data flow or storage strategy
- security/privacy tradeoffs
- deployment/runtime model

Do not create ADRs for small bug fixes or routine internal refactors.

## Commands

Before finishing work, run:

- `make docs-lint`
- `make docs-build`
- `make docs-generate`
- `python3 scripts/check_doc_impact.py`
- `make version-check` when behavior or release impact changed

If these fail, fix the issue before considering the task complete.

## Important rule

Never leave generated docs stale.
Never change externally visible behavior without considering documentation impact.
