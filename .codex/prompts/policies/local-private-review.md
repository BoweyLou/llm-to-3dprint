# Local And Private Review Policy

Use this policy when the repository is private, commercially sensitive,
regulated, personal, or otherwise unsuitable for broad external context sharing.

## Data Boundary

Before starting review, state:

- which agent or model is being used
- whether repository content leaves the machine
- whether prompts include source code, diffs, logs, secrets, personal data, or
  private URLs
- whether browser sessions or authenticated accounts are in scope
- whether outputs are local artifacts, PR comments, issue comments, or external
  tickets

## Default Private Mode

- Prefer local commands, local artifacts, and read-only review.
- Do not paste secrets, tokens, cookies, private URLs, request bodies, customer
  data, medical/financial records, or personal messages into prompts.
- Summarize sensitive evidence by file path and symbol when exact content is not
  needed.
- Keep receipts local unless the user requests publication.
- Use a local or self-hosted model only when its capability is good enough for
  the review task; do not trade correctness away silently for privacy.

## Provider Notes

Record provider expectations in the receipt:

- `local-only`: no repository content was sent to an external model or service.
- `external-model`: repository snippets, diffs, or logs were sent to a provider.
- `browser-authenticated`: a logged-in browser session was used for source
  collection.
- `unknown`: the boundary was not confirmed; treat findings as advisory until a
  human reviews exposure risk.

## Stop Conditions

Stop and ask for approval before:

- sending proprietary code or sensitive logs to a new provider
- using a logged-in browser account
- downloading files from private systems
- creating public artifacts
- running tools that need secrets or privileged network access
