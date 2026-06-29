# Review Map

Use this artifact for large changesets when reviewers need a navigable map
before opening every file. A review map organizes evidence from local reports
and source inspection; it is not a replacement for reading the changed source,
tests, docs, ADRs, scripts, runtime config, or receipts behind any claim.

Start with `make agent-context-bundle` or an installed context bundle when available.
Record missing, stale, blocked, ambiguous, or incomplete report data as an
omission, then inspect the scoped source files needed to fill the gap.

## Source Inputs

- Review map id: `<stable id, run id, task id, or branch label>`
- Repo: `<repo path or name>`
- Diff range: `<base..head, working tree, staged diff, task branch, or explicit scope>`
- Context packet: `<path, command result, unavailable reason, or omitted>`
- Context bundle: `<path, command result, unavailable reason, or omitted>`
- Task packet: `<path, issue, backlog row, accepted finding, or none>`
- Receipts consulted:
  - `<receipt path, summary path, or none>`
- Manual inspection notes:
  - `<file, command, ADR, doc, runtime config, or reason still unknown>`

## Scope Summary And Review Objective

Objective field: `<what the review must decide>`

Change summary:
  - `<one compact fact about the diff>`

Out of scope:
  - `<files, products, behaviors, or risks intentionally not reviewed>`

Assumptions:
  - `<assumption plus source or uncertainty>`

## Changed-File Clusters

Create clusters that a reviewer can follow independently. Keep each cluster
bounded enough that a reviewer can verify the rationale without broad rereads.

```markdown
### `<cluster-id>` - `<cluster title>`

- Rationale: `<why these files belong together>`
- Owner or area: `<team, subsystem, docs area, unknown, or ambiguous>`
- Changed files:
  - `<path>` - `<role in this cluster>`
- Supporting context:
  - `<agent-context-bundle item, doc, ADR, caller, test, script, or receipt>`
- Uncertainty:
  - `<unknown ownership, incomplete context packet, generated/vendor ambiguity, or none>`
```

## Entry Points And Contracts To Inspect

Use this section as navigation, not as proof that the listed surfaces are safe.
For each item, include a path or command, why it matters, and whether it has
already been inspected.

- Entrypoints:
  - `<path or command>` - `<why it starts the behavior>`
- Public contracts:
  - `<API, CLI, prompt, schema, file format, generated adapter, or user-visible output>`
- Data and schema boundaries:
  - `<schema, migration, persisted data, fixture, payload, or state file>`
- Operational surfaces:
  - `<Make target, script, workflow, deployment, runtime config, env var, or scheduler>`
- Docs and ADRs:
  - `<doc, README, changelog, versioning note, ADR, or docs-impact evidence>`
- Scripts:
  - `<script path or command>`
- Tests:
  - `<test file, fixture, validation command, or gap>`

## Risk Hotspots And Reviewer Routing

- Risk hotspots:
  - `<risk id>` - `<paths>` - `<why this can break correctness, docs, security, runtime, or maintainability>`
- Default personas:
  - `<persona id>` - `<scope>`
- Specialist personas:
  - `<persona id>` - `<trigger or reason>`
- Personas or areas skipped:
  - `<persona/area>` - `<reason and residual risk>`

## Recommended Review Sequence

1. `<step>` - Inspect `<paths or artifacts>` to answer `<review question>`.
2. `<step>` - Inspect `<paths or artifacts>` to answer `<review question>`.
3. `<step>` - Run or inspect `<validation surface>` before accepting findings.

For each step, record the exit criterion that lets the reviewer move on without
claiming the entire changeset is reviewed.

## Validation And Evidence To Capture

- Commands:
  - `<command>` - `<expected result or why skipped>`
- Receipts or summaries to preserve:
  - `<receipt path, receipt summary path, or none>`
- Docs and ADR checks:
  - `<docs-impact, docs-freshness, ADR decision, changelog/version check, or not applicable>`
- Runtime or configuration checks:
  - `<local runtime, config parse, script dry run, or not applicable>`
- Evidence gaps:
  - `<missing test, skipped command, unavailable runtime, or blocked inspection>`

## Omissions And Uncertainty

Make omissions explicit so a reviewer can decide whether the map is enough for
triage or whether more source inspection is required.

- Skipped files:
  - `<path>` - `<reason, owner, and residual risk>`
- Unclassified paths:
  - `<path>` - `<why no cluster owns it yet>`
- Missing agent-context-bundle data:
  - `<section or field>` - `<missing, stale, blocked, ambiguous, or truncated>`
- Ambiguous ownership:
  - `<path or cluster>` - `<possible owners and what would resolve it>`
- Validation gaps:
  - `<command, test, docs check, runtime check, or receipt>` - `<why unavailable and risk>`
- Other unknowns:
  - `<question>` - `<next source to inspect>`

## Follow-Up Task-Packet Candidates

Record only work that should not be folded into the current review.

```text
title: <candidate title>
rationale: <why this should become a separate packet>
likely_scope: <paths or areas>
priority: P0 | P1 | P2 | P3 | unknown
trigger: <finding, omission, owner decision, or validation gap>
```

## Disposition

```text
map_status: draft | ready-for-review | blocked | superseded
handoff_notes: <what reviewers can trust, what they must inspect directly, and what remains unknown>
```
