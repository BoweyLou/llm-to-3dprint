# Working Rhythm

Use this page when the command list feels wider than the workflow.

## Stack Map

This repository has local guardrails installed by `repo-contract-kit`. The
prompts under `.codex/prompts/` are a generated workflow snapshot, and normal
work should happen from this checkout with local commands.

For the harness view of these commands, use `docs/harness-engineering.md`.

For setup and maintenance, use the global CLI:

```bash
kit setup
kit status
kit update --dry-run
kit update
kit doctor
kit closeout-plan
```

`kit setup` is the target enrollment command. It is intentionally a normal CLI
subcommand, not a workspace script named `kit-setup`.

This target repo owns day-to-day work, local docs/version decisions, and any
explicit local overrides, including the root `Makefile`. Target repos do not
need to fetch or understand the workflow-source checkout at runtime.

## Four Moves

### 1. Orient

Use this when returning to the repo or starting a new agent session.

```bash
kit start --json
kit start --no-update --json
make agent-start
make goal-check
make kit-status
make agent-next
make agent-context-bundle
make agent-state-ledger
make agent-branch-readiness
```

`kit start --json` chooses the route from repo state and reports
`local_update`; in installed target repos it may apply already-local,
local-safe managed-file updates. Use `kit start --no-update --json` when
startup must be guaranteed no-write. `agent-start` writes an ignored local
packet with changed files, docs impact,
latest ADR context, kit/version state, review risk, goal-check summary,
recommended prompts, and a receipt template. `goal-check` maps changed files to
`.agent-workflows/area-contracts.json` and leaves unmatched paths as explicit
unknowns. `kit-status` explains the installed kit version, prompt snapshot,
managed-file status, and target repo version.
`agent-next` combines backlog status, dirty working tree state, and active task
metadata so the next handoff is based on the current repo rather than memory.
`agent-context-bundle` composes those local signals with docs impact,
goal-check, task-status, token-budget, sidecar, and readiness hints into a
bounded report with explicit omissions for startup or handoff.
`agent-state-ledger` is the local read-only state index: it summarizes checkout
dirt, task metadata/worktrees, leases, active overlaps, final receipts, sidecar
receipt categories, closeout preview state, unresolved blockers/warnings, and
the next safe commands without cleaning, closing out, finalizing, handing off,
or writing sidecar receipts.
`agent-branch-readiness` is the local branch-or-PR readiness aggregate. It
checks git cleanliness, base/head refs, docs-impact and explicit
`No docs needed:` waiver state, changelog/version evidence, task readiness when
prepared task metadata is available, task-status hazards, optional local
CI/check JSON, and optional receipt or review-disposition JSON. It reports
`target_repo_writes=false`, `sidecar_writes=false`, and `network_calls=false`;
it is not a merge, approval, PR comment, merge-queue, auto-merge, or
branch-protection action. Use the merge-governance examples in
`docs/ops/agent-workflow.md` to map local readiness evidence to hosted required
checks, branch protection, and merge queues without giving repo-contract-kit
GitHub authority.

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
make goal-check
make backlog-status
make backlog-check
make agent-task-packet-from-backlog BACKLOG_ID=<id>
```

The packet should name story context, scope, goal alignment, non-goals, exact
docs and release metadata surfaces, docs impact, validation, risk, and approval
state before implementation starts.
Use `backlog-status` and `backlog-check` when the task should start from a repo
backlog source. `agent-task-packet-from-backlog` turns one selected row into a
machine-readable task packet scaffold with a default operator story and explicit
non-goals, without implementing it.

### 4. Execute

Use this after the task is approved for write-capable work.

```bash
make agent-task-status
make agent-preflight
make agent-state-ledger
make agent-branch-readiness
make agent-self-heal
make agent-task-cleanup
make agent-task-prepare TASK=<id> SCOPE=<paths>
make agent-task-ready
make agent-automation-handoff
make agent-task-heartbeat TASK=<id>
make agent-task-finalize TASK=<id> TASK_RECEIPT=<path>
make agent-task-finish TASK=<id> TASK_RECEIPT=<path>
make agent-task-closeout
kit closeout-plan --json
make agent-verify
```

`agent-task-status` shows active local tasks, registered git worktrees, dirty
task worktrees, stale or missing metadata, unknown scopes, declared scope
overlaps, and local attribution such as owner label, session/thread id, and
automation id when metadata provides it. `agent-state-ledger` gives a broader
no-write index of unresolved task, receipt, sidecar, automation, readiness,
finalizer, self-heal, and closeout state with attribution and latest receipt
provenance, then recommends deterministic next commands such as
`agent-self-heal`, `agent-task-status`, `agent-task-ready`,
`agent-task-finalize`, `agent-task-closeout`, or `agent-automation-handoff`.
Run `kit closeout-plan --json` after validation and before a final handoff. If
it reports `can_claim_done=false`, do not claim the work is done; report the
`completion_state`, `claim_blockers`, and `next_action`.
Use `git_worktree_state` for real Git dirt and `kit_managed_state` for kit
template or proposal review; managed proposals are not Git worktree dirt, but
they still need an accept, reject, or receipt decision before closeout.
`agent-branch-readiness` sits after those local task gates when a whole branch
or PR needs one JSON answer before a human updates PR state or hosted branch
governance.
`agent-preflight` or `agent-doctor` gives a startup-blocker view of
the current checkout dirt, sibling worktrees, task metadata, sidecar state, and
recommended recovery commands, including attribution for dirty-checkout,
sibling-worktree, missing-worktree, active-task, and blocked automation-receipt
state where local metadata or receipts exist. Use `PREFLIGHT_STRICT=1` when a
job should fail closed on blockers or `PREFLIGHT_WRITE_SIDECAR=1` when the
diagnosis needs a durable external receipt. `agent-task-cleanup` audits existing flat and nested
task worktrees and can move nested worktrees into the flat pool only when
`TASK_CLEANUP_APPLY=1` is set. `agent-self-heal` previews guarded generated-state
repairs and is no-write by default. Set `SELF_HEAL_APPLY=1` only after reviewing
the plan; apply can initialize sidecar state and quarantine stale generated task
metadata or stale prepare locks with a sidecar receipt. It is not a source
cleanup, stash, reset, unrecognized-untracked delete, or task-worktree removal
command. `agent-task-prepare` creates a task branch and
sibling worktree, writes task artifacts, and records local in-flight metadata
with run id, owner/session/thread/automation attribution, heartbeat, lease
expiry, sibling task context, and overlap warnings. Set `TASK_OWNER`,
`TASK_OWNER_LABEL`, `TASK_SESSION_ID`, `TASK_THREAD_ID`, or
`TASK_AUTOMATION_ID` when the local operator or automation identity is known.
If the main checkout is dirty, the prepare blocker lists dirty
entries and safe recovery commands; set `TASK_PREPARE_JSON=1` for machine output
or `DIRTY_PRIMARY_BASELINE=1` only when preserving existing dirt is intentional.
That mode records the primary checkout's dirty entries, counts, HEAD, changed
files, and state hash in task metadata and receipt scaffolds. Because the task
worktree starts from HEAD, prepare blocks dirty-baseline runs when untracked
files overlap the declared task scope; commit or park those files first.
`ALLOW_DIRTY=1` remains a legacy alias for the same baseline mode.
`agent-task-ready` then checks actual changed files against declared scope,
reports goal-check status, validates strict receipt/docs-impact evidence,
verifies base branch freshness, blocks primary-checkout drift after a dirty
baseline, and blocks overlap with other in-progress tasks before PR update or
merge handoff. The worker edits in the
task worktree, refreshes the
lease with `agent-task-heartbeat` during long work, checks `agent-task-status`
before handoff, then captures validation evidence and closes the task with
`agent-task-finalize`, or directly with `agent-task-finish`,
`agent-task-block`, or `agent-task-abandon`. `agent-task-finalize` combines
readiness, lifecycle update, final status, and closeout preview in one local
receipt; set `TASK_FINALIZE_CLOSEOUT_APPLY=1` only when removal should be
applied. After review or merge, `agent-task-closeout` previews finished sibling
worktrees that are safe to remove; set `TASK_CLOSEOUT_APPLY=1` only after
reviewing the dry run.
For recurring automation that edits backlog or research files in a disposable
worktree, run `agent-automation-handoff` before cleanup so accepted edits are
preserved as a sidecar patch and JSON receipt while the original checkout stays
clean. If the original checkout starts dirty, capture an original-baseline
receipt at the start and pass it back during handoff so only new original
mutations block.

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
make goal-check
make kit-status
make agent-next
make kit-explain
make docs-freshness
make docs-as-tests
make agent-docs-propose
make agent-changelog-update
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
make backlog-status
make agent-task-status
make agent-task-prepare TASK=<id> SCOPE=<paths>
```

