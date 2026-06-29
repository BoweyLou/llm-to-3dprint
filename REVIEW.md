# REVIEW.md

This repository is reviewed locally first. Do not assume GitHub Actions,
hosted CI, or a specific coding agent is available.

## Local Review Rules

- Start from the diff or explicitly requested scope.
- Read `AGENTS.md`, `doc-contract.json`, and `docs/documentation-contract.md`
  before making findings.
- Run local commands from the checkout when available.
- Treat `scripts/check_doc_impact.py` as the local docs-impact coverage gate
  and `scripts/check_docs_freshness.py` / `make docs-freshness` as the
  executable documentation freshness gate when installed.
- Use `scripts/localize_doc_impact.py --json` to map changed source paths to
  likely docs before asking an agent to reason broadly.
- Use `scripts/lint_agent_docs.py --strict-paths` before trusting local agent
  instructions.
- Treat `docs/ops/agent-instruction-hygiene.md` and
  `.agent-workflows/instruction-budgets.json` as the guardrail against packing
  too much context into `AGENTS.md` or runtime-specific rule files.
- Use `.agent-workflows/agent-permission-policy.json` to select an explicit
  trust profile before running read-only reviewers or write-capable workers.
- Use `docs/ops/agent-tool-network-allowlist.md` to confirm allowed shell,
  browser, network, MCP, Git, and CI surfaces before running agentic review.
- Use the `review_risk` block from `make agent-start` to decide whether the
  default reviewer set is enough or specialist reviewers are required.
- Use `make agent-task-prepare TASK=<id> SCOPE=<paths>` before write-capable
  implementation work so the worker runs in a task branch and sibling worktree.
- Use `scripts/verify_agent_receipt.py --strict` before treating a JSON receipt
  as complete evidence.

## Tool-Agnostic Agent Use

Any local coding tool can use this file: AmpCode, Codex, Claude Code, Aider,
Cline, or a human reviewer. If a tool has native prompt folders, those are
optional convenience layers. The source of truth is the checked-in Markdown,
schemas, scripts, and local command output.

## Evidence Required

Every serious agent run should leave either a JSON receipt or a Markdown handoff
with:

- agent tool used
- mode: bootstrap, drift, pull-request, release-gate, learning-comments,
  test-first, or verification
- files inspected
- commands run and results
- docs-impact result
- review risk tier and selected trust profile
- TDD red/green evidence when behavior changed
- findings with priority, confidence, evidence, recommendation, and disposition
- skipped checks and reasons

Strict receipt validation should fail when required evidence is missing or
malformed. When red/green test evidence is not practical, record the explicit
skip reason rather than leaving the receipt blank.

## Review Quality Bar

- Cap normal reviews at five findings per reviewer.
- Do not report nits unless they affect correctness, security, docs drift, or
  maintainability.
- Include the most plausible false-positive explanation for each finding.
- Keep auto-merge and write-back out of scope unless a human explicitly opts in.
