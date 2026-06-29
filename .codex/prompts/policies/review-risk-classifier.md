# Review Risk Classifier Policy

Use this policy before dispatching multi-agent review or write-capable follow-up
work.

## Purpose

Classify changed files into a small, deterministic risk tier so deep review runs
are used where they add value and normal changes keep a narrow reviewer set.

## Local Command

```bash
python3 scripts/classify_review_risk.py --working-tree
```

For a known path list:

```bash
python3 scripts/classify_review_risk.py src/auth/session.py migrations/0004_users.sql
```

## Risk Tiers

- `low`: no path trigger matched; use the default reviewer set.
- `medium`: docs-contract, CI/build, runtime, or frontend paths changed; add the
  relevant specialist when the output affects users or operations.
- `high`: auth, secrets, APIs, migrations, schemas, or persisted data changed;
  add specialist reviewers and require concrete file, command, or runtime
  evidence.
- `critical`: destructive or deletion-oriented paths changed; keep review
  read-only and require human approval plus rollback or recovery evidence before
  any write-capable follow-up.

## Deterministic Triggers

The classifier checks lowercased changed-path text for these token families:

- Auth/secrets: auth, login, session, permission, secret, token, credential, and
  environment-file markers.
- Destructive data operations: delete, destroy, purge, truncate, wipe, drop, and
  reset.
- Migration/persistence: migration, database, schema, SQL, and model markers.
- Public contracts: API, OpenAPI, GraphQL, webhook, contract, public, SDK, and
  client markers.
- CI/build/release: workflow, CI, build, release, container, make, package, and
  requirements markers.
- Runtime/ops: deploy, infra, Terraform, Helm, service, scheduler, cron,
  runbook, and operations markers.
- Docs contract: agent instruction, review instruction, documentation contract,
  and ADR markers.
- Frontend: frontend, component, page, route, and common web UI extension
  markers.

## Dispatch Rules

- Start from `doc-code-delta`, `ai-code-slop`, `test-behavior-risk`, and
  `reuse-architecture`.
- Add `security-privacy` for auth, secret, permission, destructive, or privacy
  triggers.
- Add `api-data-contracts` for API, schema, migration, database, destructive,
  generated-client, or persisted-data triggers.
- Add `dependencies-build` for package, CI, build, release, and container
  triggers.
- Add `runtime-observability` for deployment, service, scheduling, runbook, and
  operational triggers.
- Add `frontend-ux` for changed user-facing frontend paths.

## Evidence Bar

Risk classification is only a routing signal. Findings still need concrete
evidence: file path, line or symbol, command output, docs/ADR source, or runtime
surface.
