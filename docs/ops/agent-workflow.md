# Agent Workflow Operations

This repository is set up for local-first agentic development. The installed
workflow files are intended to work from a normal shell and from local coding
agents such as Codex, AmpCode, Claude Code, Aider, or Cline.

## Local Commands

Use these commands before committing agent-generated or agent-assisted work:

```bash
make workflow-help
make agent-start
make goal-check
make agent-context-bundle
make agent-state-ledger
make agent-branch-readiness
make kit-status
make kit-explain
make agent-next
make agent-preflight
make agent-self-heal
make backlog-status
make backlog-check
make docs-check
make docs-freshness
make docs-as-tests
make agent-docs-lint
make agent-instruction-diet
make agent-docs-localize
make agent-docs-explain
make agent-docs-propose
make agent-changelog-update
make agent-research-plan
make agent-research-run RESEARCH_SOURCE=github
make agent-research-synthesize
make agent-research-to-task-packet
make agent-task-packet
make agent-task-packet-from-backlog BACKLOG_ID=<id>
make agent-task-prepare TASK=<id> SCOPE=<paths>
make agent-task-heartbeat TASK=<id>
make agent-task-finalize TASK=<id> TASK_RECEIPT=<path>
make agent-task-finish TASK=<id> TASK_RECEIPT=<path>
kit closeout-plan --json
make agent-token-budget
make agent-receipt-verify
make agent-verify
make version-check
```

`make workflow-help` prints the four-move rhythm: orient, review, scope, and
execute. Use `docs/working-rhythm.md` as the human-facing entrypoint when the
command list feels too wide.
Use `docs/harness-engineering.md` when you need to see which installed surfaces
shape agent behavior and which local artifacts verify them.

`make agent-verify` is the default local gate. It runs the available
documentation and agent-instruction checks for the installed profile.

`make docs-freshness` checks documentation truth surfaces that path-based
docs-impact cannot prove: local Markdown links, documented `make` targets,
script references, and schema references. `make docs-check` runs this gate after
basic docs lint/build/generate steps and before docs-impact coverage. Set
`DOCS_REQUIRE_SEMANTIC=1 DOCS_SEMANTIC_RECEIPT=<path>` when a change needs an
explicit doc-code semantic review receipt.
The `doc-contract.json` `docs_freshness.historical_paths` scope treats ADRs,
audits, archives, and changelog history as time-bound records for command,
script, and schema reference checks while still checking local links. Add
target-specific history with `docs_freshness.extra_historical_paths`; use
`docs_freshness.exclude_paths` only for Markdown that should be skipped
entirely.

`make docs-as-tests` is an experimental explicit gate for repos that install the
`docs-as-tests` profile and maintain `.agent-workflows/docs-as-tests.json`. It
checks declared local OpenAPI operation, response-status, schema-property, and
JSON key assertions while preserving the older method/path assertion format. It
refuses missing config, invalid JSON, unsupported assertion kinds, network URLs,
command-like input, missing local artifacts, and missing or ambiguous selectors.
It is not part of `make docs-check`, and it does not scrape prose, run fenced
code, call hosted models, use GitHub APIs, or start services.

`make agent-docs-lint` also checks `.agent-workflows/instruction-budgets.json`
so agent-facing instruction files stay small enough to route context instead of
duplicating every rule in `AGENTS.md`.

`make agent-instruction-diet` is the no-write follow-up when lint warnings or
operator review suggest instruction bloat. It reports recommendation categories,
evidence, and offload targets without editing `AGENTS.md`, runtime adapters, or
prompt files.

`make agent-token-budget` estimates token footprint for agent-facing context
files such as `AGENTS.md`, `REVIEW.md`, `.agent-workflows/**/*.md`, and
`.codex/prompts/**/*.md`. It reports by default; set `TOKEN_BUDGET_STRICT=1`
after adding `.agent-workflows/token-budgets.json` or accepting the default
budgets as a hard gate.
The optional `private-context` profile installs `.agent-context/` for ignored
local context examples only. Default token-budget and docs checks do not read
ignored private context files. Do not store secrets, tokens, cookies, passwords,
private URLs, account identifiers, customer data, personal messages, medical or
financial data, or proprietary snippets that should not leave the machine there.
Review and redact local context before sharing it with hosted models, browser
tools, GitHub comments, pull requests, issues, external tickets, or chat tools.

