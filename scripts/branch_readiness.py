#!/usr/bin/env python3
"""Aggregate local branch/PR readiness evidence without writes or network calls."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import check_doc_impact
import changelog_update
from verify_agent_receipt import validate_receipt

SCRIPT_DIR = Path(__file__).resolve().parent

PASSING_CHECK_STATES = {"success", "passed", "pass", "neutral"}
NONPASSING_CHECK_STATES = {
    "pending",
    "failed",
    "failure",
    "error",
    "missing",
    "unknown",
    "skipped",
    "cancelled",
    "canceled",
    "timed_out",
    "timed-out",
    "action_required",
    "startup_failure",
}
PASSING_DISPOSITIONS = {"pass", "passed", "approved", "accepted", "ready", "clean", "no-findings"}
FAILING_DISPOSITIONS = {"fail", "failed", "blocked", "not-ready", "changes-requested", "rejected"}
DEFAULT_CHECK_WARNING = "No local CI/check input supplied; hosted check state was not verified by this command."


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def git_output(repo: Path, args: list[str]) -> tuple[str, str, int]:
    result = run_git(repo, args)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def repo_root(path: Path) -> Path:
    stdout, stderr, code = git_output(path, ["rev-parse", "--show-toplevel"])
    if code != 0:
        raise SystemExit(stderr or stdout or f"Not a git repository: {path}")
    return Path(stdout).resolve()


def git_common_dir(root: Path) -> Path:
    stdout, stderr, code = git_output(root, ["rev-parse", "--git-common-dir"])
    if code != 0:
        raise SystemExit(stderr or stdout or "Unable to resolve git common dir.")
    path = Path(stdout)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def primary_checkout(root: Path) -> Path:
    common = git_common_dir(root)
    if common.name == ".git":
        return common.parent.resolve()
    return root


def current_branch(repo: Path) -> str:
    stdout, _, code = git_output(repo, ["branch", "--show-current"])
    return stdout if code == 0 else ""


def ref_commit(repo: Path, ref: str) -> tuple[str | None, str | None]:
    if not ref:
        return None, "empty ref"
    stdout, stderr, code = git_output(repo, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    if code == 0 and stdout:
        return stdout, None
    return None, stderr or f"ref not found: {ref}"


def default_base_ref(repo: Path) -> str:
    stdout, _, code = git_output(repo, ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"])
    if code == 0 and stdout and ref_commit(repo, stdout)[0]:
        return stdout
    for candidate in ("origin/main", "origin/master", "main", "master"):
        if ref_commit(repo, candidate)[0]:
            return candidate
    return ""


def status_entries(repo: Path) -> list[dict[str, str]]:
    stdout, stderr, code = git_output(repo, ["status", "--porcelain=v1", "--untracked-files=all"])
    if code != 0:
        raise SystemExit(stderr or stdout or "Unable to inspect git status.")
    entries: list[dict[str, str]] = []
    for line in stdout.splitlines():
        if not line:
            continue
        code_value = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        entries.append({"code": code_value, "path": path})
    return entries


def dirty_summary(entries: list[dict[str, str]]) -> dict[str, Any]:
    tracked = [entry["path"] for entry in entries if entry["code"] != "??"]
    untracked = [entry["path"] for entry in entries if entry["code"] == "??"]
    staged = [entry["path"] for entry in entries if entry["code"] != "??" and entry["code"][0] != " "]
    unstaged = [entry["path"] for entry in entries if entry["code"] != "??" and len(entry["code"]) > 1 and entry["code"][1] != " "]
    return {
        "dirty": bool(entries),
        "count": len(entries),
        "tracked_count": len(set(tracked)),
        "untracked_count": len(set(untracked)),
        "staged_count": len(set(staged)),
        "unstaged_count": len(set(unstaged)),
        "entries": entries,
        "changed_files": sorted({entry["path"] for entry in entries}),
    }


def diff_files(repo: Path, base_ref: str, head_ref: str) -> tuple[list[str], str | None]:
    if not base_ref:
        return [], "No base ref was available for branch diff."
    base_commit, base_error = ref_commit(repo, base_ref)
    head_commit, head_error = ref_commit(repo, head_ref)
    if base_error:
        return [], base_error
    if head_error:
        return [], head_error
    stdout, stderr, code = git_output(repo, ["diff", "--name-only", f"{base_commit}...{head_commit}"])
    if code != 0:
        return [], stderr or stdout or "Unable to calculate branch diff."
    return sorted({line.strip() for line in stdout.splitlines() if line.strip()}), None


def branch_freshness(repo: Path, base_ref: str, head_ref: str) -> dict[str, Any]:
    if not base_ref:
        return {
            "checked": False,
            "fresh": False,
            "base_ref": None,
            "message": "No usable base ref found for freshness check.",
            "remote_fetch_performed": False,
        }
    stdout, stderr, code = git_output(repo, ["merge-base", "--is-ancestor", base_ref, head_ref])
    if code == 0:
        return {
            "checked": True,
            "fresh": True,
            "base_ref": base_ref,
            "head_ref": head_ref,
            "message": f"{head_ref} contains {base_ref}.",
            "remote_fetch_performed": False,
        }
    if code == 1:
        return {
            "checked": True,
            "fresh": False,
            "base_ref": base_ref,
            "head_ref": head_ref,
            "message": f"{head_ref} does not contain {base_ref}.",
            "remote_fetch_performed": False,
        }
    return {
        "checked": True,
        "fresh": False,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "message": stderr or stdout or "merge-base freshness check failed.",
        "remote_fetch_performed": False,
    }


def changed_files_for_docs(diff_changed: list[str], dirty: dict[str, Any]) -> list[str]:
    return sorted(set(diff_changed) | set(dirty.get("changed_files") or []))


def no_docs_declaration(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    if args.no_docs_needed and args.no_docs_needed.strip():
        return {"declared": True, "source": "argument", "reason": args.no_docs_needed.strip()}
    env_reason = os.environ.get("DOC_CONTRACT_NO_DOCS_NEEDED", "").strip()
    if env_reason:
        return {"declared": True, "source": "DOC_CONTRACT_NO_DOCS_NEEDED", "reason": env_reason}
    pr_body = os.environ.get("DOC_CONTRACT_PR_BODY", "")
    markers = config.get("no_docs_needed_markers") or ["No docs needed:"]
    for line in pr_body.splitlines():
        lowered = line.lower()
        for marker in markers:
            index = lowered.find(str(marker).lower())
            if index == -1:
                continue
            reason = line[index + len(str(marker)) :].strip()
            if reason and not reason.startswith("<!--"):
                return {"declared": True, "source": "DOC_CONTRACT_PR_BODY", "reason": reason}
    return {"declared": False, "source": None, "reason": None}


def docs_impact_section(repo: Path, args: argparse.Namespace, changed_files: list[str]) -> dict[str, Any]:
    config_path = Path(args.config).expanduser()
    if not config_path.is_absolute():
        config_path = repo / config_path
    config = check_doc_impact.load_config(config_path)
    missing_required = [
        path
        for path in config.get("required_files", [])
        if not (repo / check_doc_impact.normalize_path(path)).exists()
    ]
    waiver = no_docs_declaration(args, config)
    evaluation = check_doc_impact.evaluate(changed_files, config, waiver["declared"])
    categories = [
        {
            "category": category,
            "changed_files": sorted(paths),
            "suggested_doc_paths": config["category_doc_paths"].get(category, config["doc_paths"]),
            "covered": category in evaluation.covered_categories,
        }
        for category, paths in sorted(evaluation.categories.items())
    ]
    return {
        "source_command": "repo_contract_kit.py doc-impact --working-tree/branch --json",
        "config": str(config_path),
        "changed_files": evaluation.changed_files,
        "docs_changed": evaluation.docs_changed,
        "categories": categories,
        "missing_categories": sorted(evaluation.missing_categories),
        "required_files_missing": missing_required,
        "no_docs_needed": waiver,
        "result": "missing-docs" if evaluation.failed else "covered-or-no-impact",
        "passed": not evaluation.failed and not missing_required,
    }


def changelog_section(repo: Path, args: argparse.Namespace, changed_files: list[str]) -> dict[str, Any]:
    changelog_args = argparse.Namespace(
        repo=str(repo),
        config=args.config,
        changed_files=changed_files,
        staged=False,
        working_tree=False,
        docs_impact_json=None,
        summary=None,
        section=None,
        version=None,
        bump=None,
        check=True,
    )
    payload, exit_code = changelog_update.build_report(changelog_args, repo)
    payload["source_command"] = "repo_contract_kit.py changelog-update --check --json"
    payload["exit_code"] = exit_code
    return payload


def load_json_file(repo: Path, value: str) -> tuple[Path, Any]:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo / path
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"JSON input not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def normalize_check_state(value: Any) -> str:
    state = str(value or "unknown").strip().lower().replace(" ", "-")
    return state or "unknown"


def checks_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_checks = payload
    elif isinstance(payload, dict):
        raw_checks = payload.get("checks") or payload.get("check_runs") or payload.get("statuses") or []
    else:
        raise SystemExit("CI/check input must be a JSON object or array.")
    if not isinstance(raw_checks, list):
        raise SystemExit("CI/check input field must be an array.")
    checks = []
    for index, item in enumerate(raw_checks):
        if not isinstance(item, dict):
            raise SystemExit(f"CI/check input item {index} must be an object.")
        name = str(item.get("name") or item.get("context") or item.get("check") or "").strip()
        if not name:
            raise SystemExit(f"CI/check input item {index} is missing name/context.")
        advisory = bool(item.get("advisory"))
        required = bool(item.get("required", not advisory)) and not advisory
        state = normalize_check_state(item.get("state") or item.get("conclusion") or item.get("status"))
        if state not in PASSING_CHECK_STATES and state not in NONPASSING_CHECK_STATES:
            state = "unknown"
        checks.append(
            {
                "name": name,
                "state": state,
                "required": required,
                "advisory": not required,
                "url": item.get("url") or item.get("details_url"),
                "summary": item.get("summary") or item.get("description"),
            }
        )
    return checks


def ci_section(repo: Path, args: argparse.Namespace) -> dict[str, Any]:
    if not args.checks_json:
        return {
            "provided": False,
            "path": None,
            "checks": [],
            "required_total": 0,
            "required_passing": 0,
            "required_blocking": [],
            "advisory_nonpassing": [],
            "result": "omitted",
        }
    path, payload = load_json_file(repo, args.checks_json)
    checks = checks_from_payload(payload)
    required_blocking = [
        check for check in checks if check["required"] and check["state"] not in PASSING_CHECK_STATES
    ]
    advisory_nonpassing = [
        check for check in checks if not check["required"] and check["state"] not in PASSING_CHECK_STATES
    ]
    required_total = len([check for check in checks if check["required"]])
    return {
        "provided": True,
        "path": str(path),
        "checks": checks,
        "required_total": required_total,
        "required_passing": required_total - len(required_blocking),
        "required_blocking": required_blocking,
        "advisory_nonpassing": advisory_nonpassing,
        "result": "blocked" if required_blocking else "passed",
    }


def validate_receipt_path(repo: Path, value: str) -> dict[str, Any]:
    path, payload = load_json_file(repo, value)
    errors = validate_receipt(payload, strict=True)
    run = payload.get("run") if isinstance(payload, dict) else {}
    run_status = run.get("status") if isinstance(run, dict) else None
    if run_status in {"fail", "blocked"}:
        errors.append(f"receipt run.status is {run_status}")
    return {
        "path": str(path),
        "passed": not errors,
        "run_status": run_status,
        "errors": errors,
    }


def receipt_section(repo: Path, args: argparse.Namespace) -> dict[str, Any]:
    receipts = [validate_receipt_path(repo, value) for value in args.receipt or []]
    return {
        "provided": bool(receipts),
        "receipts": receipts,
        "passed": all(item["passed"] for item in receipts),
    }


def review_disposition_status(payload: dict[str, Any]) -> str:
    for key in ("result", "status", "decision", "conclusion"):
        value = str(payload.get(key) or "").strip().lower()
        if value:
            return value
    return "unknown"


def review_disposition_section(repo: Path, args: argparse.Namespace) -> dict[str, Any]:
    if not args.review_disposition_json:
        return {"provided": False, "path": None, "passed": True, "errors": []}
    path, payload = load_json_file(repo, args.review_disposition_json)
    errors = []
    if not isinstance(payload, dict):
        errors.append("review disposition JSON must be an object")
        status = "invalid"
    else:
        status = review_disposition_status(payload)
        if status in PASSING_DISPOSITIONS:
            pass
        elif status in FAILING_DISPOSITIONS:
            errors.append(f"review disposition is {status}")
        else:
            errors.append(f"review disposition status is unknown: {status}")
        blockers = payload.get("blockers")
        if isinstance(blockers, list) and blockers:
            errors.append("review disposition includes blockers")
        findings = payload.get("findings")
        open_findings = [
            item
            for item in (findings if isinstance(findings, list) else [])
            if isinstance(item, dict) and str(item.get("status") or "open").lower() in {"open", "accepted"}
        ]
        if open_findings:
            errors.append("review disposition includes open or accepted findings")
    return {
        "provided": True,
        "path": str(path),
        "status": status,
        "passed": not errors,
        "errors": errors,
    }


def task_metadata_candidates(primary: Path, repo: Path, branch: str, explicit_task: str) -> list[dict[str, Any]]:
    tasks_root = primary / ".agent-workflows" / "tasks"
    if not tasks_root.exists():
        return []
    candidates = []
    for path in sorted(tasks_root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        task_id = str(payload.get("task_id") or payload.get("id") or "").strip()
        if explicit_task and task_id.lower() != explicit_task.lower():
            continue
        match = bool(explicit_task)
        worktree = str(payload.get("worktree") or "").strip()
        if worktree:
            try:
                match = match or Path(worktree).expanduser().resolve() == repo
            except OSError:
                pass
        if branch and payload.get("branch") == branch:
            match = True
        if match:
            payload["_metadata_path"] = str(path)
            candidates.append(payload)
    return candidates


def run_json(command: list[str], cwd: Path) -> tuple[dict[str, Any], int, str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"stdout": result.stdout, "stderr": result.stderr, "parse_error": True}
    return payload if isinstance(payload, dict) else {"value": payload}, result.returncode, result.stderr.strip()


def task_readiness_section(primary: Path, repo: Path, args: argparse.Namespace, branch: str) -> dict[str, Any]:
    candidates = task_metadata_candidates(primary, repo, branch, args.task)
    if not candidates:
        return {
            "available": False,
            "task_id": args.task or None,
            "source_command": None,
            "passed": None,
            "reason": "No prepared task metadata matched this branch/worktree.",
        }
    if len(candidates) > 1:
        return {
            "available": False,
            "task_id": args.task or None,
            "source_command": None,
            "passed": None,
            "reason": "Multiple task metadata entries matched; pass --task to disambiguate.",
            "matches": [item.get("task_id") or item.get("id") for item in candidates],
        }
    metadata = candidates[0]
    task_id = metadata.get("task_id") or metadata.get("id") or args.task
    command = [sys.executable, str(SCRIPT_DIR / "agent_task_ready.py"), "--task", str(task_id), "--json"]
    if args.base_ref:
        command.extend(["--base-ref", args.base_ref])
    if args.task_receipt:
        command.extend(["--receipt", args.task_receipt])
    worktree = Path(str(metadata.get("worktree") or repo)).expanduser()
    payload, exit_code, stderr = run_json(command, worktree if worktree.exists() else repo)
    return {
        "available": True,
        "task_id": task_id,
        "metadata_path": metadata.get("_metadata_path"),
        "worktree": str(worktree),
        "source_command": " ".join(command),
        "exit_code": exit_code,
        "passed": exit_code == 0 and bool(payload.get("ready", False)),
        "stderr": stderr,
        "report": payload,
    }


def task_status_section(primary: Path) -> dict[str, Any]:
    script = SCRIPT_DIR / "agent_task_status.py"
    if not script.exists():
        return {"available": False, "passed": True, "reason": f"Task status script not found: {script}"}
    payload, exit_code, stderr = run_json([sys.executable, str(script), "--json", "--include-closed"], primary)
    hazards = payload.get("hazards") if isinstance(payload.get("hazards"), list) else []
    stale = payload.get("stale_tasks") if isinstance(payload.get("stale_tasks"), list) else []
    unknown_scope = payload.get("unknown_scope_tasks") if isinstance(payload.get("unknown_scope_tasks"), list) else []
    dirty_tasks = payload.get("dirty_worktree_tasks") if isinstance(payload.get("dirty_worktree_tasks"), list) else []
    return {
        "available": True,
        "source_command": "make agent-task-status TASK_STATUS_INCLUDE_CLOSED=1 TASK_STATUS_JSON=1",
        "exit_code": exit_code,
        "stderr": stderr,
        "active_task_count": payload.get("active_task_count", 0),
        "hazards": hazards,
        "stale_tasks": stale,
        "unknown_scope_tasks": unknown_scope,
        "dirty_worktree_tasks": dirty_tasks,
        "passed": exit_code == 0 and not hazards and not stale and not unknown_scope,
    }


def ref_metadata(repo: Path, target_ref: str, base_ref: str, head_ref: str) -> dict[str, Any]:
    branch = current_branch(repo)
    refs = {}
    for key, value in (("target_ref", target_ref), ("base_ref", base_ref), ("head_ref", head_ref)):
        commit, error = ref_commit(repo, value)
        refs[key] = {
            "name": value or None,
            "exists": bool(commit),
            "commit": commit,
            "error": error,
        }
    refs["current_branch"] = branch
    return refs


def append_blockers_and_warnings(payload: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    dirty = payload["evidence"]["git"]["dirty"]
    if dirty["dirty"]:
        blockers.append({"code": "dirty_checkout", "message": "Working tree has uncommitted changes.", "count": dirty["count"]})
    freshness = payload["evidence"]["git"]["base_freshness"]
    if not freshness["fresh"]:
        blockers.append({"code": "stale_or_unknown_base", "message": freshness["message"]})
    if payload["evidence"]["git"].get("diff_error"):
        blockers.append({"code": "diff_unavailable", "message": payload["evidence"]["git"]["diff_error"]})
    if not payload["evidence"]["git"]["branch_changed_files"]:
        warnings.append({"code": "no_branch_changes", "message": "No branch changes were detected relative to the resolved base ref."})

    docs = payload["evidence"]["docs_impact"]
    if docs["required_files_missing"]:
        blockers.append({"code": "required_docs_missing", "message": "Required documentation contract files are missing.", "paths": docs["required_files_missing"]})
    if docs["missing_categories"] and not docs["no_docs_needed"]["declared"]:
        blockers.append({"code": "missing_docs", "message": "Documentation impact is missing required coverage.", "categories": docs["missing_categories"]})
    if docs["missing_categories"] and docs["no_docs_needed"]["declared"]:
        warnings.append({"code": "docs_waived", "message": "Documentation impact was waived by explicit no-docs-needed declaration.", "reason": docs["no_docs_needed"]["reason"]})
    if docs["no_docs_needed"]["declared"]:
        warnings.append({"code": "no_docs_needed_recorded", "message": "Explicit no-docs-needed declaration recorded.", "source": docs["no_docs_needed"]["source"], "reason": docs["no_docs_needed"]["reason"]})

    changelog = payload["evidence"]["changelog_version"]
    if changelog.get("exit_code"):
        blockers.append({"code": "changelog_required", "message": "Release-impacting changes require changelog/version evidence.", "result": changelog.get("result")})
    versioning = changelog.get("versioning") or {}
    if versioning.get("version_present") and not versioning.get("version_valid"):
        blockers.append({"code": "invalid_version", "message": versioning.get("version_error") or "VERSION is invalid."})

    checks = payload["evidence"]["checks"]
    if not checks["provided"]:
        warnings.append({"code": "checks_omitted", "message": DEFAULT_CHECK_WARNING})
    for check in checks.get("required_blocking", []):
        blockers.append({"code": "required_check_not_passing", "message": f"Required check {check['name']} is {check['state']}.", "check": check})
    for check in checks.get("advisory_nonpassing", []):
        warnings.append({"code": "advisory_check_not_passing", "message": f"Advisory check {check['name']} is {check['state']}.", "check": check})

    receipts = payload["evidence"]["receipts"]
    for receipt in receipts.get("receipts", []):
        if not receipt["passed"]:
            blockers.append({"code": "receipt_invalid", "message": "Receipt validation failed.", "path": receipt["path"], "errors": receipt["errors"]})

    review = payload["evidence"]["review_disposition"]
    if review["provided"] and not review["passed"]:
        blockers.append({"code": "review_disposition_blocked", "message": "Review disposition evidence is invalid or failing.", "path": review["path"], "errors": review["errors"]})

    task_ready = payload["evidence"]["task_readiness"]
    if task_ready["available"] and not task_ready["passed"]:
        blockers.append({"code": "task_readiness_blocked", "message": "Per-task readiness did not pass.", "task_id": task_ready.get("task_id")})
    if not task_ready["available"]:
        warnings.append({"code": "task_readiness_omitted", "message": task_ready["reason"]})

    task_status = payload["evidence"]["task_status"]
    if task_status["available"] and not task_status["passed"]:
        blockers.append({"code": "task_status_hazards", "message": "Task status reported hazards or stale/unknown-scope tasks."})
    if not task_status["available"]:
        warnings.append({"code": "task_status_unavailable", "message": task_status["reason"]})


def next_safe_commands(blockers: list[dict[str, Any]], ready: bool, task_available: bool) -> list[str]:
    codes = {item.get("code") for item in blockers}
    commands: list[str] = []
    if "dirty_checkout" in codes:
        commands.append("git status --short")
    if "stale_or_unknown_base" in codes or "diff_unavailable" in codes:
        commands.append("git log --oneline --decorate --graph --max-count=20")
    if "missing_docs" in codes or "required_docs_missing" in codes:
        commands.append("make docs-check")
    if "changelog_required" in codes or "invalid_version" in codes:
        commands.append("make agent-changelog-update CHANGELOG_UPDATE_CHECK=1")
        commands.append("make version-check")
    if "required_check_not_passing" in codes:
        commands.append("rerun or inspect the local CI/check export before merge governance")
    if "receipt_invalid" in codes:
        commands.append("make agent-receipt-verify RECEIPT=<path>")
    if "review_disposition_blocked" in codes:
        commands.append("refresh the local review disposition JSON")
    if "task_readiness_blocked" in codes and task_available:
        commands.append("make agent-task-ready TASK=<id> TASK_READY_JSON=1")
    if "task_status_hazards" in codes:
        commands.append("make agent-task-status TASK_STATUS_INCLUDE_CLOSED=1 TASK_STATUS_STRICT=1")
    if ready:
        commands.extend(
            [
                "make docs-check",
                "make version-check",
                "git diff --check",
                "review this JSON before PR update, merge queue, auto-merge, or branch-protection changes",
            ]
        )
    deduped: list[str] = []
    for command in commands:
        if command not in deduped:
            deduped.append(command)
    return deduped or ["make agent-branch-readiness BRANCH_READY_JSON=1"]


def build_report(args: argparse.Namespace, repo_arg: Path) -> tuple[dict[str, Any], int]:
    repo = repo_root(repo_arg)
    primary = primary_checkout(repo)
    base_ref = args.base_ref or default_base_ref(repo)
    head_ref = args.head_ref or "HEAD"
    target_ref = args.target_ref or base_ref
    branch = current_branch(repo)
    refs = ref_metadata(repo, target_ref, base_ref, head_ref)
    entries = status_entries(repo)
    dirty = dirty_summary(entries)
    branch_changed, diff_error = diff_files(repo, base_ref, head_ref)
    changed_for_docs = changed_files_for_docs(branch_changed, dirty)
    freshness = branch_freshness(repo, base_ref, head_ref)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "command": "branch-readiness",
        "created_at": now_iso(),
        "repo_root": str(repo),
        "primary_checkout": str(primary),
        "target_repo_writes": False,
        "sidecar_writes": False,
        "network_calls": False,
        "hosted_mutations": False,
        "refs": refs,
        "evidence": {
            "git": {
                "current_branch": branch,
                "dirty": dirty,
                "branch_changed_files": branch_changed,
                "changed_files_for_local_gates": changed_for_docs,
                "diff_error": diff_error,
                "base_freshness": freshness,
            },
            "docs_impact": docs_impact_section(repo, args, changed_for_docs),
            "changelog_version": changelog_section(repo, args, changed_for_docs),
            "checks": ci_section(repo, args),
            "receipts": receipt_section(repo, args),
            "review_disposition": review_disposition_section(repo, args),
            "task_readiness": task_readiness_section(primary, repo, args, branch),
            "task_status": task_status_section(primary),
        },
        "no_write_proof": {
            "target_repo_writes": False,
            "sidecar_writes": False,
            "network_calls": False,
            "github_api_calls": False,
            "pr_mutations": False,
            "merge_queue_actions": False,
            "branch_protection_edits": False,
            "notes": [
                "The command reads git state, local config, local JSON inputs, and local receipts only.",
                "It does not create sidecar directories, write receipts, call hosted providers, or mutate PR/branch governance.",
            ],
        },
    }
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    append_blockers_and_warnings(payload, blockers, warnings)
    ready = not blockers
    payload["ready"] = ready
    payload["result"] = "ready" if ready else "blocked"
    payload["blockers"] = blockers
    payload["warnings"] = warnings
    payload["next_safe_commands"] = next_safe_commands(blockers, ready, payload["evidence"]["task_readiness"]["available"])
    payload["exit_code"] = 0 if ready else 1
    return payload, payload["exit_code"]


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Branch readiness:",
        f" - repo: {payload['repo_root']}",
        f" - result: {payload['result']}",
        f" - branch: {payload['evidence']['git']['current_branch'] or '(detached)'}",
        f" - base ref: {payload['refs']['base_ref']['name'] or '(unknown)'}",
        f" - changed files: {len(payload['evidence']['git']['branch_changed_files'])}",
        f" - target writes: {str(payload['target_repo_writes']).lower()}",
        f" - sidecar writes: {str(payload['sidecar_writes']).lower()}",
    ]
    if payload["blockers"]:
        lines.append(" - blockers:")
        for item in payload["blockers"]:
            lines.append(f"   - {item['code']}: {item['message']}")
    if payload["warnings"]:
        lines.append(" - warnings:")
        for item in payload["warnings"]:
            lines.append(f"   - {item['code']}: {item['message']}")
    lines.append(" - next safe commands:")
    for command in payload["next_safe_commands"]:
        lines.append(f"   - {command}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Target git repository. Defaults to the current directory.")
    parser.add_argument("--base-ref", default="", help="Base ref for local branch diff and freshness. Defaults to origin HEAD/main/master or local main/master.")
    parser.add_argument("--head-ref", default="HEAD", help="Head ref for branch diff. Defaults to HEAD.")
    parser.add_argument("--target-ref", default="", help="Target ref metadata to report. Defaults to the resolved base ref.")
    parser.add_argument("--config", default=check_doc_impact.CONFIG_FILE, help="Docs contract config path.")
    parser.add_argument("--no-docs-needed", default="", help="Explicit no-docs-needed reason to record for this readiness run.")
    parser.add_argument("--checks-json", default="", help="Local JSON export of required/advisory checks.")
    parser.add_argument("--receipt", action="append", help="Local agent receipt JSON to validate. Can be repeated.")
    parser.add_argument("--review-disposition-json", default="", help="Local review disposition JSON to validate.")
    parser.add_argument("--task", default="", help="Prepared task id to aggregate through agent-task-ready when available.")
    parser.add_argument("--task-receipt", default="", help="Receipt path passed through to agent-task-ready.")
    parser.add_argument("--format", choices=["text", "json"], default=None)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload, exit_code = build_report(args, Path(args.repo).expanduser())
    output_format = args.format or ("json" if args.json else "text")
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
