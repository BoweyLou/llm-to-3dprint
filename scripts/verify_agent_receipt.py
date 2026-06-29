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
VALID_COMMENT_ONLY_RESULTS = {
    "comment-only",
    "comment-and-explanation-note",
    "explanation-note-only",
    "fail",
    "uncertain",
    "not-run",
}
PASSING_COMMENT_ONLY_RESULTS = {
    "comment-only",
    "comment-and-explanation-note",
    "explanation-note-only",
}


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


def string_list(value: Any, path: str, errors: list[str]) -> list[str]:
    require(isinstance(value, list), f"{path} must be an array", errors)
    if not isinstance(value, list):
        return []
    for index, item in enumerate(value):
        require(isinstance(item, str) and bool(item.strip()), f"{path}[{index}] must be a non-empty string", errors)
    return [item for item in value if isinstance(item, str)]


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


def validate_comment_only_verification(
    verification: Any,
    run: dict[str, Any],
    scope: dict[str, Any],
    evidence: dict[str, Any],
    strict: bool,
    errors: list[str],
) -> None:
    learning_comments = run.get("mode") == "learning-comments"
    if verification is None:
        if strict and learning_comments:
            errors.append("strict learning-comments receipts require evidence.comment_only_verification")
        return

    require(isinstance(verification, dict), "evidence.comment_only_verification must be an object", errors)
    if not isinstance(verification, dict):
        return

    checked = verification.get("checked")
    result = verification.get("result")
    behavior_assertion = verification.get("behavior_change_assertion")
    source_files_changed = verification.get("source_files_changed")
    no_source_edit_reason = verification.get("no_source_edit_reason")

    require(isinstance(checked, bool), "evidence.comment_only_verification.checked must be boolean", errors)
    require(result in VALID_COMMENT_ONLY_RESULTS, "evidence.comment_only_verification.result is invalid", errors)
    require(
        behavior_assertion in (True, False),
        "evidence.comment_only_verification.behavior_change_assertion must be boolean",
        errors,
    )
    require(
        source_files_changed in (True, False),
        "evidence.comment_only_verification.source_files_changed must be boolean",
        errors,
    )
    require(
        no_source_edit_reason is None or isinstance(no_source_edit_reason, str),
        "evidence.comment_only_verification.no_source_edit_reason must be string or null",
        errors,
    )

    diff_scope = string_list(verification.get("diff_scope"), "evidence.comment_only_verification.diff_scope", errors)
    changed_reviewed = string_list(
        verification.get("changed_files_reviewed"),
        "evidence.comment_only_verification.changed_files_reviewed",
        errors,
    )
    comment_only_paths = string_list(
        verification.get("comment_only_paths"),
        "evidence.comment_only_verification.comment_only_paths",
        errors,
    )
    explanation_note_paths = string_list(
        verification.get("explanation_note_paths"),
        "evidence.comment_only_verification.explanation_note_paths",
        errors,
    )
    non_comment_paths = string_list(
        verification.get("non_comment_paths"),
        "evidence.comment_only_verification.non_comment_paths",
        errors,
    )
    evidence_commands = string_list(
        verification.get("evidence_commands"),
        "evidence.comment_only_verification.evidence_commands",
        errors,
    )
    uncertainties = string_list(
        verification.get("uncertainties"),
        "evidence.comment_only_verification.uncertainties",
        errors,
    )

    explanations = verification.get("non_comment_path_explanations")
    require(
        isinstance(explanations, list),
        "evidence.comment_only_verification.non_comment_path_explanations must be an array",
        errors,
    )
    explanation_map: dict[str, dict[str, Any]] = {}
    if isinstance(explanations, list):
        for index, item in enumerate(explanations):
            require(
                isinstance(item, dict),
                f"evidence.comment_only_verification.non_comment_path_explanations[{index}] must be an object",
                errors,
            )
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            reason = item.get("reason")
            behavior_safe = item.get("behavior_safe")
            require(
                isinstance(path, str) and bool(path.strip()),
                f"evidence.comment_only_verification.non_comment_path_explanations[{index}].path is required",
                errors,
            )
            require(
                isinstance(reason, str) and bool(reason.strip()),
                f"evidence.comment_only_verification.non_comment_path_explanations[{index}].reason is required",
                errors,
            )
            require(
                behavior_safe in (True, False),
                f"evidence.comment_only_verification.non_comment_path_explanations[{index}].behavior_safe must be boolean",
                errors,
            )
            if isinstance(path, str):
                explanation_map[path] = item

    if not (strict and learning_comments):
        return

    require(scope.get("behavior_change") is False, "strict learning-comments receipts require scope.behavior_change=false", errors)
    require(checked is True, "strict learning-comments receipts require evidence.comment_only_verification.checked=true", errors)
    require(
        result in PASSING_COMMENT_ONLY_RESULTS,
        "strict learning-comments receipts require comment-only verification result to prove comment-only or explanation-note-only changes",
        errors,
    )
    require(
        behavior_assertion is False,
        "strict learning-comments receipts require behavior_change_assertion=false",
        errors,
    )
    require(bool(diff_scope), "strict learning-comments receipts require comment-only diff_scope evidence", errors)
    require(bool(evidence_commands), "strict learning-comments receipts require comment-only evidence_commands", errors)

    command_names = {
        command.get("command")
        for command in as_list(evidence.get("commands"))
        if isinstance(command, dict) and isinstance(command.get("command"), str)
    }
    missing_commands = sorted(set(evidence_commands) - command_names)
    require(
        not missing_commands,
        f"comment_only_verification.evidence_commands not found in evidence.commands: {', '.join(missing_commands)}",
        errors,
    )

    changed_files = string_list(scope.get("changed_files"), "scope.changed_files", errors)
    missing_reviewed = sorted(set(changed_files) - set(changed_reviewed))
    require(
        not missing_reviewed,
        f"comment_only_verification.changed_files_reviewed must include scope.changed_files: {', '.join(missing_reviewed)}",
        errors,
    )

    if result == "comment-only":
        require(not non_comment_paths, "comment-only verification cannot list non_comment_paths", errors)
        require(not explanation_note_paths, "comment-only verification cannot list explanation_note_paths", errors)
    if result in {"comment-and-explanation-note", "explanation-note-only"}:
        require(
            not set(explanation_note_paths) - set(non_comment_paths),
            "explanation_note_paths must also be listed in non_comment_paths",
            errors,
        )
    if result == "explanation-note-only":
        require(
            source_files_changed is False,
            "explanation-note-only verification requires source_files_changed=false",
            errors,
        )
        require(not comment_only_paths, "explanation-note-only verification cannot list comment_only_paths", errors)

    if not changed_files:
        require(
            result == "explanation-note-only",
            "learning-comments receipts with no changed files must use result=explanation-note-only",
            errors,
        )
        require(
            source_files_changed is False,
            "learning-comments receipts with no changed files require source_files_changed=false",
            errors,
        )
        require(
            isinstance(no_source_edit_reason, str) and bool(no_source_edit_reason.strip()),
            "learning-comments receipts with no changed files require no_source_edit_reason",
            errors,
        )

    unexplained_non_comment = sorted(
        path
        for path in non_comment_paths
        if path not in explanation_map or explanation_map[path].get("behavior_safe") is not True
    )
    require(
        not unexplained_non_comment,
        f"non_comment_paths require behavior_safe explanations: {', '.join(unexplained_non_comment)}",
        errors,
    )
    require(
        not uncertainties,
        "strict learning-comments receipts cannot prove comment-only behavior while uncertainties remain",
        errors,
    )


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
    behavior_change = scope.get("behavior_change")
    require(
        behavior_change in (True, False, None),
        "scope.behavior_change must be boolean or null when present",
        errors,
    )

    harness_metrics = receipt.get("harness_metrics")
    if harness_metrics is not None:
        require(isinstance(harness_metrics, dict), "harness_metrics must be an object when present", errors)
        metrics = as_dict(harness_metrics)
        for field in ("context_file_count", "commands_run_count", "changed_file_count"):
            if field in metrics:
                require(isinstance(metrics[field], int) and metrics[field] >= 0, f"harness_metrics.{field} must be a non-negative integer", errors)

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
    if strict and behavior_change is True and tests.get("result") != "red-green":
        require(
            bool(tests.get("skip_reason")),
            "strict mode requires red/green evidence or tests.skip_reason for behavior-changing work",
            errors,
        )
    if strict and tests.get("result") in {"not-run", "blocked", "green-only"}:
        require(bool(tests.get("skip_reason")), "strict mode requires tests.skip_reason when red/green evidence is absent", errors)

    validate_comment_only_verification(
        evidence.get("comment_only_verification"),
        run,
        scope,
        evidence,
        strict,
        errors,
    )

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