For kit maintenance:

```bash
kit status
kit update --dry-run
kit update
kit target import --root /path/to/repos --dry-run
kit target list --json
kit update --all --dry-run
kit worktree audit --root /path/to/repos --json
kit worktree prune --root /path/to/repos --dry-run
kit doctor
kit closeout-plan
make kit-explain
```

Use `kit start` for opportunistic local-safe kit maintenance and
`kit update --dry-run` before explicit managed-file updates. Remote/global
updates stay explicit through `kit update --global`. Update plans and reports
include a `read_next` list; read those docs before merging proposed replacements
from `.doc-contract-kit/updates/`.
Successful `kit setup` and `kit update` runs register enrolled targets for
`kit update --all --dry-run`. Use `kit target import --root <root> --dry-run`
to seed existing primary repos from install receipts; agent-worktree and archive
paths are excluded by default. Batch apply needs `--apply` and skips dirty,
missing, or no-longer-enrolled targets. Use `kit worktree audit` and
`kit worktree prune --dry-run` for disposable task worktrees, separately from
primary repo updates.
Use `docs/upgrade-flow.md` for the full safe update sequence, including
metadata-only migration and conflict review. Kit updates keep root `AGENTS.md`
in place and preserve customized managed files.
Pass `RUNTIME_ADAPTERS=claude-code,github-copilot` only when this repo should
manage thin runtime-specific instruction files. Keep canonical repo rules in
`AGENTS.md` and scoped docs.

