# Harness Engineering

Use this page when the installed commands feel like separate helper scripts.
The installed kit is an agent harness: it shapes what agents see, what tools
they can use, where they write, how evidence is captured, and where humans
review the result.

This is the target-repo view. The companion `agent-workflow-kit` repo owns the
canonical prompts, schemas, policies, and source-side harness design.
`repo-contract-kit` owns the installed surfaces that make that design executable
inside this repository.

## Installed Harness Components

| Component | Installed path or command | What it shapes | Evidence or gate |
| --- | --- | --- | --- |
| Startup packet | `make agent-start` | initial repo context, changed files, ADRs, docs impact, kit/version state, receipt template | `.agent-workflows/runs/<id>/session-start.json` |
| Working rhythm | `docs/working-rhythm.md`, `make workflow-help` | orient, review, scope, execute flow | target repo operator can find the next command |
| Permission policy | `.agent-workflows/agent-permission-policy.json` | read-only review, untrusted PR, browser research, and write-worker boundaries | receipt trust-profile fields and review-run validation |
| Research runner | `make agent-research-*` | bounded source-specific research before backlog, ADR, design, or task-packet proposals | research brief, source report templates, synthesis artifacts |
| Task packet | `make agent-task-packet`, `schemas/task-packet.schema.json` | allowed files, protected files, validation, docs impact, risk, approval state | task packet JSON or Markdown handoff |
| Task status | `make agent-task-status` | active local tasks, worktrees, dirty or stale metadata, unknown scopes, overlaps | status text or JSON/strict failure |
| Task cleanup | `make agent-task-cleanup` | existing flat and nested task-worktree layout | dry-run inventory and explicit nested move action |
| Task worktree | `make agent-task-prepare TASK=<id> SCOPE=<paths>` | isolated branch and sibling worktree for write-capable agents | task packet, receipt template, in-flight metadata |
| Session receipt | `make agent-receipt-verify`, receipt schema | commands, tests, skipped checks, docs impact, findings, disposition | strict receipt validation |
| Docs contract | `make docs-check`, `scripts/check_doc_impact.py` | documentation impact for source, workflow, config, API, and operations changes | pass/fail docs-impact output |
| Instruction hygiene | `make agent-docs-lint` | concise, safe, non-stale agent-facing instructions | instruction lint warnings or failures |
| Version gate | `make version-check`, `make version-bump` | target repo release-impact accounting | SemVer/changelog checks |
| Kit provenance | `make kit-status`, `make kit-explain` | installed kit version, prompt snapshot, managed-file status, ownership boundary | status output and manifest metadata |

## Quality Questions

For any installed harness change, answer these before calling it done:

1. Which agent behavior does this installed surface shape?
2. What local artifact proves it ran or was followed?
3. What failure mode does it prevent or expose?
4. Does the source belong in `agent-workflow-kit`, `repo-contract-kit`, or this
   target repo?
5. Which local command verifies the change?

## Ownership Boundary

Start in `agent-workflow-kit` when changing:

- prompt wording
- persona behavior
- workflow schemas
- task-packet or receipt contract source
- research prompt design
- regression fixture concepts
- source-side harness design

Start in `repo-contract-kit` when changing:

- installed Make targets
- target-repo scripts
- managed templates
- installer/update behavior
- installed docs
- docs-contract checks
- instruction linting
- task-worktree execution

Start in this target repo when changing:

- product code
- target-specific docs
- target-owned Makefile behavior
- local overrides
- repo-specific version notes

## Next Safe Improvements

The harness map points to three practical follow-ups:

- add merge-readiness checks that compare actual changed files with declared
  task scope, docs impact, receipt validity, branch freshness, and active
  overlaps
- include active sibling-task context inside task packets and receipts so
  workers keep seeing the coordination picture after handoff
- add token-budget and context-economy metrics once the source workflow defines
  what context is protected, required, or optional