`make agent-start` is the lowest-friction session entrypoint. It writes an
ignored packet under `.agent-workflows/runs/` containing the agent brief,
machine-readable startup context, latest ADR context, discovery check results,
recommended prompts/personas, kit version context, target repo version context,
task-start freshness, goal-check summary, and a receipt template. The freshness
section reports global kit metadata, target install metadata, repo cleanliness,
backlog source, and safe update modes. Its selected policy is `report-only`;
dry-run, auto-update-clean, and maintenance modes are described as next steps
but are not applied by startup. Discovery check failures are recorded as
warnings so inherited or messy repos can still be reviewed.

`make goal-check` maps current changed files to
`.agent-workflows/area-contracts.json`. Each changed file reports `aligned`,
`extends`, `conflict`, or `unknown`; unmatched paths stay explicit unknowns so
agents do not infer ownership from broad documentation.

`make agent-context-bundle` emits a bounded startup or handoff bundle that
combines dirty state, backlog/next work, task status, docs impact, goal check,
token-budget totals, sidecar paths, and readiness hints. Use
`CONTEXT_BUNDLE_JSON=1` for machine-readable output. Truncated sections add
explicit omission records so compact context does not hide missing evidence.

`make agent-state-ledger` emits a read-only local ledger across checkout dirt,
task metadata/worktrees, leases, active overlaps, final receipts, sidecar
receipt categories, automation handoff/baseline receipts, self-heal receipts,
finalizer receipts, closeout preview state, unresolved blockers/warnings, and
next safe commands. Use `STATE_LEDGER_JSON=1` for machine-readable output. It
reports `target_repo_writes=false` and `sidecar_writes=false`; it is not a
cleanup, closeout, finalizer, automation handoff, self-heal apply, or receipt
writer.

`kit closeout-plan --json` translates the ledger, task status, dirty checkout,
receipt, and closeout preview evidence into a completion decision. Run it after
validation and before the final handoff. If `can_claim_done=false`, report the
`completion_state`, `claim_blockers`, and `next_action` instead of saying the
work is done. Use `--strict` when the shell command should fail until closeout
is clean.

`make agent-branch-readiness` emits a no-write branch-or-PR readiness report for
the point just before a human considers PR update, merge queue, auto-merge, or
branch-protection governance. Use `BRANCH_READY_JSON=1` for machine-readable
output, `BRANCH_READY_CHECKS_JSON=<path>` for an explicit local CI/check export,
`BRANCH_READY_RECEIPT=<path>` for strict receipt validation, and
`BRANCH_READY_REVIEW_DISPOSITION_JSON=<path>` for local review-disposition
evidence. Required checks whose state is pending, failed, skipped, missing, or
unknown block readiness; advisory checks become warnings. Missing docs-impact
coverage blocks unless an explicit `No docs needed:` reason is supplied through
`BRANCH_READY_NO_DOCS_NEEDED`. The command references `agent-task-ready` when a
prepared task matches the branch, but it does not replace that per-task gate and
does not call GitHub, comment, approve, label, enqueue, merge, or edit branch
protection.

For GitHub branch protection, use this local report as owner-reviewed evidence,
not as a hosted status publisher. GitHub branch protection can require status
checks before merge, and GitHub merge queues rerun required checks against the
latest target branch plus queued changes. Map the layers explicitly:

- Local required evidence: `make agent-task-ready`, `make docs-check`,
  `make version-check`, and
  `make agent-branch-readiness BRANCH_READY_JSON=1`.
- Imported required or advisory check state: pass
  `BRANCH_READY_CHECKS_JSON=.agent-workflows/local-checks.json`.
- Hosted required checks: configure them in GitHub or the CI provider, not in
  repo-contract-kit.
- Queue authority: a human or hosted GitHub workflow decides whether to add,
  remove, or merge a PR.

Example `checks-json`:

```json
{
  "checks": [
    {"name": "docs-check", "required": true, "state": "passed"},
    {"name": "unit", "required": true, "state": "passed"},
    {"name": "flaky-e2e", "advisory": true, "state": "failed"}
  ]
}
```

Required checks block readiness unless passing; advisory checks become warnings.
If GitHub merge queue is enabled and GitHub Actions provides required checks,
GitHub documents that those workflows need the `merge_group` event as well as
normal PR triggers. repo-contract-kit does not publish GitHub statuses, comment,
approve, label, enqueue/dequeue, merge, edit branch protection, or read
credentials.

