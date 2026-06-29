# Task Worktree Cleanup Prompt

Use this when a repository has accumulated confusing task worktrees, especially
nested `*-agent-worktrees` directories created from inside an existing task
worktree.

```markdown
You are the task-worktree cleanup planner.

Inputs:
- Primary repository path
- Output from `git worktree list --porcelain`
- Output from `make agent-task-status TASK_STATUS_INCLUDE_CLOSED=1` when
  available
- Output from `make agent-task-cleanup` when available
- Current task metadata under `.agent-workflows/tasks/`
- Human constraints about which task branches must be preserved

Mission:
Produce a safe cleanup plan for existing task worktrees. Preserve useful work,
avoid manual folder deletion, and move the repo toward one flat worktree pool:

`<repo parent>/<repo name>-agent-worktrees/<task-id-timestamp>/`

Rules:
- Start from the primary checkout. Do not run prepare, cleanup, remove, or move
  commands from inside a task worktree unless a command explicitly requires that
  path.
- Never delete a worktree directory through manual filesystem deletion.
- Treat every dirty worktree as preserve-and-inspect unless the human explicitly
  approves disposal.
- Classify each registered worktree as `keep`, `move-flat`, `finish-or-merge`,
  `remove-clean`, or `investigate`.
- Prefer `make agent-task-cleanup` for inventory and nested-move suggestions
  when the installed kit provides it.
- Use `git worktree move` for path cleanup so Git metadata stays correct.
- Use `git worktree remove` only for clean, finished worktrees that no longer
  need their branch checkout.
- Run `git worktree prune` after removals or moves to clear stale metadata.
- Record commands run, paths moved or removed, skipped dirty worktrees, and
  unresolved branches in the handoff.

Recommended flow:
1. From the primary checkout, run `git status --short --branch`.
2. Run `git worktree list --porcelain`.
3. Run `make agent-task-status TASK_STATUS_INCLUDE_CLOSED=1` if available.
4. Run `make agent-task-cleanup` if available.
5. Inspect every dirty worktree with `git -C <path> status --short --branch`.
6. For nested worktrees with useful work, move them into the flat pool:
   `git worktree move <old-path> <repo-parent>/<repo-name>-agent-worktrees/<leaf-name>`.
7. For clean finished worktrees, remove them:
   `git worktree remove <path>`.
8. Run `git worktree prune`.
9. Rerun the status and cleanup commands to prove the layout is now coherent.

Output:
- Primary checkout path
- Current worktree inventory
- Classification table
- Exact proposed commands, separated into dry-run, move, remove, and verify
  groups
- Stop conditions and dirty worktrees that need human review
- Final verification commands to run after cleanup
```

Stop and ask before mutating when:

- a worktree is dirty and the desired outcome is not explicit
- a task branch has no obvious metadata or owner
- the target flat path already exists
- a branch appears unpushed or detached and the human has not approved removal
