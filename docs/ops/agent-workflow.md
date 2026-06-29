# Agent Workflow Operations

This repository is set up for local-first agentic development. The installed
workflow files are intended to work from a normal shell and from local coding
agents such as Codex, AmpCode, Claude Code, Aider, or Cline.

## Local Commands

Use these commands before committing agent-generated or agent-assisted work:

```bash
make workflow-help
make agent-start
make kit-status
make kit-explain
make docs-check
make agent-docs-lint
make agent-docs-localize
make agent-research-plan
make agent-research-run RESEARCH_SOURCE=github
make agent-research-synthesize
make agent-research-to-task-packet
make agent-task-packet
make agent-task-prepare TASK=<id> SCOPE=<paths>
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

`make agent-docs-lint` also checks `.agent-workflows/instruction-budgets.json`
so agent-facing instruction files stay small enough to route context instead of
duplicating every rule in `AGENTS.md`.

`make agent-start` is the lowest-friction session entrypoint. It writes an
ignored packet under `.agent-workflows/runs/` containing the agent brief,
machine-readable startup context, latest ADR context, discovery check results,
recommended prompts/personas, kit version context, target repo version context,
and a receipt template. Discovery check failures are recorded as warnings so
inherited or messy repos can still be reviewed.

`make kit-status` shows the installed kit version, source ref, selected profiles,
vendored `agent-workflow-kit` prompt snapshot ref/hash, manifest status,
managed-file cleanliness, and target repo version. When a local kit checkout is
available, run `make kit-status KIT=/path/to/repo-contract-kit` for an explicit
`current`/`available` update signal.

`make kit-explain` prints the ownership boundary for installed kit files. Use it
when the repo's root `Makefile` or installed scripts look like project code.
The target repo owns the root `Makefile`; the kit-owned targets live in
`.doc-contract-kit/make/repo-contract.mk` and are exposed by including that
fragment.

`make kit-update KIT=/path/to/repo-contract-kit` updates local kit-managed files
from a newer local checkout. Clean managed files are replaced. Customized managed
files are preserved and proposed replacements are written under
`.doc-contract-kit/updates/`. Update plans and reports include `read_next`
entries for the target repo instructions, installed workflow docs, and source
kit changelog; read them before accepting proposed replacements.

`make kit-refresh KIT=/path/to/repo-contract-kit` first verifies that the local
kit checkout is clean, runs `git pull --ff-only`, prints the refreshed
`kit-status`, and then runs the same safe managed update. Use `kit-update`
directly when the user explicitly wants to install from an unpushed local kit
checkout.

For repo-external agent work, call the source checkout's
`scripts/repo_contract_kit.py` with `--repo <path>`. Use `sidecar-init` to create
the external state directory, or pass `--write-sidecar` to `orient`,
`review-plan`, `task-packet`, or `verify` so run artifacts land under
`${XDG_STATE_HOME:-~/.local/state}/repo-contract-kit/` instead of this repo.

`make agent-task-packet` points the agent at the task-packet prompt. Use it when
a backlog row, issue, accepted review finding, external planning item, or broad
human request needs to become scoped executable work before implementation
starts.

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
and declared scope overlaps. Run it before starting a new write-capable task and
again before handoff so each worker has the current parallel-job picture. Set
`TASK_STATUS_STRICT=1` to fail on coordination hazards such as missing
worktrees, unknown active scopes, untracked task worktrees, or overlapping
active scopes.

`make agent-task-cleanup` audits the local task-worktree layout. It is read-only
by default and highlights nested task pools, dirty worktrees, missing metadata,
and flat target paths. To flatten nested worktrees after reviewing the plan, run
`make agent-task-cleanup TASK_CLEANUP_MOVE_NESTED=1 TASK_CLEANUP_APPLY=1`.
Removal stays explicit: inspect the worktree first, then use
`git worktree remove <path>` for clean finished work.

`make agent-task-prepare TASK=<id> SCOPE=<paths>` creates a write-capable task
branch and sibling worktree, writes a task packet and receipt template under
`.agent-workflows/tasks/` in that worktree, and records local in-flight metadata
under `.agent-workflows/tasks/` in the main checkout. It refuses a dirty main
checkout by default. Set `OVERLAP=block` to stop when declared scope overlaps
another active task, or keep the default `OVERLAP=warn` while triaging.

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

`make version-check` validates the target repo `VERSION` file when the
versioning profile is installed. Use `make version-bump BUMP=patch|minor|major`
only when the accepted change needs a target repo version bump.

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
- `.agent-workflows/instruction-budgets.json` contains warning-only size and
  rule-count budgets for agent-facing instruction files.
- `.agent-workflows/tasks/` contains ignored local in-flight task metadata for
  worktree-per-task write workers. `make agent-task-status` reads this registry
  and compares it to `git worktree list`.
- `.codex/prompts/` contains reusable prompts. The files can be read by other
  agents or used manually; they are not limited to Codex.
- `schemas/research-brief.schema.json`,
  `schemas/research-source-report.schema.json`, and
  `schemas/research-synthesis.schema.json` define targeted research artifacts.
- `schemas/task-packet.schema.json` defines the machine-readable handoff from
  backlog item to agent task.
- `.github/workflows/docs.yml` is an optional hosted adapter for repos that can
  use GitHub Actions. Local verification does not depend on it.
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
