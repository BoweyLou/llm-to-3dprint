# Agent Tool And Network Allowlist

Use this document before running local review agents, browser research agents,
or CI review adapters.

## Default Boundary

- Filesystem reads are allowed inside the repository checkout.
- Source, docs, config, and test writes are denied for reviewer personas.
- Review artifact writes are allowed only under `.agent-workflows/runs/`.
- Git status and diff are allowed.
- Git stage, commit, branch, reset, clean, push, and force-push are denied until
  a human approves a scoped implementation task.
- Browser use is read-only by default.
- Account mutation, CAPTCHA bypass, purchases, bookings, PR mutation, issue
  mutation, and CI secret access are denied.
- Network calls are denied unless this file or the active trust profile names
  an explicit allowlist.

## Trust Profiles

The concrete machine-readable policy is
`.agent-workflows/agent-permission-policy.json`.

- `read-only-review`: local repository inspection with read-only shell and git
  operations.
- `untrusted-pr`: fork-origin or otherwise untrusted changes; no network, no
  browser, no PR mutation, and no source writes.
- `browser-research`: source collection through a browser without account
  mutation.
- `write-worker`: scoped implementation after human approval.

## CI Adapter Notes

GitHub-hosted runners cannot be treated as a security boundary for arbitrary
agents. The installed read-only workflow therefore:

- uses read-only repository permissions
- checks out without persisted write credentials
- uses `AGENT_TRUST_PROFILE=untrusted-pr`
- produces local artifacts instead of comments or commits
- does not expose secrets to fork-origin review jobs

If a team adds networked tools, package installation, PR comments, code scanning
upload, or external model calls, record the host/service here and explain why it
is needed.

## Allowlist Table

| Surface | Default | Allowed Examples | Approval Needed For |
| --- | --- | --- | --- |
| Filesystem | read-only | repository reads, `.agent-workflows/runs/` artifacts | source/docs/config/test writes |
| Shell | allowlisted | `git status`, `git diff`, `rg`, local verification commands | destructive commands, package installs, network tools |
| Git | inspect only | status, diff | stage, commit, branch, push, reset, clean |
| Browser | read-only | open/search/read pages | posts, likes, bookmarks, DMs, forms, account settings |
| Network | denied unless allowlisted | documented package or source endpoints | new hosts, uploads, external model calls |
| MCP/tools | read-only | retrieval/context tools | write tools, issue/PR mutation, vault writes |
| CI | read-only | local checks and local artifacts | secrets, PR comments, labels, merge, deploy |

## Receipt Checklist

Record in the session receipt:

- selected trust profile
- review risk tier
- network or tool allowlist checked: yes/no
- mutation boundary checked: yes/no
- data boundary checked: yes/no
- any approved deviations
