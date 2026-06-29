# Versioning

This repo uses local SemVer in `VERSION` as the source of truth. Tags are useful
release markers when your host allows them, but the local file and changelog are
the required baseline.

## Commands

- `make version-status` prints the current target repo version.
- `make version-check` validates that `VERSION` contains SemVer in the form
  `major.minor.patch` or `major.minor.patch-prerelease`.
- `make version-bump BUMP=patch` updates `VERSION` and prepends a changelog
  stub. `BUMP=minor` and `BUMP=major` are also supported.

## Agent Guidance

Agents should consider a version bump when a change affects behavior, APIs,
configuration, data contracts, runtime operations, or user-visible output. The
command does not commit, tag, push, or publish anything; a human or local agent
must review the changelog stub and decide when to commit.

`VERSION` and `CHANGELOG.md` are target-owned files. The kit creates them when
missing, but future kit updates must not overwrite the target repo's version
history.
