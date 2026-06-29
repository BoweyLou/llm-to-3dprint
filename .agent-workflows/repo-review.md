# Local Repo Review Workflow

Use this workflow for a local agentic code review in a locked-down repository.

## Inputs

- User request or review goal
- Current branch or changed files
- `AGENTS.md`
- `REVIEW.md`
- `doc-contract.json`
- `docs/documentation-contract.md`
- Latest ADRs under `docs/adr/`, when present

## Steps

1. Establish scope: bootstrap, drift, pull-request, release-gate, learning, or
   test-first.
2. Run local discovery:

   ```bash
   git status --short
   python3 scripts/localize_doc_impact.py --working-tree --json
   python3 scripts/lint_agent_docs.py --strict-paths
   ```

3. Select the smallest reviewer set needed. Prefer one focused reviewer for
   normal drift and add specialists only for high-risk areas. Use the
   `review_risk` block in the `make agent-start` packet as the routing signal.
4. Optionally run `make agent-run-review AGENT=manual` to create persona prompts
   and review-run artifacts, or `make agent-run-review AGENT=amp` to execute the
   selected personas through Amp CLI.
5. Produce at most five findings per reviewer.
6. Require file evidence, command evidence, docs/ADR evidence, or runtime
   evidence for every finding.
7. Record false-positive notes for every finding.
8. Use `.agent-workflows/schemas/session-receipt.schema.json` for persona
   finding receipts and `schemas/review-synthesis.schema.json` for synthesis
   when JSON output is possible.

## Default Reviewer Set

- Documentation/code delta
- AI code slop
- Test and behavior risk
- Reuse and architecture

Add security, API/data contracts, dependencies/build, runtime, duplication, dead
code, or frontend UX reviewers only when the changed files justify them.

## Tool And Network Boundary

Before running browser research, hosted CI adapters, external models, or
write-capable workers, read `docs/ops/agent-tool-network-allowlist.md` and the
selected trust profile in `.agent-workflows/agent-permission-policy.json`.
Reviewer personas are read-only by default.

## Output

Return:

- summary
- findings table with priority, area, confidence, evidence, recommendation, and
  disposition
- docs-impact result
- commands run
- review risk tier and selected trust profile
- tests run or skipped with reasons
- next local command the human should run

If `make agent-run-review` was used, inspect:

- `.agent-workflows/runs/<id>/review-run/review-run.json`
- `.agent-workflows/runs/<id>/review-run/personas/*/findings.json`
- `.agent-workflows/runs/<id>/review-run/synthesis/review-synthesis.json`
