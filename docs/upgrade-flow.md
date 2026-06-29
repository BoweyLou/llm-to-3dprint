# Guided Upgrade Flow

Use this flow when moving an enrolled target repo to a newer
`repo-contract-kit` version. It keeps updates explicit, preserves target-owned
work, and treats conflict proposals as review artifacts rather than automatic
instructions.

## Safety Boundary

The upgrade flow must not reset the target repo, discard local changes, move
`AGENTS.md` out of the repo root, or blindly copy proposed replacements from
`.doc-contract-kit/updates/`. A kit update can replace clean kit-managed files,
refresh kit metadata, and write proposed replacements for customized managed
files. It must preserve target-owned files and customized managed files.

Stop and ask a human before applying an update if the target repo has unrelated
dirty work, the source kit checkout is not the intended version, or a proposed
replacement changes repository instructions, documentation contracts, or update
guardrails in a way you cannot justify.

## 1. Inspect

Start from the target repo:

```bash
kit status
kit update --dry-run
```

When the global launcher is unavailable, use the local fallback:

```bash
make kit-status KIT=/path/to/kit
```

For automation, prefer a non-mutating JSON plan:

```bash
kit update-plan --json
```

The plan should show the installed kit version, available source version,
managed-file states, profile/config schema state, conflicts, blockers, and the
next safe commands.

## 2. Review The Plan

Read the plan before applying anything:

- `target-owned` files are owned by the repo and should not be overwritten by
  kit updates.
- `customized` managed files stay in place; the updater writes proposed
  replacements under `.doc-contract-kit/updates/<timestamp>/proposed/`.
- `missing` clean managed files can be restored by an update.
- `migrate-profile-config` means only kit metadata is missing or stale.
- `blockers` mean the update should not be applied until the blocker is fixed
  or intentionally accepted by a human.

If the plan includes `read_next`, read those files before accepting any
proposal. They point at the repo instructions, installed workflow docs, and kit
changelog that explain the upgrade.

## 3. Apply Metadata-Only Migration When Needed

If the dry run reports only missing or outdated profile/config metadata, use
the metadata-only migration path:

```bash
make kit-migrate-config KIT=/path/to/kit
```

This updates `.doc-contract-kit/install.json` and
`.doc-contract-kit/manifest.json` schema markers. It does not rewrite
target-owned files, managed files, customized managed-file baselines, or
`AGENTS.md`.

## 4. Apply The Managed Update

After reviewing the dry run, apply the safe managed update:

```bash
kit update
```

Local checkout fallback:

```bash
make kit-update KIT=/path/to/kit
```

Clean managed files are updated in place. Customized managed files are
preserved and get proposed replacements plus an update report under
`.doc-contract-kit/updates/`.

## 5. Review Conflicts

Open the newest update report:

```bash
ls -t .doc-contract-kit/updates/*/update-report.md | head -1
```

Review each conflict deliberately. Do not copy the entire `proposed/` tree over
the target repo. Merge only the lines that still fit the target repo, then rerun
`kit status` or `make kit-status KIT=/path/to/kit`.

Keep `.doc-contract-kit/updates/` as evidence until a human decides it is safe
to archive or remove old proposals.

## 6. Diagnose

Run diagnostics after updating:

```bash
kit doctor
make agent-preflight
make agent-state-ledger
```

Use these checks to catch dirty-state blockers, active task scopes, sibling
worktrees, sidecar availability, and recovery-command guidance before starting
write-capable agent work.

## 7. Verify

Run the target repo's normal checks. For a standard installed repo, include:

```bash
make docs-check
make version-check
kit status
```

If the target repo has project tests, run that project-specific test command as
well. Do not treat a successful kit update as proof that product code still
works.

## What This Flow Does Not Do

This flow does not migrate application code, dependency managers, CI services,
hosted project settings, external issue trackers, or private memory systems. It
only updates local repo-contract-kit guardrails, prompt snapshots, metadata, and
operator docs inside the target repo.
