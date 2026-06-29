# Sidecar Retention

repo-contract-kit sidecar state is local operator evidence. It is outside the target repository and is never deleted by default.

## Default Policy

- Default retention window: 90 days for routine receipts, task packets, review artifacts, feedback, and automation handoffs.
- Privacy labels: `public-ok`, `internal`, `private-local`, `sensitive-local`.
- Default label: `private-local`.
- Hosted model sharing: do not upload sidecar receipts, feedback, private context, or task packets to a hosted model unless a human explicitly approves the specific content.
- Purge behavior: `kit retention --json` only previews candidates. It does not delete files.

## Safe Archive Guidance

Archive receipts that support release decisions, migration proof, rollback decisions, or accepted findings before purging local state. Keep enough evidence to reconstruct why a task was selected, which mode was used, what validation ran, and what human approval existed.

## Purge Preview

Use `kit retention --json` to list sidecar directories, privacy labels, retention windows, and candidate counts. Review the preview manually before deleting anything with external tools.
