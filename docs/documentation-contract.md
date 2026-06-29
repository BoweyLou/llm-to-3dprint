# Documentation Contract

This repository treats documentation as part of the product.

## Principle

Every code change must be evaluated for documentation impact.

A change is not complete until either:

1. the relevant docs are updated, or
2. it is explicitly declared to have no doc impact

Silence is not acceptable.

## Change types and required actions

### 1. Public behavior changes
Required actions:
- update relevant README/docs pages
- update examples if needed
- add migration notes if the change is breaking

### 2. API changes
Required actions:
- regenerate API/reference docs
- update usage examples
- add migration notes if breaking

### 3. CLI changes
Required actions:
- regenerate CLI docs or help output docs
- update usage examples
- update README if setup or usage changed

### 4. Config and environment variable changes
Required actions:
- update config reference docs
- update setup/deployment docs if needed

### 5. Schema or data contract changes
Required actions:
- update relevant schema/data docs
- add migration notes if needed
- consider ADR if the change is architectural

### 6. Operations or deployment changes
Required actions:
- update runbooks or deployment docs
- update setup instructions if needed

### 7. Architecture changes
Required actions:
- add or update an ADR
- update architecture documentation if needed

## No-docs-needed cases

Examples:
- typo fix in code with no behavior change
- internal refactor with no external impact
- test-only changes
- comment-only changes

Even in these cases, the PR must explicitly state:
`No docs needed: <reason>`

The documentation impact checker accepts that marker from the PR body, or from
the `DOC_CONTRACT_NO_DOCS_NEEDED` environment variable for local/CI adapters.

## Repository-specific rules

Documentation impact rules live in `doc-contract.json`.

Use that file to define:
- which files are required for the docs contract
- which paths count as documentation
- which paths are ignored
- which source paths imply API, CLI, config, or operations impact
- which documentation paths are expected for each impact category

## Generated documentation

Generated docs must never be edited manually unless the repo explicitly says otherwise.

If generated docs exist, contributors must run the generation command and commit the updated output.
