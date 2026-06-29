#!/usr/bin/env python3
"""Validate local agent session receipts without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# Script flow:
# 1. Locate an explicit receipt or the latest local review-run receipt.
# 2. Validate the receipt's top-level fields, commands, findings, and evidence.
# 3. Accumulate all errors so callers get one complete failure report.
# 4. Exit cleanly only when the receipt is structurally usable.
#
# Function guide:
# - load_json/latest_receipt read the receipt input.
# - require/as_dict/as_list provide defensive validation helpers.
# - validate_command/validate_finding validate nested receipt records.
# - validate_receipt/parse_args/main run the full CLI check.
VALID_RUN_STATUSES = {"pass", "pass-with-caveats", "fail", "blocked", "not-run"}
VALID_COMMAND_RESULTS = {"pass", "fail", "not-run", "blocked"}
VALID_TEST_RESULTS = {"red-green", "green-only", "not-applicable", "not-run", "blocked"}
VALID_FINDING_PRIORITIES = {"P0", "P1", "P2", "P3"}
VALID_FINDING_CONFIDENCE = {"high", "medium", "low"}
VALID_FINDING_STATUS = {"open", "accepted", "rejected", "fixed", "deferred", "duplicate"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Receipt not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def latest_receipt(root: Path) -> Path:
    runs_root = root / ".agent-workflows" / "runs"
    candidates = sorted(runs_root.glob("*/review-run/receipt.json")) if runs_root.exists() else []
    if not candidates:
        raise SystemExit("No receipt found. Pass --receipt or run make agent-run-review first.")
    return candidates[-1]


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validate_command(command: Any, index: int, errors: list[str]) -> None:
    require(isinstance(command, dict), f"evidence.commands[{index}] must be an object", errors)
    if not isinstance(command, dict):
        return
    require(bool(command.get("command")), f"evidence.commands[{index}].command is required", errors)
    require(command.get("result") in VALID_COMMAND_RESULTS, f"evidence.commands[{index}].result is invalid", errors)
    exit_code = command.get("exit_code")
    require(exit_code is None or isinstance(exit_code, int), f"evidence.commands[{index}].exit_code must be integer or null", errors)


def validate_finding(finding: Any, index: int, errors: list[str]) -> None:
    require(isinstance(finding, dict), f"findings[{index}] must be an object", errors)
    if not isinstance(finding, dict):
        return
    for field in ["id", "area", "title", "recommendation"]:
        require(bool(finding.get(field)), f"findings[{index}].{field} is required", errors)
    require(finding.get("priority") in VALID_FINDING_PRIORITIES, f"findings[{index}].priority is invalid", errors)
    require(finding.get("confidence") in VALID_FINDING_CONFIDENCE, f"findings[{index}].confidence is invalid", errors)
    require(finding.get("status") in VALID_FINDING_STATUS, f"findings[{index}].status is invalid", errors)
    evidence = finding.get("evidence")
    require(isinstance(evidence, list) and bool(evidence), f"findings[{index}].evidence must be a non-empty array", errors)


def validate_receipt(receipt: Any, strict: bool) -> list[str]:
    errors: list[str] = []
    require(isinstance(receipt, dict), "receipt must be an object", errors)
    if not isinstance(receipt, dict):
        return errors

    require(receipt.get("schema_version") == 1, "schema_version must be 1", errors)
    for field in ["run", "tooling", "scope", "evidence", "findings", "disposition"]:
        require(isinstance(receipt.get(field), dict if field != "findings" else list), f"{field} has the wrong type", errors)

    run = as_dict(receipt.get("run"))
    require(bool(run.get("id")), "run.id is required", errors)
    require(bool(run.get("started_at")), "run.started_at is required", errors)
    require(bool(run.get("mode")), "run.mode is required", errors)
    require(run.get("status") in VALID_RUN_STATUSES, "run.status is invalid", errors)
    if strict:
        require(run.get("status") != "not-run", "strict mode requires run.status to be completed, not not-run", errors)

    tooling = as_dict(receipt.get("tooling"))
    require(bool(tooling.get("agent_tool")), "tooling.agent_tool is required", errors)
    require(isinstance(tooling.get("local_only"), bool), "tooling.local_only must be boolean", errors)
    if strict:
        require(tooling.get("local_only") is True, "strict mode requires tooling.local_only=true", errors)

    scope = as_dict(receipt.get("scope"))
    require(bool(scope.get("repo_root")), "scope.repo_root is required", errors)
    require(isinstance(scope.get("changed_files"), list), "scope.changed_files must be an array", errors)

    evidence = as_dict(receipt.get("evidence"))
    commands = evidence.get("commands")
    require(isinstance(commands, list), "evidence.commands must be an array", errors)
    for index, command in enumerate(as_list(commands)):
        validate_command(command, index, errors)
    if strict:
        require(bool(commands), "strict mode requires at least one evidence command", errors)

    docs_impact = as_dict(evidence.get("docs_impact"))
    require(isinstance(docs_impact.get("checked"), bool), "evidence.docs_impact.checked must be boolean", errors)
    require(bool(docs_impact.get("result")), "evidence.docs_impact.result is required", errors)
    if strict and not docs_impact.get("checked"):
        require(
            docs_impact.get("result") in {"not-applicable", "waived"} and bool(docs_impact.get("waiver_reason")),
            "strict mode requires docs impact evidence or an explicit waiver/not-applicable reason",
            errors,
        )

    tests = as_dict(evidence.get("tests"))
    require(tests.get("result") in VALID_TEST_RESULTS, "evidence.tests.result is invalid", errors)
    if tests.get("result") == "red-green":
        require(bool(tests.get("failing_test_evidence")), "red-green tests require failing_test_evidence", errors)
        require(bool(tests.get("passing_test_evidence")), "red-green tests require passing_test_evidence", errors)
    if strict and tests.get("result") in {"not-run", "blocked", "green-only"}:
        require(bool(tests.get("skip_reason")), "strict mode requires tests.skip_reason when red/green evidence is absent", errors)

    findings = as_list(receipt.get("findings"))
    for index, finding in enumerate(findings):
        validate_finding(finding, index, errors)

    disposition = as_dict(receipt.get("disposition"))
    require(isinstance(disposition.get("summary"), str), "disposition.summary must be a string", errors)
    require(isinstance(disposition.get("next_actions"), list), "disposition.next_actions must be an array", errors)
    if strict:
        require(bool(disposition.get("summary", "").strip()), "strict mode requires disposition.summary", errors)

    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to inspect when --receipt is omitted")
    parser.add_argument("--receipt", type=Path, default=None, help="Receipt JSON to validate")
    parser.add_argument("--strict", action="store_true", help="Require completed local evidence, not just JSON shape")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).expanduser().resolve()
    receipt_path = args.receipt.expanduser().resolve() if args.receipt else latest_receipt(root)
    receipt = load_json(receipt_path)
    errors = validate_receipt(receipt, args.strict)
    payload = {
        "status": "fail" if errors else "pass",
        "receipt": str(receipt_path),
        "strict": args.strict,
        "error_count": len(errors),
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR {error}")
        print(f"Agent receipt validation failed with {len(errors)} error(s).")
    else:
        print(f"Agent receipt validation passed: {receipt_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
