# Pull Request Slash Command Grammar

This is a specification only. repo-contract-kit does not currently execute
slash commands, mutate pull requests from command comments, edit files, push
branches, approve reviews, or call external APIs because of these lines.

Future implementations must keep the local-first contract: parse intent
deterministically, prefer local commands and sidecar receipts, use the base
repository policy files for PR checks, and respect
`.agent-workflows/agent-permission-policy.json` before writing files, posting
comments, or mutating pull requests.

## Grammar

Slash commands are exact lowercase tokens at the start of a comment line after
optional whitespace. Arguments use POSIX-style long flags. Short flags,
unknown flags, absolute paths, parent-directory traversal, shell operators, and
implicit default writes are invalid.

```text
command-line = [space] command *(space argument) [space]
command      = "/docs-impact" | "/waive-docs" | "/review-docs" |
               "/add-docs" | "/update-changelog"
argument     = flag [space value]
flag         = "--" name
name         = 1*(lowercase-letter | digit | "-")
value        = quoted-string | token
quoted-string = DQUOTE *(escaped-character | non-quote-character) DQUOTE
token        = 1*(visible-character except space, tab, backtick, quote)
```

Path values are repository-relative paths. Implementations must normalize paths
before use and reject values that resolve outside the repository root.

## Commands

| Command | Intent | Allowed arguments | Permission boundary |
| --- | --- | --- | --- |
| `/docs-impact` | Report documentation impact for the PR, branch, working tree, or explicit changed files. | `--base <ref>`, `--head <ref>`, repeatable `--changed-file <path>`, `--format text|json|sarif`. | Read-only. Use the `read-only-review` profile. It may run local docs-impact checks and write local or sidecar receipts only when explicitly requested by the runner. |
| `/waive-docs` | Ask reviewers to accept that a change has no required docs update. | Required `--reason "<text>"`; optional repeatable `--category <name>` and `--expires <YYYY-MM-DD>`. | Human approval only. Agents must not invent a waiver, edit the PR body, add labels, or mark checks successful from this command. A future adapter may report the requested waiver, but PR mutation still requires explicit `pr-comment` or `pr-mutation` permission. |
| `/review-docs` | Review whether changed docs, code, schemas, CLI help, and changelog entries agree. | `--mode quick|full`, `--scope changed|all`, repeatable `--focus <path-or-category>`. | Read-only by default. Use `read-only-review` for inspection and local artifacts. File edits require a separate accepted task and the `write-worker` profile. |
| `/add-docs` | Request a docs addition or a docs-patch proposal for missing coverage. | Required `--path <doc-path>`; optional repeatable `--source <path>`, repeatable `--category <name>`, `--title "<text>"`, `--mode propose|task|write`. | Default mode is `propose`. It may create sidecar proposal artifacts or a task packet. `--mode write` requires an approved scoped task, local write permission, and `write-worker`; it must not run from untrusted PR credentials. |
| `/update-changelog` | Request a changelog entry or versioning task for release-impacting work. | `--version <semver>`, `--bump patch|minor|major`, `--section "<heading>"`, repeatable `--summary "<text>"`, `--mode propose|task|write`. | Default mode is `propose`. Local proposal/check mode maps to `repo_contract_kit.py changelog-update` or `make agent-changelog-update` and does not write `CHANGELOG.md` or `VERSION`. Writing either file requires the versioning profile, accepted release scope, local write permission, `write-worker`, and `make version-check` evidence. |

Before `/waive-docs` or `/add-docs`, use local `docs-explain` when policy is
unclear. It is not a hosted slash command: it scans local docs, returns cited
paths/headings/snippets and a ready prompt, and does not write target files,
sidecar files, `VERSION`, or `CHANGELOG.md`.

## Receipts And Comments

Future implementations should emit a deterministic receipt with:

- command name
- normalized arguments
- actor and trust profile
- target repository, PR, branch, or changed-file list
- local commands run and exit codes
- docs-impact or review result
- sidecar artifact paths when used
- rejected permissions or mutation attempts

Hosted adapters may upsert a single marker comment only when the selected
permission policy allows `pr-comment`. They must not merge, approve, label,
edit the PR body, rerun privileged workflows, expose secrets, or checkout
untrusted head code with write credentials.

## Rejection Cases

Reject the command without side effects when any of these are true:

- the command token or flag is unknown
- a required argument is missing or empty
- a path is absolute, contains `..`, expands outside the repo, or targets an
  ignored/protected path
- a quoted value is unterminated
- `--format`, `--mode`, `--scope`, or `--bump` uses a value outside its
  allowed set
- the actor or selected trust profile lacks the required permission
- the command asks a read-only profile to write files, stage, commit, push,
  comment, mutate a PR, access secrets, or make non-allowlisted network calls
- `/waive-docs` is issued without a specific human reason
- `/add-docs --mode write` or `/update-changelog --mode write` lacks an
  approved task packet and local receipt plan

## Examples

```text
/docs-impact --changed-file src/new_cli.py --format json
/waive-docs --reason "Comment-only typo fix; no behavior or user-facing docs changed."
/review-docs --mode full --scope changed --focus docs/ops/agent-workflow.md
/add-docs --path docs/ops/new-command.md --source src/new_command.py --mode propose
/update-changelog --bump patch --summary "Documented the PR slash-command grammar." --mode propose
```

Local read/proposal/check equivalents:

```bash
python3 scripts/repo_contract_kit.py docs-explain --question "Can this docs work be waived?" --focus waiver
make agent-docs-explain DOCS_EXPLAIN_QUESTION="What docs policy applies?"
python3 scripts/repo_contract_kit.py changelog-update --changed-file src/new_cli.py --bump patch --summary "Documented the PR slash-command grammar."
make agent-changelog-update CHANGELOG_UPDATE_CHECK=1
```
