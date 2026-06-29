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

## Method

1. Check the research brief first. Reject source reports that ignored allowed
   domains, seed URLs, queries, include/exclude terms, budgets, or quality
   floors.
2. Group findings by theme.
3. Prefer primary evidence over anecdotal evidence.
4. Mark GitHub examples as implementation patterns unless license, maintenance,
   and fit make dependency adoption plausible.
5. Mark Hacker News/forum/social content as leads unless independently verified.
6. Convert paper ideas into architecture options, evaluation methods, or risks,
   not direct implementation tasks, unless the repo already has the necessary
   primitives.
7. Reject or defer weak, stale, duplicated, out-of-scope, over-budget, or
   unverified leads.

## Synthesis Thresholds

- A backlog or task-packet proposal needs at least one primary source or two
  independent medium-grade sources.
- An architecture or ADR proposal needs explicit tradeoffs, not just source
  enthusiasm.
- A review question can come from a weak lead, but it must be labelled as a
  question rather than a finding.
- A Hacker News or forum-only signal cannot become an implementation task.
- A GitHub-only signal cannot become a dependency recommendation without
  maintenance, license, and fit checks.

## Output

Return JSON matching `schemas/research-synthesis.schema.json`.

Each proposal must have:

- target: backlog, review, architecture, design, ADR, risk, or task-packet.
- priority.
- source evidence.
- rationale.
- proposed artifact or next action.
- docs impact.
- acceptance criteria or verification path.
- human decision state.

Do not create or edit the proposed artifacts in this step.
