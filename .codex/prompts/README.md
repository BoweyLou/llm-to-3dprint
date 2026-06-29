# Prompt Index

Use these prompts as the workflow library for `repo-contract-kit`: portable
multi-agent review, learning, targeted research, remediation, TDD, and
verification workflows.

The prompt content is tool agnostic. Codex can read it from `.codex/prompts/`,
but AmpCode, Claude Code, Aider, Cline, or a manual reviewer can use the same
Markdown files directly from the checkout.

## Deterministic Reports First

When an installed target repo exposes compact reports, use them before broad
repo rereads. Prefer the installed `agent-context-bundle` report for startup
and handoff context, then fall back to smaller available reports such as
`agent-start`, `agent-next`, `backlog-status`, `goal-check`,
`agent-task-status`, and `agent-token-budget`.

Compact reports are routing evidence, not a waiver for required fields.
Prompts should still preserve scope, docs impact, goal alignment, validation,
closeout, receipt, and omission evidence. If a report is missing, stale,
blocked, ambiguous, or omits a required field, inspect the scoped source files
needed to resolve that gap and record the omission.
Do not copy full report bodies into prompts when a command name, status, path,
and omission summary are enough.

Review synthesis may populate optional receipt metrics for review outcome and
effort when the values are directly known from findings, dispositions, commands,
timing, token/cost reports, or explicit human review observations. Treat those
metrics as calibration evidence, not productivity proof, and omit or caveat
unknown values instead of estimating them.

## Closeout-First Startup

Implementation handoffs must carry `previous_task_state` and
`closeout_required_before_start` before work starts. The gate distinguishes
`safe-start`, `refuse-start`, and `blocker-escalation` so agents do not begin
editing on top of unresolved prior work. Safe starts need finalizer or equivalent
receipt evidence. Unsafe starts should name the exact task-status, finalizer,
closeout preview, self-heal, blocker receipt, or owner escalation needed next
without cleaning or deleting unrelated work.

## Core Flow

- `multi-agent-repo-review.md`: Orchestrates repo mapping, reviewer dispatch, and review boundaries.
- `maintainer-queue.md`: Summarizes backlog, active tasks, receipts, readiness, and owner decisions into `Active`, `Needs owner`, `Ready next`, and `Blocked` without granting mutation authority.
- `templates/review-map.md`: Organizes large changesets into changed-file
  clusters, entrypoints, contracts, risk hotspots, review sequence, validation
  evidence, omissions, and follow-up packet candidates. Use it with
  `make agent-context-bundle` or installed context bundles for navigation; it does
  not replace direct source, tests, docs, ADR, script, runtime-config, or
  receipt inspection.
- `codebase-learning-comments.md`: Uses subagents to understand docs, ADRs,
  and code before adding learner-friendly comments or producing a
  non-developer explanation note when inline comments would be noisy, with
  deterministic latest-ADR discovery, explicit no-ADR fallback evidence, and
  comment-only receipt evidence for strict validation.
- `review-synthesis.md`: Merges persona outputs into one ranked action plan.
- `task-packet.md`: Converts backlog items, issues, accepted findings, or broad
  requests into executable work packets with goal alignment, coordination
  context, previous-task closeout gates, closeout evidence requirements, and
  lightweight harness metrics when available.
- `task-worktree-cleanup.md`: Plans safe cleanup for flat and nested task worktrees without deleting useful work.
- `fix-planner.md`: Converts accepted findings into scoped implementation batches.
- `fix-implementer.md`: Applies a selected batch without widening scope.
- `verification-sentinel.md`: Validates claims, tests, and residual risk after remediation.
- `research/`: Targeted source-specific research workflows for backlog, review, architecture, design, ADR, risk, and task-packet discovery.
- `policies/review-risk-classifier.md`: Deterministic changed-path risk routing for reviewer selection.
- `policies/read-only-reviewer-sandbox.md`: Default mutation and evidence boundary for reviewer personas.
- `policies/local-private-review.md`: Data-boundary, local-model suitability,
  and escalation guidance for private/local review-only modes.
- `policies/browser-research-agent.md`: Account-safety policy for browser-based source collection.
- `tdd/`: Test-first and executable-spec prompt set for feature work, bug fixes, refactors, contracts, invariants, and test-quality review.

## Persona Reviewers

The machine-readable reviewer registry is `personas/manifest.json`. Use it to
keep reviewer scopes narrow, read-only by default, and capped to high-signal
findings.

- `personas/doc-code-delta.md`: Finds drift between docs, behavior-describing
  comments/docstrings, and implementation, with advisory labels and
  false-positive handling for comment/docstring cases.
