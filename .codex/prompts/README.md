# Prompt Index

Use these prompts as the workflow library for `agent-workflow-kit`: portable
multi-agent review, learning, targeted research, remediation, TDD, and
verification workflows.

The prompt content is tool agnostic. Codex can read it from `.codex/prompts/`,
but AmpCode, Claude Code, Aider, Cline, or a manual reviewer can use the same
Markdown files directly from the checkout.

## Core Flow

- `multi-agent-repo-review.md`: Orchestrates repo mapping, reviewer dispatch, and review boundaries.
- `codebase-learning-comments.md`: Uses subagents to understand docs, ADRs, and code before adding learner-friendly comments.
- `review-synthesis.md`: Merges persona outputs into one ranked action plan.
- `task-packet.md`: Converts backlog items, issues, accepted findings, or broad requests into executable work packets.
- `task-worktree-cleanup.md`: Plans safe cleanup for flat and nested task worktrees without deleting useful work.
- `fix-planner.md`: Converts accepted findings into scoped implementation batches.
- `fix-implementer.md`: Applies a selected batch without widening scope.
- `verification-sentinel.md`: Validates claims, tests, and residual risk after remediation.
- `research/`: Targeted source-specific research workflows for backlog, review, architecture, design, ADR, risk, and task-packet discovery.
- `policies/review-risk-classifier.md`: Deterministic changed-path risk routing for reviewer selection.
- `policies/read-only-reviewer-sandbox.md`: Default mutation and evidence boundary for reviewer personas.
- `policies/local-private-review.md`: Data-boundary guidance for private/local review modes.
- `policies/browser-research-agent.md`: Account-safety policy for browser-based source collection.
- `tdd/`: Test-first and executable-spec prompt set for feature work, bug fixes, refactors, contracts, invariants, and test-quality review.

## Persona Reviewers

The machine-readable reviewer registry is `personas/manifest.json`. Use it to
keep reviewer scopes narrow, read-only by default, and capped to high-signal
findings.

- `personas/doc-code-delta.md`: Finds drift between docs and implementation.
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
- `templates/agent-brief.md`: Fill-in brief for launching a focused reviewer.
- `templates/task-packet.md`: Fill-in template for backlog-to-work handoff.
- `schemas/session-receipt.schema.json`: Local run receipt schema for
  commands, docs impact, TDD evidence, findings, and final disposition.
- `schemas/review-synthesis.schema.json`: Machine-readable synthesis schema for
  ranked findings, remediation batches, human decisions, rejected suggestions,
  and final disposition.
- `schemas/task-packet.schema.json`: Machine-readable task packet schema for
  scope, acceptance criteria, validation, docs impact, risk, and approval state.
- `schemas/research-brief.schema.json`: Machine-readable brief for bounded
  source-specific research dispatch.
- `schemas/research-source-report.schema.json`: Machine-readable evidence report
  from one source-specific research agent.
- `schemas/research-synthesis.schema.json`: Machine-readable synthesis of
  research reports into proposed backlog, review, design, ADR, risk, or
  task-packet outputs.
- `schemas/persona-manifest.schema.json`: Validator schema for the persona
  manifest.
- `schemas/review-risk.schema.json`: Machine-readable risk classifier output
  schema.

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

For understanding a repo as a learner, run `codebase-learning-comments.md` instead of the defect-review flow.

For targeted discovery, run `research/research-brief.md`, dispatch source
agents from `research/source-*.md`, and synthesize with
`research/research-synthesis.md` before proposing backlog or design changes.

For implementing accepted changes test-first, use `tdd/README.md` to choose the right executable-spec prompt.

Run `python3 scripts/classify_review_risk.py --working-tree` before broad
review dispatch when the script is available. Use the result to decide whether
the default reviewer set is enough or whether security, API/data, dependency,
runtime, or frontend specialists should be added.
