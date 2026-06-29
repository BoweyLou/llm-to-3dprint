# Planning Adapter Examples

`repo-contract-kit` does not try to be a planning app. It provides local
contracts that let a selected planning item become one reviewable task packet.

Use this page when work starts in Keryx, Obsidian, GitHub Issues, Linear, Jira,
a spreadsheet, or another external planning system.

## Boundary

- External planning systems own prioritization, sequencing, labels, owners, and
  long-lived product context.
- Repo backlog mirrors such as `docs/backlog.md`, `BACKLOG.md`, `backlog.md`, or
  `research/agentic-workflow-review/backlog.csv` are reviewable local copies.
- `make backlog-status`, `make backlog-check`, and `make agent-next` report the
  local mirror state; they do not settle priority disputes.
- `make agent-task-packet` and `make agent-task-packet-from-backlog
  BACKLOG_ID=<id>` turn one selected item into bounded executable work.
- External writes need that system's own governed workflow. The kit does not
  write Keryx notes, Obsidian vault files, issues, labels, project boards, or
  hosted planning state.

## Example: Keryx Or Obsidian Project Task

Use Keryx or Obsidian as the durable planning source when project memory and
human context matter.

1. Read the project task from the memory system using its normal governed
   workflow.
2. Mirror only the selected fields into the repo backlog: stable id, title,
   priority, source pointer, acceptance notes, and current status.
3. Run `make backlog-check` so the mirror shape is valid.
4. Run `make agent-task-packet-from-backlog BACKLOG_ID=<id>` or create a richer
   packet manually from `.codex/prompts/task-packet.md`. Keep the mirror row
   compact, but make the executable packet expand the actor, need, desired
   outcome, acceptance summary, non-goals, validation, exact docs and release
   metadata surfaces, docs impact, and risk.
5. Keep status updates in the external system explicit. A repo commit closing a
   backlog mirror does not silently update Keryx or Obsidian.

Suggested mirror note:

```markdown
Source of truth: Keryx project task `KX-123`.
Repo mirror purpose: local task-packet handoff only.
Stale mirror policy: refresh from Keryx before implementation if this row is
older than 7 days or conflicts with current project memory.
```

## Example: GitHub Issue Or Tracker Item

Use issue trackers for team-visible ownership, labels, and discussion. Use the
repo mirror for local agent handoff.

1. Link the issue id or URL in the backlog row's source/context field.
2. Keep the issue body as the discussion source of truth.
3. Copy only the implementation slice into the task packet: allowed files,
   protected files, acceptance criteria, validation, exact docs and release
   metadata surfaces, docs impact, and risk.
4. Run local checks and commit normally.
5. Let a human or explicit hosted workflow update issue labels, milestones, or
   project-board state.

Suggested mirror row fields:

```text
id: ISSUE-42
source: https://github.com/org/repo/issues/42
status: open
notes: Repo mirror for local AGW task packet; issue remains discussion source.
```

## Example: `docs/backlog.md` Mirror

For simple repos, a Markdown backlog can be enough:

```markdown
# Backlog

## Open

- [ ] WEB-014 [P1] Add upload retry telemetry
  - Source: Product review 2026-06-22
  - Scope: `src/upload/**`, `docs/ops/upload.md`
  - Acceptance: retry attempts are logged locally and docs explain the signal
  - Validation: project test command, `make docs-check`

## Done

- [x] WEB-013 [P2] Document upload limits
  - Closed in: abc1234
```

The mirror should be boring and easy to diff. Do not embed private memory dumps,
large issue threads, or credentials in repo backlog files.

## Stale Or Conflicting State

When the external planner and repo mirror disagree:

1. Stop before implementation.
2. Record which source is stale or ambiguous.
3. Refresh the mirror from the external system, or ask the owner to choose the
   current item.
4. Create or update one task packet only after the selected item is clear.

Do not let an agent choose between conflicting priority systems by intuition.

## What A Good Task Packet Carries

A task packet should carry enough local evidence that the implementer does not
need broad planning-system access:

- source pointer and stable id
- story context: user story, operator story, or job-to-be-done
- problem statement
- non-goals
- allowed and protected files
- acceptance criteria
- validation commands
- docs impact
- exact docs and release metadata surfaces
- risk and stop conditions
- previous-task closeout state

If the external system contains private or sensitive context, summarize only the
minimum safe facts needed for the local task.
