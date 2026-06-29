# AGENTS.md

## Purpose

This repository uses docs-as-code. Documentation is part of the definition of done.

If you change code, you must consider whether documentation also needs to change.

## Agent self-start

If asked to review, understand, clean up, or formalize this repo, start here:

1. Read `AGENTS.md`, `REVIEW.md`, and `.agent-workflows/README.md`.
2. Run `make agent-start` to create a local startup packet under
   `.agent-workflows/runs/`.
3. Inspect `make kit-status` and `make version-status` output when available so
   you know the installed kit version, vendored prompt snapshot, and target repo
   version.
4. Inspect `docs/ops/agent-tool-network-allowlist.md` and the selected trust
   profile in `.agent-workflows/agent-permission-policy.json` before running
   review agents, browser research, or CI adapters.
5. Inspect `docs/ops/agent-instruction-hygiene.md` before adding new
   agent-facing rules so `AGENTS.md` stays an index instead of a context dump.
6. Follow `.agent-workflows/repo-review.md` in the requested mode. Use
   `bootstrap` for the first review of an inherited or newly instrumented repo.
7. Use the installed personas and prompts under `.codex/prompts/` where useful.
8. Run `make agent-verify` and `make agent-docs-localize` before proposing code
   changes.
9. Produce a findings backlog before editing code.
10. If work starts from a backlog item, issue, accepted finding, or broad human
   request, run `make agent-task-packet` and convert one selected item into
   scoped executable work before implementation.
11. For write-capable implementation, run
    `make agent-task-prepare TASK=<id> SCOPE=<paths>` before editing so the
    worker gets an isolated branch, worktree, task packet, and receipt template.

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

Use `make kit-status` to inspect the installed kit version, source ref, vendored
`agent-workflow-kit` prompt snapshot, profiles, manifest status, managed-file
cleanliness, and target repo version. Use
`make kit-status KIT=/path/to/repo-contract-kit` when a local kit checkout is
available and you need a `current`/`available` update signal. Use
`make kit-update KIT=/path/to/repo-contract-kit` only when the user asks to
refresh the local kit files from that checkout, or
`make kit-refresh KIT=/path/to/repo-contract-kit` when the user wants to pull a
clean local kit checkout first and then update. Customized managed files must be
preserved; review proposed replacements under `.doc-contract-kit/updates/` and
read the update report's `read_next` entries before accepting them.
Use `make kit-explain` when ownership is unclear. The target repo owns the root
`Makefile`; repo-contract-kit owns `.doc-contract-kit/make/repo-contract.mk`,
which the root `Makefile` may include to expose installed kit targets.

For external agent artifacts, use the source kit CLI with `--repo <path>`;
`sidecar-init` and `--write-sidecar` store packets, plans, and receipts outside the target repo.
Use the review-risk tier from `make agent-start` to choose the smallest safe
reviewer set. High-risk or critical changes should stay read-only until a human
accepts a scoped implementation task.

Use `make agent-task-prepare TASK=<id>` for accepted write-capable tasks. Run it
from the primary checkout, not from inside an existing task worktree. It creates
a sibling worktree under a task branch with the normal Codex branch prefix,
records local in-flight metadata under `.agent-workflows/tasks/`, and warns
when declared scope overlaps another active task.

Use `make agent-task-status` before launching or handing off parallel
write-capable tasks. It compares the local task registry with `git worktree
list`, reports dirty or missing task worktrees, and surfaces unknown or
overlapping active scopes.

Use `make agent-task-cleanup` before manually cleaning old worktree folders. It
audits registered task worktrees and suggests nested-worktree moves. Only set
`TASK_CLEANUP_APPLY=1` after reviewing the dry run; use `git worktree remove`
explicitly for clean finished worktrees.

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

## Pull request expectations

Every PR must clearly state:

1. what changed
2. whether docs were updated
3. whether an ADR was added or updated
4. if no docs changed, why not

## Important rule

Never leave generated docs stale.
Never change externally visible behavior without considering documentation impact.
