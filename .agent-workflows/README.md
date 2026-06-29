# Local Agent Workflows

These workflows are local-first and agent-tool agnostic. They do not require
GitHub Actions, hosted CI, or a specific coding assistant.

Use them from AmpCode, Codex, Claude Code, Aider, Cline, another local agent, or
a human terminal session.

For the operator mental model, start with `docs/working-rhythm.md`. This file
is the mechanics reference for local packets, review-run artifacts, permissions,
and installed workflow files.

## Start an Agent

Give the agent this brief from the repository root:

```bash
make agent-start
```

The command writes an ignored local packet under `.agent-workflows/runs/` with
an agent brief, startup context, latest ADR context, recommended prompts and
personas, kit version context, target repo version context, and a receipt
template.

To generate a concrete review run folder from that packet:

```bash
make agent-run-review AGENT=manual
make agent-run-review AGENT=manual AGENT_TRUST_PROFILE=untrusted-pr
```

Manual mode writes one prompt per selected persona plus placeholder JSON
artifacts under the latest `.agent-workflows/runs/<id>/review-run/` directory.
Use it when you want to paste prompts into AmpCode, Codex, Claude Code, or a
human review session yourself.

When Amp is installed and signed in, execute the same review through Amp CLI
execute mode:

```bash
make agent-run-review AGENT=amp
```

The Amp adapter uses `amp --execute --stream-json`, saves raw JSONL output,
extracts structured findings, runs synthesis, and checks that git status did
not change during each read-only reviewer run.

Review runs load `.agent-workflows/agent-permission-policy.json`. The default
profile is `read-only-review`; use `AGENT_TRUST_PROFILE=untrusted-pr` for
fork-origin or otherwise untrusted changes so the run is artifact-only and has
no PR mutation, account mutation, secret, or write-back expectation.
The `make agent-start` packet also includes a `review_risk` block with the
detected tier, trust profile, trigger rules, and policy docs.

For manual startup, use:

```text
Read AGENTS.md, REVIEW.md, and .agent-workflows/README.md.
Then follow .agent-workflows/repo-review.md in bootstrap mode.
Use the installed personas and prompts under .codex/prompts/ where useful.
Start by running make agent-verify and make agent-docs-localize.
Produce a findings backlog before editing code.
```

For ongoing work after the first bootstrap review, change `bootstrap mode` to
`drift mode`, `pull-request mode`, `release-gate mode`,
`learning-comments mode`, or `test-first mode`.

## Files

- `REVIEW.md`: local review rules and evidence bar.
- `.agent-workflows/repo-review.md`: focused local repo-review workflow.
- `.agent-workflows/tdd-red-green-receipt.md`: TDD evidence format.
- `.agent-workflows/agent-permission-policy.json`: explicit local trust
  profiles for read-only reviewers, untrusted PRs, browser research, and scoped
  write workers.
- `docs/ops/agent-tool-network-allowlist.md`: human-readable shell, browser,
  network, MCP, Git, and CI boundary for agentic review.
- `.agent-workflows/schemas/session-receipt.schema.json`: JSON receipt schema.
- `.agent-workflows/schemas/safe-output.schema.json`: safe agent output schema.
- `schemas/review-synthesis.schema.json`: JSON schema for synthesized review
  findings and remediation batches.
- `schemas/task-packet.schema.json`: JSON schema for backlog-to-work handoff.

## Local Commands

Run these from the repository root:

```bash
make workflow-help
make agent-start
make agent-run-review AGENT=manual
make kit-status
make kit-explain
make agent-next
make backlog-status
make backlog-check
make docs-check
make docs-freshness
make agent-docs-lint
make agent-docs-localize
make agent-task-packet
make agent-task-packet-from-backlog BACKLOG_ID=<id>
make agent-task-status
make agent-task-prepare TASK=<id> SCOPE=<paths>
make agent-task-heartbeat TASK=<id>
make agent-task-finish TASK=<id> TASK_RECEIPT=<path>
make agent-task-closeout
make agent-token-budget
make agent-receipt-verify
make version-check
```

If your repo does not use `make`, run the scripts directly:

```bash
python3 scripts/check_doc_impact.py --working-tree
python3 scripts/agent_start.py --mode bootstrap
python3 scripts/agent_review_run.py --mode bootstrap --agent manual
python3 scripts/repo_contract_kit.py agent-next --repo .
python3 scripts/repo_contract_kit.py backlog-status --repo .
python3 scripts/repo_contract_kit.py backlog-check --repo .
python3 scripts/verify_agent_receipt.py --strict
python3 scripts/kit_status.py
python3 scripts/kit_status.py --explain
python3 scripts/check_docs_freshness.py
python3 scripts/lint_agent_docs.py --strict-paths
python3 scripts/localize_doc_impact.py --working-tree --json
python3 scripts/check_token_budget.py
python3 scripts/version.py check
```

Use `make agent-task-packet` when a backlog item, Keryx task, issue, review
finding, or human request needs scope, acceptance criteria, docs impact, risk,
and approval state before implementation.

Use `make backlog-status` and `make backlog-check` when the repo has a
portable Markdown or CSV backlog source. `backlog-status` prints the selected
source and candidate paths that exist in the current checkout. Use
`make agent-next` when returning to a dirty checkout because it combines the
selected backlog source, active task metadata, and working-tree state.

Use `make docs-freshness` for executable documentation checks beyond
path-based docs impact: local Markdown links, documented Make targets, script
references, schema references, and optional semantic receipt requirements.
Use `make agent-token-budget` to report agent-facing context footprint.

Long-running write workers should refresh task leases with
`make agent-task-heartbeat TASK=<id>` and close task metadata with
`make agent-task-finish`, `make agent-task-block`, or
`make agent-task-abandon`.

Use `make agent-task-closeout` after final receipt evidence is durable and the
task branch is reviewed or merged. It previews clean finished sibling worktrees
by default; set `TASK_CLOSEOUT_APPLY=1` only after reviewing the candidates.

## Updates And Versioning

The installed `.doc-contract-kit/manifest.json` records which files are
kit-managed and which files are target-owned. To update from a newer local kit
checkout, run:

```bash
make kit-update KIT=/path/to/kit
```

The updater only replaces clean managed files. Customized files are preserved and
reported under `.doc-contract-kit/updates/`.

The root `Makefile` belongs to this target repo. Kit make targets live in
`.doc-contract-kit/make/repo-contract.mk`; include that file from the root
`Makefile` when this repo wants the installed make commands. Run
`make kit-explain` or `python3 scripts/kit_status.py --explain` for the update
path when an older install has a customized Makefile.

When `VERSION` and `CHANGELOG.md` exist, they belong to this target repo. Agents
should run `make version-check` for behavior/API/config/runtime changes and only
run `make version-bump BUMP=patch|minor|major` when a version bump is part of
the accepted task.

## Tool-Neutral Rule

Native folders like `.codex/prompts/`, `.cursor/rules/`, or `CLAUDE.md` are
optional adapters. The local workflow must still be understandable from this
folder, `AGENTS.md`, `REVIEW.md`, and the scripts.

## Prompt Source

The prompts under `.codex/prompts/` are copied into this repo by
`repo-contract-kit` so local agents can work without fetching another
repository. The canonical prompt library lives in
the public `agent-workflow-kit` repository; refresh this repo by rerunning the
installer from a newer `repo-contract-kit` checkout.
