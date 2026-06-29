# Agent Instruction Hygiene

Agent-facing instructions should route agents to the right local source of
truth. They should not become a second copy of every policy, runbook, design
decision, or backlog item.

## Budget Rule

`make agent-docs-lint` reads `.agent-workflows/instruction-budgets.json` and
warns when root or tool-specific instruction files grow past their configured
line or rule-bullet budgets.

Keep the default budgets warning-only until the repository has calibrated them.
Repos that want stricter governance can set an entry's `severity` to `error`.

## Promotion Rule

Add a durable rule to an agent-facing instruction file only when it is one of
these:

- a stable repository invariant
- a safety boundary
- a command or local check agents must run because it gates local safety or quality
- a short route to a scoped contract, runbook, ADR, or generated report

If the rule is repeatable and machine-checkable, prefer a JSON contract, script,
or Make target. If it is contextual or temporary, keep it in a task packet,
backlog item, ADR, or run-specific receipt instead of `AGENTS.md`.

## Routing Pattern

Use `AGENTS.md` as the index:

- review behavior routes to `REVIEW.md`
- documentation impact routes to `doc-contract.json` and
  `docs/documentation-contract.md`
- permissions route to `.agent-workflows/agent-permission-policy.json`
- tool/network limits route to `docs/ops/agent-tool-network-allowlist.md`
- instruction-size limits route to `.agent-workflows/instruction-budgets.json`
- run evidence routes to the local receipt under `.agent-workflows/runs/`

When adding a new feature, add the smallest route needed in `AGENTS.md` and put
the detailed contract beside the checker or workflow that owns it.
