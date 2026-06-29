# Read-Only Reviewer Sandbox Policy

Use this policy for review personas and review runners unless the user has
explicitly approved a scoped implementation task.

## Default Boundary

Reviewers may:

- read repository files
- search the checkout
- inspect git status and diffs
- run local read-only checks
- write review artifacts only when the runner already owns an ignored artifact
  directory

Reviewers must not:

- edit source, docs, config, tests, prompts, or generated artifacts
- stage, commit, branch, reset, clean, push, or mutate Git history
- post PR comments, resolve threads, merge, label, or mutate issues
- call write-capable MCP tools
- mutate browser/account state
- access secrets or CI secret contexts
- make network calls outside a documented allowlist

## Write-Capable Escalation

Escalate to a write-capable worker only after:

- the accepted finding or task packet names the files in scope
- protected files and out-of-scope directories are listed
- validation commands are known
- human approval is explicit
- the work happens in an isolated checkout or worktree when parallel work is
  possible

## Receipt Requirements

Every review run should record:

- changed files and files inspected
- commands run and their result
- risk tier and selected trust profile
- selected personas
- findings with evidence and false-positive notes
- confirmation that no file writes, git mutations, account mutations, or
  non-allowlisted network calls occurred
