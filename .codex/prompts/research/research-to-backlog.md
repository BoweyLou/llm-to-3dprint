# Research To Work Handoff Prompt

Use this prompt after a human accepts one or more research synthesis proposals.

## Goal

Convert accepted proposals into reviewable backlog rows, design notes, ADR
candidates, review questions, risk notes, or task-packet candidates.

## Inputs

- Research synthesis JSON.
- Human acceptance notes.
- Current backlog, ADR, design, or task-packet conventions for the repo.

## Rules

- Keep source evidence attached to every proposed item.
- Do not mix accepted proposals with rejected or weak leads.
- Confirm that each accepted proposal satisfied the brief's source plan,
  including allowed domains, seed queries, evidence budget, and quality floor.
- Confirm that each accepted proposal satisfied the novelty ledger: its
  candidate score must clear the novelty threshold or explain why a human chose
  to carry a lower-novelty item anyway.
- For backlog rows, use the repo's existing priority, theme, delivery-shape, and
  status conventions.
- For ADR candidates, include decision pressure, options, consequences, and
  open questions.
- For task-packet candidates, include scope, acceptance criteria, validation,
  docs impact, risk, and approval state.
- If evidence is too weak, produce a review question or follow-up research item
  instead of an implementation task.
- Do not fill a backlog merely because sources were found. Only create a work
  item when the research changes a concrete repo decision.
- Carry rejected or deferred leads forward into the next research brief ledger;
  do not convert them into backlog rows unless a human explicitly accepts them.

## Output

Return a Markdown handoff with separate sections:

- Accepted proposals.
- Proposed backlog rows.
- Proposed review questions.
- Proposed architecture or design notes.
- Proposed ADR candidates.
- Proposed task-packet candidates.
- Rejected or deferred leads.

End with the exact files that would change if the human approves the write step.
