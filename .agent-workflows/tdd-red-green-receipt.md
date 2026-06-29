# TDD Red/Green Receipt

Use this when an agent or human changes behavior through test-first work.

## Required Fields

- Change goal:
- Public behavior or contract being protected:
- Failing test command before production change:
- Failing test result:
- Production change summary:
- Passing test command after production change:
- Passing test result:
- Adjacent checks run:
- Generated-test provenance:
- Docs impact:
- Exception reason if red/green was not practical:

## Rules

- Prefer one meaningful failing test over broad test churn.
- Do not claim TDD when the test was written after the production change.
- Generated tests need human review before they become permanent project
  policy.
- Manual validation is useful, but it does not replace feasible automated
  verification.
