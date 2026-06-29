# Research Synthesis Prompt

Use this prompt after source-specific agents have produced source reports.

## Goal

Deduplicate source reports, rank evidence, and turn research into proposed
repo work without directly mutating backlog, docs, ADRs, issues, or code.

## Inputs

- Research brief JSON.
- One or more source reports.
- Current repo context: backlog, review findings, docs, ADRs, or product area
  named in the brief.
- Novelty ledger from the brief: prior-question fingerprints, recent topics,
  novelty threshold, and rejected or deferred carry-forward leads.

## Method

1. Check the research brief first. Reject source reports that ignored allowed
   domains, seed URLs, queries, include/exclude terms, budgets, or quality
   floors.
2. Check candidate themes against the novelty ledger before ranking them.
   Reject low-novelty repeats unless new evidence materially changes the
   decision.
3. Group findings by theme.
4. Score several candidate ideas before selecting proposals. Include novelty,
   evidence strength, repo fit, effort, risk, recommendation state, and a short
   rationale for each scored candidate.
5. Prefer primary evidence over anecdotal evidence.
6. Mark GitHub examples as implementation patterns unless license, maintenance,
   and fit make dependency adoption plausible.
7. Mark Hacker News/forum/social content as leads unless independently verified.
8. Convert paper ideas into architecture options, evaluation methods, or risks,
   not direct implementation tasks, unless the repo already has the necessary
   primitives.
9. Reject or defer weak, stale, duplicated, out-of-scope, over-budget,
   low-novelty, or unverified leads. Carry rejected or deferred leads forward
   when a future run should remember the decision.

## Synthesis Thresholds

- A backlog or task-packet proposal needs at least one primary source or two
  independent medium-grade sources.
- An architecture or ADR proposal needs explicit tradeoffs, not just source
  enthusiasm.
- Because weak-source evidence is not enough for a defect claim, a review
  question can come from a weak lead, but it must be labelled as a question
  rather than a finding.
- A Hacker News or forum-only signal cannot become an implementation task.
- A GitHub-only signal cannot become a dependency recommendation without
  maintenance, license, and fit checks.
- Because AGW-083 guards recurring backlog loops, a backlog proposal must meet
  or exceed the brief's `novelty_threshold` unless the rationale explains why
  lower novelty is still worth a human decision.
- Repeated topics below the threshold go to `rejected_leads` with
  `carry_forward: true` when future runs should avoid proposing them again.

## Output

Return JSON matching `schemas/research-synthesis.schema.json`.

Each candidate idea must have:

- target: backlog, review, architecture, design, ADR, risk, or task-packet.
- candidate_score with novelty, evidence_strength, fit, effort, risk,
  recommendation_state, and rationale.
- source evidence and a proposed artifact or next action.
- state: draft, recommended, needs-human-decision, rejected, or deferred.

Each proposal must have:

- target: backlog, review, architecture, design, ADR, risk, or task-packet.
- priority.
- candidate_score showing why it is novel enough, evidenced enough, and worth
  the effort/risk.
- source evidence.
- rationale.
- proposed artifact or next action.
- docs impact.
- acceptance criteria or verification path.
- human decision state.

Do not create or edit the proposed artifacts in this step.