`make kit-status` shows the installed kit version, source ref, selected profiles,
selected runtime adapters, workflow prompt snapshot ref/hash, manifest status,
managed-file cleanliness, and target repo version.
For update management, prefer the global CLI:

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
```

`make kit-explain` prints the ownership boundary for installed kit files. Use it
when the repo's root `Makefile` or installed scripts look like project code.
`kit update --all --dry-run` previews registered enrolled target repos from the
local kit registry. `kit update --all --apply` may update clean registered
targets and skips dirty, missing, or no-longer-enrolled targets. Use
`kit target import --root <root> --dry-run` to seed existing primary repos;
agent-worktree and archive paths are excluded by default. Use `kit worktree
audit` and `kit worktree prune --dry-run` for disposable task worktrees.
The target repo owns the root `Makefile`; the kit-owned targets live in
`.doc-contract-kit/make/repo-contract.mk` and are exposed by including that
fragment.

When the global CLI is unavailable, `make kit-status
KIT=/path/to/kit` compares against a local checkout and
`make kit-update KIT=/path/to/kit` updates local kit-managed files
from that checkout. Clean managed files are replaced. Customized managed files
are preserved and proposed replacements are written under
`.doc-contract-kit/updates/`. Update plans and reports include `read_next`
entries for the target repo instructions, installed workflow docs, and kit
changelog; read them before accepting proposed replacements.
Use `docs/upgrade-flow.md` for the full target-repo checklist. It keeps root
`AGENTS.md` in place, separates metadata-only migration from managed-file
updates, and treats proposed replacements as review artifacts rather than
automatic copy instructions.
`kit update --json` applies the same managed update and returns machine-readable
write paths. Use `kit update --dry-run --json` or `kit update-plan --json` when
you need a non-mutating plan.
When `update-plan` reports missing or outdated profile/config metadata, run
`make kit-migrate-config KIT=/path/to/kit` to apply only the
metadata schema migration. That command updates the installed kit receipt and
manifest markers without rewriting target-owned files, managed files, or
customized managed-file conflict baselines.
Pass `RUNTIME_ADAPTERS=claude-code,github-copilot` when adding or keeping thin
managed runtime adapters such as `CLAUDE.md` or
`.github/copilot-instructions.md`.

`make kit-refresh KIT=/path/to/kit` is the legacy local-checkout
equivalent of refreshing first, then running the same safe managed update. Use
`kit-update` directly when the user explicitly wants to install from an unpushed
local kit checkout.

Target repos should not manage workflow-source checkouts. Ordinary maintenance
stays on the global `kit setup/status/update/doctor` commands above.

For repo-external agent work, call the source checkout's
`scripts/repo_contract_kit.py` with `--repo <path>`. Use `sidecar-init` to create
the external state directory, or pass `--write-sidecar` to `orient`,
`review-plan`, `task-packet`, or `verify` so run artifacts land under
`${XDG_STATE_HOME:-~/.local/state}/repo-contract-kit/` instead of this repo.
`make agent-docs-explain` is the local read-only bridge for docs-policy Q&A:
it scans README/docs/policy files, returns cited paths, headings, and snippets,
and emits a prompt a human or local agent can use before requesting
`/waive-docs`, `/add-docs`, or docs-patch work. It does not write target files,
sidecar files, `VERSION`, or `CHANGELOG.md`, and it does not call hosted models
or the network.
`make agent-docs-propose` uses the same sidecar pattern for docs proposal JSON,
Markdown, and patch artifacts, so missing-docs follow-up can be reviewed without
dirtying the target checkout.
`make agent-changelog-update` derives release-note proposals and check results
from docs-impact context without writing `VERSION` or `CHANGELOG.md`; use
`CHANGELOG_UPDATE_CHECK=1` to fail when release-note work appears required but
`CHANGELOG.md` is not part of the changed files.

`make agent-task-packet` points the agent at the task-packet prompt. Use it when
a backlog row, issue, accepted review finding, external planning item, or broad
human request needs to become scoped executable work before implementation
starts. Task packets should carry `goal_alignment` from `goal-check`, including
explicit unknowns when no area contract matches the proposed scope. They should
also expand compact source rows with a story block, explicit non-goals,
acceptance, validation, exact docs and release metadata surfaces, docs-impact,
and risk before any write-capable handoff.

`make backlog-status` reports the selected backlog source, mirrors, open/done
counts, warnings, and the next open item. `make backlog-check` fails when the
source is missing, malformed, or has duplicate stable ids. `make agent-next`
combines backlog state, dirty working tree state, and active task metadata so a
returning agent can identify the next safe handoff. `make agent-state-ledger`
is the broader index to run when multiple receipts or task states may be
unresolved; it carries local attribution and latest receipt provenance where
available, uses explicit `unknown` when metadata is missing, and points to the
next safe command without mutating state.
`make agent-preflight` and
its alias `make agent-doctor` diagnose dirty-state startup blockers, registered
worktrees, task metadata, sidecar availability, and concrete recovery commands.
Use `PREFLIGHT_JSON=1` for machine output, `PREFLIGHT_STRICT=1` to fail when
blockers are present, and `PREFLIGHT_WRITE_SIDECAR=1` to store the report as a
sidecar receipt without writing target repo files. JSON output includes a
local-only attribution object for dirty checkout, sibling-worktree,
missing-worktree, active-task, and blocked automation-receipt state when local
metadata or receipts provide it; otherwise the source is explicit `unknown`.
Use
`make agent-task-packet-from-backlog BACKLOG_ID=<id>` to turn one selected row
into a machine-readable task packet scaffold. The generated scaffold includes a
default operator story and explicit non-goals so the backlog mirror can stay
compact while the executable packet carries enough context to implement safely.

`make agent-self-heal` is the explicit recovery path for low-risk generated
state. It previews by default and reports planned actions without writing. Set
`SELF_HEAL_APPLY=1` only after reviewing the plan. Apply mode can initialize
the sidecar and quarantine stale terminal task metadata that no longer points
at an existing worktree, or a stale `.agent-workflows/tasks/.prepare.lock` whose
PID is not running. It writes a sidecar before/after receipt with
`target_repo_writes` and `sidecar_writes`. The command refuses unrelated tracked
source changes unless an exact generated path is supplied with
`SELF_HEAL_ALLOW_PATHS=<path>`, and it reports unrecognized untracked files
outside the generated-state allowlist without deleting them. It does not stash,
reset, clean source files, or remove task worktrees; use `agent-task-closeout`
for finished sibling worktree removal.

`make agent-research-plan` creates a read-only targeted-research packet under
`.agent-workflows/runs/`. Use `make agent-research-run
RESEARCH_SOURCE=github|arxiv|hacker-news|official-docs` to create source-agent
prompts and source-report templates, then `make agent-research-synthesize` and
`make agent-research-to-task-packet` to turn accepted evidence into proposed
backlog, review, design, architecture, ADR, risk, or task-packet handoffs.
These commands require the research prompts from the `review-prompts` profile.
If those prompts are missing, the command should fail before writing artifacts.

`make agent-task-status` shows the active local task registry, registered git
worktrees, dirty task worktrees, missing or stale task metadata, unknown scopes,
declared scope overlaps, task leases, owner labels, owner/session/thread ids,
automation ids, and linked receipts.
Run it before starting a new write-capable task and again before handoff so each
worker has the current parallel-job picture. Set `TASK_STATUS_STRICT=1` to fail
on coordination hazards such as missing worktrees, unknown active scopes,
expired leases, untracked task worktrees, or overlapping active scopes.

`make agent-task-ready` is the local handoff gate for one prepared task
worktree. Run it from the task worktree before opening or updating a PR, or
before handing the branch back for merge. It compares actual changed files to
the declared task scope, reports goal-check status, checks base-branch
freshness, validates receipt and docs-impact evidence in strict mode, and
blocks overlap with other in-progress task scopes. Unknown goal-check areas are
warnings; paths declared as `conflict` are readiness blockers. Set
`BASE_REF=<branch>` when the default branch cannot be inferred correctly and
`TASK_READY_JSON=1` for machine-readable output.
Run `make agent-branch-readiness BRANCH_READY_JSON=1` after per-task readiness
when the whole branch or PR also needs explicit local CI/check, receipt, review,
docs waiver, and changelog/version disposition in one JSON object.

`make agent-task-finalize TASK=<id> TASK_RECEIPT=<path>` closes one prepared
task by running readiness, lifecycle update, final task status, and closeout
preview in one command. Finish mode requires a receipt and readiness unless
`TASK_FINALIZE_SKIP_READY=1` is set. Use `TASK_FINALIZE_ACTION=block|abandon`
for terminal non-passing states, `TASK_FINALIZE_JSON=1` for the full local
finalizer receipt, and `TASK_FINALIZE_CLOSEOUT_APPLY=1` only when eligible
worktree removal should be applied.

`make agent-automation-handoff` is the recurring-automation handoff gate for
backlog and research edits made in a disposable linked worktree. It writes a
sidecar patch and JSON receipt, blocks primary-checkout runs by default, can
verify `AUTOMATION_HANDOFF_ORIGINAL_ROOT=<path>` stayed clean, and refuses
changed files outside backlog/research paths. Use it before cleanup when
accepted automation output must survive without dirtying the live checkout.
If the original checkout is already dirty before the run starts, first capture
`AUTOMATION_HANDOFF_CAPTURE_ORIGINAL_BASELINE=1 AUTOMATION_HANDOFF_JSON=1` and
preserve the emitted receipt path. The final handoff can then pass
`AUTOMATION_HANDOFF_ORIGINAL_BASELINE=<path>` to block only changes introduced
after that baseline. Use `AUTOMATION_HANDOFF_ALLOW_ORIGINAL_DRIFT=1` only when
the original-checkout drift is known and accepted.

`make agent-task-cleanup` audits the local task-worktree layout. It is read-only
by default and highlights nested task pools, dirty worktrees, missing metadata,
and flat target paths. To flatten nested worktrees after reviewing the plan, run
`make agent-task-cleanup TASK_CLEANUP_MOVE_NESTED=1 TASK_CLEANUP_APPLY=1`.

`make agent-task-closeout` previews finished sibling task worktrees that are
eligible for removal. A candidate must be a registered task worktree in the
default sibling pool, have terminal task metadata, have durable final receipt
evidence unless `TASK_CLOSEOUT_ALLOW_NO_RECEIPT=1` is set, be clean, have a
known scope, avoid active scope overlap, and have a task branch already merged
into primary `HEAD`. Dirty, missing, unregistered, nested, unknown-scope,
missing-receipt, active-overlap, and unmerged cases stay blocked for manual
inspection. Set `TASK_CLOSEOUT_APPLY=1` only after reviewing the dry run. Use
`TASK_CLOSEOUT_KEEP=<n>` or `TASK_CLOSEOUT_OLDER_THAN_DAYS=<n>` to retain
recent finished worktrees.

`make agent-task-prepare TASK=<id> SCOPE=<paths>` creates a write-capable task
branch and sibling worktree, writes a task packet and receipt template under
`.agent-workflows/tasks/` in that worktree, and records local in-flight metadata
under `.agent-workflows/tasks/` in the main checkout. It refuses a dirty main
checkout by default and now reports the exact dirty entries plus recovery
commands. Set `TASK_PREPARE_JSON=1` for machine-readable blocker output,
`DIRTY_PRIMARY_BASELINE=1` only when the operator accepts preserving
pre-existing checkout dirt, and `OVERLAP=block` to stop when declared scope
overlaps another active task. Dirty-primary baseline mode records tracked and
untracked entries, counts, changed files, HEAD, and a deterministic
content-sensitive state hash in the task metadata and receipt template; later
`agent-task-ready` / `agent-task-finalize` runs block if the primary checkout
changed after that baseline. Because the task worktree starts from HEAD,
prepare blocks dirty-baseline runs when untracked files overlap the declared
task scope; commit or park those files first. `ALLOW_DIRTY=1` remains a legacy
alias for the same baseline mode. Keep the default `OVERLAP=warn` while
triaging.
The metadata records run id, owner/session id, optional `TASK_OWNER_LABEL`,
`TASK_THREAD_ID`, and `TASK_AUTOMATION_ID`, heartbeat timestamp, lease expiry,
active sibling tasks, and overlap warnings. Long-running workers should
call `make agent-task-heartbeat TASK=<id>` periodically, and use
`make agent-task-ready` before PR update or merge handoff. Close work with
`make agent-task-finish TASK=<id> TASK_RECEIPT=<path>`, `make agent-task-block
TASK=<id>`, or `make agent-task-abandon TASK=<id>`. `make agent-task-prune`
previews closed metadata removal only; use `agent-task-closeout` when finished
sibling worktree folders should be reclaimed.

For Codex desktop or terminal use, run `agent-task-prepare` from the primary
checkout, then change into the printed worktree path in the same terminal. Do
not run it from inside an existing task worktree; the command refuses that path
so task worktrees stay in one flat sibling pool. For parallel work, repeat the
prepare step from the primary checkout with a different task id and scope. After
setup, agents edit only their task worktrees; the primary checkout is used for
`agent-task-status` and coordination checks.

`make agent-receipt-verify` validates the latest local review receipt in strict
mode. Set `RECEIPT=path/to/receipt.json` to validate a specific run. Strict mode
requires completed local evidence rather than a shape-only receipt.

`.agent-workflows/agent-permission-policy.json` defines local trust profiles
such as `read-only-review`, `untrusted-pr`, `browser-research`, and
`write-worker`. Read-only review runners use this policy to keep file, git,
browser, network, MCP, and CI permissions explicit.

`docs/ops/slash-command-grammar.md` specifies the future PR slash-command
grammar for docs-impact, docs waivers, docs review, docs additions, and
changelog updates. The commands are a future-interface contract only until a
local or hosted adapter implements them; they do not override the permission
policy or create implicit write approval.

`make version-check` validates the target repo `VERSION` file when the
versioning profile is installed. `make agent-changelog-update` proposes or
checks changelog work from docs-impact output without mutating target-owned
version files. Use `make version-bump BUMP=patch|minor|major` only when the
accepted change needs a target repo version bump.

## Workflow Files

- `AGENTS.md` defines repo-local operating rules for coding agents.
- `REVIEW.md` defines the review contract.
- `docs/working-rhythm.md` defines the everyday orient, review, scope, execute
  flow.
- `docs/harness-engineering.md` maps installed commands, policies, receipts,
  task worktrees, docs gates, and kit provenance as harness components.
- `.agent-workflows/` contains tool-agnostic workflow guidance and receipt
  schemas.
- `.agent-workflows/agent-permission-policy.json` contains local trust profiles
  for review, untrusted PRs, browser research, and scoped write workers.
- `docs/ops/slash-command-grammar.md` specifies the future PR slash-command
  grammar and permission boundaries for docs-impact, waiver, docs-review,
  docs-addition, and changelog-update requests.
- `.agent-workflows/instruction-budgets.json` contains warning-only size and
  rule-count budgets for agent-facing instruction files.
- `.agent-workflows/token-budgets.json`, when present, overrides default token
  footprint budgets for `make agent-token-budget`.
- `.agent-context/`, when the opt-in private-context profile is installed,
  contains checked-in README/example guidance and ignores real local context
  files by default. It is not a secret store, runtime adapter, or memory system.
- `.agent-workflows/tasks/` contains ignored local in-flight task metadata for
  worktree-per-task write workers. `make agent-task-status` reads this registry
  and compares it to `git worktree list`. Lifecycle targets update the same
  metadata so active, done, blocked, and abandoned task state stays visible.
- `.codex/prompts/` contains reusable prompts. The files can be read by other
  agents or used manually; they are not limited to Codex.
- `schemas/research-brief.schema.json`,
  `schemas/research-source-report.schema.json`, and
  `schemas/research-synthesis.schema.json` define targeted research artifacts.
- `schemas/area-contracts.schema.json` defines the local repo goal and
  path-contract config consumed by `make goal-check`.
- `schemas/task-packet.schema.json` defines the machine-readable handoff from
  backlog item to agent task.
- `.github/workflows/docs.yml` is an optional hosted adapter for repos that can
  use GitHub Actions. Local verification does not depend on it.
- `.github/workflows/docs-contract-comment.yml` is an optional hosted adapter
  that comments docs-contract status, policy links, and next actions on pull
  requests. It checks out the base repository policy files and does not replace
  local `make docs-check` verification.
- `.github/workflows/agent-review-readonly.yml` is an optional hosted adapter
  for fork-safe read-only review artifact generation. It uses
  `AGENT_TRUST_PROFILE=untrusted-pr` and does not grant write credentials.
- `.doc-contract-kit/manifest.json` records managed files and hashes for safe
  local updates.
- `.doc-contract-kit/make/repo-contract.mk` is the managed make target fragment
  included by the target-owned root `Makefile`.
- `VERSION`, `CHANGELOG.md`, and `docs/versioning.md` define local target repo
  versioning when the versioning profile is installed.

## Locked-Down Repositories

For older on-prem Git servers or work environments without hosted CI, keep the
local commands as the source of truth. The GitHub workflow file may be ignored,
removed, or replaced with a local server equivalent if the repository cannot use
GitHub Actions.

If the workflow, scripts, build gates, or operational runbooks change, update
this document or the relevant file under `docs/ops/`, `docs/deploy/`, or
`docs/runbooks/`.
