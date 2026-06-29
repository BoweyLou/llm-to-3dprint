# Review Finding Template

Use this structure for each finding.

```markdown
## [P0-P3] Short Title

Area: docs | code | tests | build | security | runtime | UX | architecture
Confidence: high | medium | low
Disposition: open | accepted | rejected | fixed | deferred | duplicate
Evidence:
- `path/to/file.ext:line`: concrete observation
- command or runtime check used, if any

Problem:
Explain the issue in one short paragraph. Describe actual behavior or maintainability risk, not taste.

Impact:
Explain who or what is affected. State whether this is a correctness, reliability, security, documentation, maintenance, or delivery risk.

Recommendation:
Give the smallest useful fix. Name the files or modules likely involved.

Verification:
Name the test, command, runtime check, or manual inspection that would prove the fix.

False-positive check:
State the most plausible reason this might be harmless, or write `none found`.
```

Priority guide:

- `P0`: Security, data-loss, production outage, or release-blocking correctness issue.
- `P1`: High-likelihood bug, serious maintenance trap, broken documented behavior, or missing critical test.
- `P2`: Moderate risk, duplicated behavior likely to drift, weak abstraction, or stale documentation.
- `P3`: Cleanup, clarity, style, or low-risk follow-up.

Default finding budget:

- Return at most 5 findings per persona.
- Do not include nits unless they block understanding, correctness, security, or
  the documentation contract.
- Prefer one well-evidenced finding over several speculative findings.