When the global CLI is unavailable, use the legacy local Make fallback:

```bash
make kit-status KIT=/path/to/kit
make kit-migrate-config KIT=/path/to/kit
make kit-update KIT=/path/to/kit
make kit-refresh KIT=/path/to/kit
```

Target repos should not need workflow-source checkout management. If a maintainer
needs to refresh workflow source, do that from the `repo-contract-kit` source
workspace rather than turning normal target maintenance into a source-management
workflow.

The root `Makefile` is target-owned. The kit make targets live in
`.doc-contract-kit/make/repo-contract.mk`; include that fragment from the root
`Makefile` when this repo wants `make agent-start`, `make kit-status`, and the
other installed commands. When an older repo updates, a clean old kit-managed
`Makefile` can migrate automatically to the bridge. Customized Makefiles are
preserved and receive proposed bridge files under `.doc-contract-kit/updates/`.
If the root `Makefile` already defines kit targets directly, `kit-status`
reports that as local maintenance rather than a missing command surface.

`docs-freshness` checks local links plus documented `make`, script, and schema
references. `docs-check` includes this gate so documentation can fail when it
points at commands or files that no longer exist, not only when a docs-impact
path is missing.
Historical paths from `doc-contract.json` still receive local link checks, but
their documented `make`, `scripts/*.py`, and schema references are treated as
time-bound history rather than current executable truth. Use
`docs_freshness.extra_historical_paths` for target-specific history, and reserve
`docs_freshness.exclude_paths` for Markdown that should be skipped entirely.

`docs-as-tests` is separate from `docs-check`. It is for the experimental
`docs-as-tests` profile and only reads explicit assertions from
`.agent-workflows/docs-as-tests.json`. The supported checks prove declared local
OpenAPI operations, response statuses, schema properties, and JSON config keys,
and refuse missing config, invalid JSON, network URLs, command-like inputs,
unsupported kinds, missing local artifacts, and ambiguous selectors.

When an agent should keep run artifacts out of this repo, use the external
`repo_contract_kit.py` CLI with `--repo <path>`. `sidecar-init` creates the
external state directory, and `--write-sidecar` on `orient`, `review-plan`,
`task-packet`, or `verify` stores packets, plans, and receipts under
`${XDG_STATE_HOME:-~/.local/state}/repo-contract-kit/` without writing
`.agent-workflows/` into the target checkout.
Use `make agent-docs-propose` when the right next step is a reviewable docs
patch artifact rather than direct documentation edits. The proposal is written
under the sidecar with JSON, Markdown, and a `docs.patch` scaffold.
Use `make agent-docs-explain` first when the question is what local docs policy
actually says. It emits deterministic source citations and a local prompt
without writing target files, sidecar files, `VERSION`, or `CHANGELOG.md`; if
the scanned docs do not match, it says so instead of inventing a waiver answer.
Use `make agent-changelog-update` when docs-impact or versioning context needs
a release-note proposal or check. It reports candidate changelog text and
version-file state without writing `VERSION` or `CHANGELOG.md`.

## Change Routing

| Change | Start in |
| --- | --- |
| Installed commands, templates, scripts, manifests, update behavior, docs-contract checks, kit make fragment | `repo-contract-kit` |
| Target-specific docs, version notes, local overrides, product behavior | this target repo |
| Workflow prompt wording or schemas | refresh through `repo-contract-kit` |
