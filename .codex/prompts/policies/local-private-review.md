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

## Review-Only Local Model Suitability

Local or self-hosted models can be useful for read-only review passes when the
task is low risk, privacy-sensitive, and tolerant of advisory output. Good
fits include:

- first-pass README, docs, and comment/docstring scans
- duplicate, stale, or low-signal finding triage
- summarizing local diffs, task packets, receipts, or validation logs
- a short pre-escalation pass that decides whether a stronger model or human
  should review before any private context leaves the trusted environment

Escalate to a stronger reviewed path or a human before relying on the result
when the task touches:

- security, privacy, compliance, legal, medical, financial, credentials, or
  account state
- migrations, data deletion, persistence, public APIs, build or release
  systems, deployment, or production operations
- large-repo architecture or cross-module judgments where context limits may
  hide evidence
- weak or unverified tool calling, unreliable structured output, stale model
  knowledge, or high false-positive/false-negative rates

Local execution is not a privacy, safety, correctness, or productivity
guarantee. Record the actual boundary and capability caveats, then keep findings
advisory until direct evidence, validation, or human review supports them.

## Provider Notes

Record provider expectations and the actual data boundary in the receipt:

- `local-only`: no repository content was sent to an external model or service.
- `self-hosted`: inference endpoint is controlled by the operator but may run on
  another machine, VM, or private server.
- `remote-openai-compatible`: the API shape is OpenAI-compatible, but repository
  snippets, diffs, logs, or prompts still leave the local machine.
- `hosted-provider`: repository snippets, diffs, logs, or prompts are sent to a
  hosted model/provider service.
- `browser-authenticated`: a logged-in browser session was used for source
  collection.
- `unknown`: the boundary was not confirmed; treat findings as advisory until a
  human reviews exposure risk.

Also record:

- selected model/provider expectations and known context limits
- whether tools, function calling, images, structured output, or repository
  indexing were expected to work
- capability caveats that affect confidence
- the escalation decision for high-risk or low-confidence findings

## Stop Conditions

Stop and ask for approval before:

- sending proprietary code or sensitive logs to a new provider
- using a logged-in browser account
- downloading files from private systems
- creating public artifacts
- running tools that need secrets or privileged network access
