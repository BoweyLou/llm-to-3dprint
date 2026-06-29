# Lite Mode

Lite mode is the smallest repo-contract-kit harness for small repositories, local-only maintenance, and low-risk documentation or implementation tasks. It keeps the operator path short while preserving deterministic escalation into standard or release-gated review when the work touches public contracts.

## Mode Matrix

| Mode | Use when | Required artifacts | Typical commands |
| --- | --- | --- | --- |
| `lite` | The repo is clean or has a narrow docs-only change, no public CLI/API/schema/config/release impact, and no active overlapping task state. | A lite task note, local validation evidence, and a final status note. | `kit status`, `kit mode-check --json`, `kit task-packet --harness-mode lite --json`, `kit verify --harness-mode lite --json` |
| `standard` | The work changes implementation behavior, spans several files, starts from a backlog/issue, or needs normal docs-impact and task-packet closeout. | Full task packet, docs-impact result, validation commands, and closeout receipt or equivalent. | `kit orient`, `kit task-packet --harness-mode standard --json`, `kit verify --harness-mode standard --json` |
| `release-gated` | The work changes public CLI/API/config/schema/contracts, install/update behavior, security/privacy policy, generated docs, `VERSION`, or `CHANGELOG.md`. | Full task packet, explicit docs and release metadata, version/check evidence, generated-doc freshness, and human-readable release summary. | `kit mode-check --mode release-gated --json`, `kit task-packet --harness-mode release-gated --json`, `make docs-freshness`, `make version-check` |

## Selection Rules

Run `kit mode-check --json` before choosing the packet size. The selector starts from `lite`, promotes to `standard` for behavioral or multi-file risk, and promotes to `release-gated` for public contract, installer, update, schema, security/privacy, generated-doc, or release metadata risk.

Humans may always choose a stricter mode. Downgrades are allowed only when no trigger for the stricter mode is present. The selector reports `selected_mode`, trigger evidence, downgrade blockers, and next commands.

## Lite Task Note

A lite task note is enough when the selector remains on `lite`. It records:

- task id, title, problem, priority, and source
- bounded scope and non-goals
- minimum validation commands
- docs-impact expectation
- escalation triggers
- final evidence location or final summary

Escalate from lite when the change touches public behavior, crosses repository ownership boundaries, adds a new dependency, changes automation or release flow, creates unclear docs impact, or fails the first validation pass for reasons outside the intended scope.

## Five-Command Happy Path

Use this path before advanced diagnostics:

1. `kit status --json`
2. `kit mode-check --json`
3. `kit task-packet --harness-mode auto --json`
4. `kit verify --harness-mode auto --json`
5. `kit update --dry-run --json`

Advanced commands remain available for migrations, automation handoffs, branch readiness, sidecar repair, and maintainer diagnostics.