- `personas/ai-code-slop.md`: Finds generated-looking slop, brittle shortcuts, and shallow abstractions.
- `personas/reuse-architecture.md`: Finds missed reuse, misplaced responsibilities, and architecture drift.
- `personas/dead-code.md`: Finds unused code, stale entrypoints, abandoned config, and unreachable paths.
- `personas/duplication.md`: Finds repeated logic and inconsistent copies.
- `personas/test-behavior-risk.md`: Finds weak tests, missing regression coverage, and behavior risk.
- `personas/security-privacy.md`: Finds secrets, unsafe IO, auth gaps, and privacy leaks.
- `personas/api-data-contracts.md`: Finds API, schema, migration, and data-shape drift.
- `personas/dependencies-build.md`: Finds dependency, packaging, CI, and build-system risk.
- `personas/runtime-observability.md`: Finds runtime, logging, metrics, scheduling, and deployability gaps.
- `personas/frontend-ux.md`: Finds frontend quality, accessibility, state, and UX consistency issues.

## Output Templates

- `templates/review-finding.md`: Shared finding format for reviewer outputs.
- `templates/review-map.md`: Large-changeset review navigation artifact for
  source inputs, changed-file clusters, inspection targets, risk hotspots,
  reviewer routing, review sequence, validation evidence, explicit omissions,
  and follow-up task-packet candidates.
- `templates/agent-brief.md`: Fill-in brief for launching a focused reviewer.
- `templates/task-packet.md`: Fill-in template for backlog-to-work handoff, goal alignment, active-task context, closeout evidence, and token-budget notes.
- Session receipt schema: local run receipt schema for
  commands, docs impact, TDD evidence, coordination context, optional review
  outcome and effort harness metrics, findings, and final disposition.
- Review synthesis schema: machine-readable synthesis schema for
  ranked findings, remediation batches, human decisions, rejected suggestions,
  and final disposition.
- Review-map schema: machine-readable review-map artifact schema mirroring
  `templates/review-map.md` without requiring private transcript data,
  hosted-service fields, or review-runner mutation.
- Task-packet schema: machine-readable task packet schema for
  goal alignment, scope, coordination context, harness metrics, acceptance
  criteria, validation, closeout requirements, docs impact, risk, and approval
  state.
- Research brief schema: machine-readable brief for bounded source-specific
  research dispatch.
- Research source report schema: machine-readable evidence report
  from one source-specific research agent.
- Research synthesis schema: machine-readable synthesis of research reports
  into proposed backlog, review, design, ADR, risk, or task-packet outputs.
- Persona manifest schema: validator schema for the persona manifest.
- Review risk schema: machine-readable risk classifier output schema.

## Recommended Dispatch

For a small repo, run:

1. `doc-code-delta`
2. `ai-code-slop`
3. `test-behavior-risk`
4. `reuse-architecture`

For a mature repo or release gate, add:

1. `dead-code`
2. `duplication`
3. `security-privacy`
4. `api-data-contracts`
5. `dependencies-build`
6. `runtime-observability`
7. `frontend-ux` when applicable

For understanding a repo as a learner or non-developer stakeholder, run
`codebase-learning-comments.md` instead of the defect-review flow. Use inline
comments only when they improve maintained source; use the explanation-note
output when the useful context belongs outside code. Start from existing
`agent-start` latest-ADR evidence, agent-context-bundle ADR items,
and task/operator decision references before scanning manually; when no ADR or
decision record exists, record that absence and rely only on README, docs,
tests, code, config, changelog, task context, or operator instructions for
comments and explanation notes. Strict learning-comments receipts should fill
`evidence.comment_only_verification` with the diff scope, no-behavior
assertion, reviewed paths, evidence commands, non-comment path explanations,
and any uncertainty.

For targeted discovery, run `research/research-brief.md`, dispatch source
agents from `research/source-*.md`, and synthesize with
`research/research-synthesis.md` before proposing backlog or design changes.

For maintainer queue triage, run `maintainer-queue.md` after local compact
reports and task status commands. Use it to decide what is active, what needs
an owner decision, what is ready to packetize next, and what is blocked.

For large changesets, fill `templates/review-map.md` before dispatching broad
reviewers. Start from `make agent-context-bundle` or an installed context bundle,
cluster changed files by review path, name entrypoints and contracts, and record
omissions so reviewers know where direct source inspection is still required.

For implementing accepted changes test-first, use `tdd/README.md` to choose the right executable-spec prompt.

Run `python3 scripts/classify_review_risk.py --working-tree` before broad
review dispatch when the script is available. Use the result to decide whether
the default reviewer set is enough or whether security, API/data, dependency,
runtime, or frontend specialists should be added.
