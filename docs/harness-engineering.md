# Harness Engineering

Use this page when the installed commands feel like separate helper scripts.
The installed kit is an agent harness: it shapes what agents see, what tools
they can use, where they write, how evidence is captured, and where humans
review the result.

This is the target-repo view. `repo-contract-kit` owns the installed surfaces
that make the harness executable inside this repository. Generated prompts,
schemas, and policies arrive through explicit `repo-contract-kit` updates; this
target repo does not need to clone or understand a workflow-source checkout.

## Installed Harness Components

| Component | Installed path or command | What it shapes | Evidence or gate |
| --- | --- | --- | --- |
| Startup packet | `make agent-start` | initial repo context, changed files, ADRs, docs impact, kit/version state, receipt template | `.agent-workflows/runs/<id>/session-start.json` |
| Goal/area contract | `make goal-check`, `.agent-workflows/area-contracts.json` | changed-file alignment with declared repo goal and local path contracts | JSON/text report with `aligned`, `extends`, `conflict`, and `unknown` states |
| Backlog source contract | `make backlog-status`, `make backlog-check`, `make agent-next` | selected backlog source, mirrors, open counts, next item, dirty state, active task state | JSON/text status and strict backlog check |
| Working rhythm | `docs/working-rhythm.md`, `make workflow-help` | orient, review, scope, execute flow | target repo operator can find the next command |
| Permission policy | `.agent-workflows/agent-permission-policy.json` | read-only review, untrusted PR, browser research, and write-worker boundaries | receipt trust-profile fields and review-run validation |
| Research runner | `make agent-research-*` | bounded source-specific research before backlog, ADR, design, or task-packet proposals | research brief, source report templates, synthesis artifacts |
| Task packet | `make agent-task-packet`, `schemas/task-packet.schema.json` | story context, non-goals, allowed files, protected files, goal alignment, validation, exact docs and release metadata surfaces, docs impact, risk, approval state | task packet JSON or Markdown handoff |
| Agent preflight | `make agent-preflight`, `make agent-doctor` | dirty-state startup blockers, task/worktree state, sidecar availability, local attribution, and safe recovery commands | text/JSON report, strict failure, optional sidecar receipt |
| Agent state ledger | `make agent-state-ledger` | read-only index of checkout dirt, task metadata/worktrees, leases, active overlaps, local attribution, sidecar receipt categories, finalizer/readiness/final receipt evidence, automation handoff/baseline receipts, self-heal receipts, closeout state, and unresolved blockers | JSON/text report with `target_repo_writes=false`, `sidecar_writes=false`, latest receipt provenance, and deterministic next safe commands |
| Branch/PR readiness | `make agent-branch-readiness` | whole-branch or PR evidence before PR update, merge queue, auto-merge, or branch-protection governance | JSON/text report with local git, docs-impact and waiver state, changelog/version, optional CI/check input, receipt/review disposition, task readiness references, `target_repo_writes=false`, `sidecar_writes=false`, and `network_calls=false` |
| Task status | `make agent-task-status` | active local tasks, worktrees, dirty or stale metadata, unknown scopes, overlaps, owner/session/thread/automation attribution, heartbeat, lease expiry, linked receipts | status text or JSON/strict failure |
| Task readiness | `make agent-task-ready` | one task worktree's actual changed files, declared scope, goal-check status, base-branch freshness, dirty-primary baseline drift, receipt/docs-impact evidence, and overlap with other active tasks | ready/not-ready text or JSON gate |
| Task finalizer | `make agent-task-finalize` | one terminal task close path across dirty-primary baseline guard, readiness, lifecycle metadata, final status, and closeout preview | local finalizer receipt plus lifecycle/status/closeout JSON |
| Automation handoff | `make agent-automation-handoff` | recurring backlog/research automation running in disposable linked worktrees | sidecar patch and JSON receipt, primary-checkout guard, original-baseline compare, and original-cleanliness guard |
| Guarded self-heal | `make agent-self-heal` | explicit generated-state recovery without source cleanup, stash/reset, or task-worktree removal | preview report by default, apply-only sidecar before/after receipt, target/sidecar write paths |
| Task lifecycle | `make agent-task-finish`, `make agent-task-block`, `make agent-task-abandon`, `make agent-task-heartbeat`, `make agent-task-prune` | close or refresh local task metadata without touching product files | metadata lifecycle events and optional final receipt link |
| Task cleanup | `make agent-task-cleanup`, `make agent-task-closeout` | existing flat/nested task-worktree layout and finished sibling-worktree retention | dry-run inventory, explicit nested move action, guarded closeout removal |
| Task worktree | `make agent-task-prepare TASK=<id> SCOPE=<paths>` | isolated branch and sibling worktree for write-capable agents, with optional `DIRTY_PRIMARY_BASELINE=1` baseline capture for pre-existing primary dirt | task packet, receipt template, in-flight metadata |
| Session receipt | `make agent-receipt-verify`, receipt schema | commands, tests, skipped checks, docs impact, findings, disposition | strict receipt validation |
| Docs contract | `make docs-check`, `scripts/check_doc_impact.py` | documentation impact for source, workflow, config, API, and operations changes | pass/fail docs-impact output |
| Docs explainer | `make agent-docs-explain`, `scripts/docs_explain.py` | local README/docs/policy files before waiver or docs-patch decisions | cited JSON/text snippets and a ready local prompt, with no target, sidecar, model, or network writes/calls |
| Instruction hygiene | `make agent-docs-lint` | concise, safe, non-stale agent-facing instructions | instruction lint warnings or failures |
| Instruction diet | `make agent-instruction-diet` | no-write proposals for moving bulky or duplicated agent-facing detail into scoped owner surfaces | JSON/text audit with recommendation categories and offload targets |
| Token budget | `make agent-token-budget` | estimated context footprint for agent-facing files | JSON/text report and optional strict budget failure |
| Changelog proposal | `make agent-changelog-update` | release-note proposal/check flow derived from docs-impact and versioning context without mutating target-owned version files | JSON/text proposal with candidate changelog text, required state, and next commands |
| Version gate | `make version-check`, `make version-bump` | target repo release-impact accounting | SemVer/changelog checks |
| Kit provenance | `make kit-status`, `make kit-explain` | installed kit version, prompt snapshot, managed-file status, ownership boundary | status output and manifest metadata |

## Quality Questions

For any installed harness change, answer these before calling it done:

1. Which agent behavior does this installed surface shape?
2. What local artifact proves it ran or was followed?
3. What failure mode does it prevent or expose?
4. Does the change belong in `repo-contract-kit` or this target repo?
5. Which local command verifies the change?

## Ownership Boundary

Start in `repo-contract-kit` when changing:

- installed Make targets
- target-repo scripts
- managed templates
- workflow prompt or schema snapshots
- installed area-contract config/schema
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

- include active sibling-task context inside task packets and receipts so
  workers keep seeing the coordination picture after handoff
- add token-budget and context-economy metrics once the source workflow defines
  what context is protected, required, or optional
