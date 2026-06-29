#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path

from _agent_scope import paths_overlap

# Script flow:
# 1. Read in-flight task metadata from the main checkout.
# 2. Inspect registered git worktrees and each task worktree's status.
# 3. Report active scopes, overlaps, missing worktrees, and stale metadata.
# 4. Optionally emit JSON or fail strict mode on coordination hazards.
#
# Function guide:
# - git_output/repo_root/git_status/parse_worktrees collect git state.
# - task_metadata/enrich_task load local task records and worktree facts.
# - overlap_hazards/untracked_agent_worktrees find coordination hazards.
# - build_report/render_text/main produce human and machine output.


def clean_optional(value: str | None):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def attribution_object(
    *,
    owner: str | None = None,
    owner_label: str | None = None,
    session_id: str | None = None,
    thread_id: str | None = None,
    automation_id: str | None = None,
    run_id: str | None = None,
    metadata_path: str | None = None,
    latest_receipt_path: str | None = None,
    latest_receipt_provenance: str | None = None,
    source: str = "metadata",
):
    payload = {
        "owner": clean_optional(owner),
        "owner_label": clean_optional(owner_label),
        "session_id": clean_optional(session_id),
        "thread_id": clean_optional(thread_id),
        "automation_id": clean_optional(automation_id),
        "run_id": clean_optional(run_id),
        "metadata_path": clean_optional(metadata_path),
        "latest_receipt": {
            "path": clean_optional(latest_receipt_path),
            "provenance": clean_optional(latest_receipt_provenance),
        },
    }
    identity_fields = ("owner", "owner_label", "session_id", "thread_id", "automation_id", "run_id")
    if any(payload.get(field) for field in identity_fields):
        confidence = "metadata" if source == "unknown" else source
    elif source == "inferred":
        confidence = "inferred"
    elif source == "receipt" and payload["latest_receipt"]["path"]:
        confidence = "receipt"
    else:
        confidence = "unknown"
    payload["confidence"] = confidence
    payload["source"] = confidence
    return payload


def attribution_from_task(task: dict):
    existing = task.get("attribution")
    if isinstance(existing, dict):
        latest = existing.get("latest_receipt") if isinstance(existing.get("latest_receipt"), dict) else {}
        return attribution_object(
            owner=existing.get("owner") or task.get("owner"),
            owner_label=existing.get("owner_label") or task.get("owner_label"),
            session_id=existing.get("session_id") or task.get("session_id"),
            thread_id=existing.get("thread_id") or task.get("thread_id"),
            automation_id=existing.get("automation_id") or task.get("automation_id"),
            run_id=existing.get("run_id") or task.get("run_id"),
            metadata_path=existing.get("metadata_path") or task.get("_metadata_path"),
            latest_receipt_path=latest.get("path") or task.get("final_receipt"),
            latest_receipt_provenance=latest.get("provenance") or ("metadata" if task.get("final_receipt") else None),
            source=existing.get("source") or "metadata",
        )
    return attribution_object(
        owner=task.get("owner"),
        owner_label=task.get("owner_label"),
        session_id=task.get("session_id"),
        thread_id=task.get("thread_id"),
        automation_id=task.get("automation_id"),
        run_id=task.get("run_id"),
        metadata_path=task.get("_metadata_path"),
        latest_receipt_path=task.get("final_receipt"),
        latest_receipt_provenance="metadata" if task.get("final_receipt") else None,
        source="metadata",
    )


def inferred_attribution():
    return attribution_object(source="inferred")


def render_attribution(attribution: dict):
    return (
        f"owner={attribution.get('owner') or '(unknown)'} "
        f"label={attribution.get('owner_label') or '(unknown)'} "
        f"session={attribution.get('session_id') or '(unknown)'} "
        f"thread={attribution.get('thread_id') or '(unknown)'} "
        f"automation={attribution.get('automation_id') or '(unknown)'} "
        f"source={attribution.get('source') or 'unknown'}"
    )


def git_output(args, cwd: Path, check=True):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def repo_root():
    stdout, _, _ = git_output(["rev-parse", "--show-toplevel"], Path.cwd())
    return Path(stdout).resolve()


def tasks_dir(root: Path):
    return root / ".agent-workflows" / "tasks"


def default_worktree_root(root: Path):
    return root.parent / f"{root.name}-agent-worktrees"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def task_metadata(root: Path, include_closed: bool):
    directory = tasks_dir(root)
    if not directory.exists():
        return []
    tasks = []
    for path in sorted(directory.glob("*.json")):
        payload = read_json(path)
        if not isinstance(payload, dict):
            continue
        payload["_metadata_path"] = str(path.relative_to(root))
        if include_closed or payload.get("status") == "in-progress":
            tasks.append(payload)
    return tasks


def parse_worktrees(output: str):
    worktrees = []
    current = None
    for line in output.splitlines():
        if not line.strip():
            if current:
                worktrees.append(current)
                current = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                worktrees.append(current)
            current = {"path": value}
        elif current is not None:
            current[key] = value
    if current:
        worktrees.append(current)
    return worktrees


def git_worktrees(root: Path):
    stdout, _, _ = git_output(["worktree", "list", "--porcelain"], root)
    return parse_worktrees(stdout)


def git_status(worktree: Path):
    stdout, stderr, code = git_output(["status", "--short"], worktree, check=False)
    if code != 0:
        return {
            "available": False,
            "dirty": None,
            "entries": [],
            "error": stderr or stdout or "git status failed",
        }
    entries = [line for line in stdout.splitlines() if line.strip()]
    return {"available": True, "dirty": bool(entries), "entries": entries, "error": None}


def branch_name(worktree: Path):
    stdout, _, code = git_output(["branch", "--show-current"], worktree, check=False)
    return stdout if code == 0 else ""


def short_head(worktree: Path):
    stdout, _, code = git_output(["rev-parse", "--short", "HEAD"], worktree, check=False)
    return stdout if code == 0 else ""


def parse_datetime(value: str | None):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def lease_expired(task: dict):
    expires = parse_datetime(task.get("lease_expires_at"))
    return bool(expires and expires < datetime.now(timezone.utc))


def enrich_task(task: dict, registered: dict[str, dict]):
    worktree_value = str(task.get("worktree") or "").strip()
    worktree_path = Path(worktree_value).expanduser() if worktree_value else None
    worktree_key = str(worktree_path.resolve()) if worktree_path else ""
    exists = bool(worktree_path and worktree_path.exists())
    worktree_info = registered.get(worktree_key)
    status = git_status(worktree_path) if exists else {
        "available": False,
        "dirty": None,
        "entries": [],
        "error": "worktree path is missing",
    }
    current_branch = branch_name(worktree_path) if exists else ""
    warnings = []
    if task.get("status") == "in-progress" and not task.get("scope"):
        warnings.append("active task has unknown scope")
    if task.get("status") == "in-progress" and lease_expired(task):
        warnings.append("task lease has expired")
    if not exists:
        warnings.append("worktree path is missing")
    elif not worktree_info:
        warnings.append("worktree is not registered by git worktree list")
    if current_branch and task.get("branch") and current_branch != task.get("branch"):
        warnings.append(f"metadata branch {task.get('branch')} does not match worktree branch {current_branch}")
    if status.get("error"):
        warnings.append(status["error"])
    attribution = attribution_from_task(task)
    return {
        "task_id": task.get("task_id") or task.get("id") or "unknown",
        "run_id": task.get("run_id") or "",
        "title": task.get("title") or "",
        "status": task.get("status") or "unknown",
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "owner": task.get("owner"),
        "owner_label": task.get("owner_label"),
        "session_id": task.get("session_id"),
        "thread_id": task.get("thread_id"),
        "automation_id": task.get("automation_id"),
        "attribution": attribution,
        "heartbeat_at": task.get("heartbeat_at"),
        "lease_expires_at": task.get("lease_expires_at"),
        "lease_expired": lease_expired(task),
        "final_receipt": task.get("final_receipt"),
        "branch": task.get("branch") or "",
        "current_branch": current_branch,
        "head": short_head(worktree_path) if exists else "",
        "worktree": worktree_key,
        "worktree_exists": exists,
        "worktree_registered": bool(worktree_info),
        "scope": task.get("scope") or [],
        "dirty": status.get("dirty"),
        "status_entries": status.get("entries") or [],
        "metadata_path": task.get("_metadata_path"),
        "task_packet": task.get("task_packet"),
        "receipt_template": task.get("receipt_template"),
        "warnings": warnings,
    }


def overlap_hazards(tasks: list[dict]):
    active = [task for task in tasks if task.get("status") == "in-progress"]
    hazards = []
    for left_index, left in enumerate(active):
        left_scope = left.get("scope") or []
        for right in active[left_index + 1:]:
            right_scope = right.get("scope") or []
            for left_path in left_scope:
                for right_path in right_scope:
                    if paths_overlap(left_path, right_path):
                        hazards.append(
                            {
                                "type": "scope-overlap",
                                "tasks": [left["task_id"], right["task_id"]],
                                "attributions": [left.get("attribution") or attribution_object(source="unknown"), right.get("attribution") or attribution_object(source="unknown")],
                                "paths": [left_path, right_path],
                                "message": f"{left['task_id']}:{left_path} overlaps {right['task_id']}:{right_path}",
                            }
                        )
    return hazards


def untracked_agent_worktrees(root: Path, registered: list[dict], tasks: list[dict]):
    known = {task.get("worktree") for task in tasks if task.get("worktree")}
    agent_root = default_worktree_root(root).resolve()
    untracked = []
    for worktree in registered:
        path = Path(worktree["path"]).resolve()
        branch = worktree.get("branch", "")
        if str(path) == str(root):
            continue
        if str(path) in known:
            continue
        under_agent_root = str(path).startswith(f"{agent_root}/")
        task_branch = "refs/heads/codex/task-" in branch or branch.startswith("codex/task-")
        if under_agent_root or task_branch:
            untracked.append({"path": str(path), "branch": branch, "attribution": inferred_attribution()})
    return untracked


def build_report(root: Path, include_closed: bool):
    raw_worktrees = git_worktrees(root)
    registered = {str(Path(item["path"]).resolve()): item for item in raw_worktrees}
    tasks = [enrich_task(task, registered) for task in task_metadata(root, include_closed)]
    hazards = overlap_hazards(tasks)
    for task in tasks:
        for hazard in hazards:
            if task["task_id"] in hazard["tasks"]:
                task["warnings"].append(hazard["message"])
    stale = []
    hazard_messages = {hazard["message"] for hazard in hazards}
    for task in tasks:
        if task.get("status") != "in-progress":
            continue
        for warning in task["warnings"]:
            if warning not in ("active task has unknown scope",) and warning not in hazard_messages:
                stale.append({"task_id": task["task_id"], "message": warning, "attribution": task.get("attribution") or attribution_object(source="unknown")})
    unknown_scope = [
        {"task_id": task["task_id"], "message": "active task has unknown scope", "attribution": task.get("attribution") or attribution_object(source="unknown")}
        for task in tasks
        if task.get("status") == "in-progress" and not task.get("scope")
    ]
    dirty_worktree_tasks = [
        {"task_id": task["task_id"], "message": "task worktree is dirty", "attribution": task.get("attribution") or attribution_object(source="unknown")}
        for task in tasks
        if task.get("dirty")
    ]
    untracked = untracked_agent_worktrees(root, raw_worktrees, tasks)
    return {
        "schema_version": 1,
        "repo_root": str(root),
        "task_count": len(tasks),
        "active_task_count": len([task for task in tasks if task.get("status") == "in-progress"]),
        "registered_worktree_count": len(raw_worktrees),
        "tasks": tasks,
        "hazards": hazards,
        "stale_tasks": stale,
        "unknown_scope_tasks": unknown_scope,
        "dirty_worktree_tasks": dirty_worktree_tasks,
        "untracked_agent_worktrees": untracked,
    }


def render_text(report: dict):
    lines = [
        "Agent task status:",
        f" - repo: {report['repo_root']}",
        f" - active tasks: {report['active_task_count']}",
        f" - registered worktrees: {report['registered_worktree_count']}",
    ]
    if report["hazards"] or report["stale_tasks"] or report["unknown_scope_tasks"] or report["dirty_worktree_tasks"] or report["untracked_agent_worktrees"]:
        lines.append(" - coordination warnings: yes")
    else:
        lines.append(" - coordination warnings: none")

    if not report["tasks"]:
        lines.append("")
        lines.append("No local agent task metadata found.")
        return "\n".join(lines)

    for task in report["tasks"]:
        scope = ", ".join(task["scope"]) if task["scope"] else "(unknown)"
        dirty = "dirty" if task["dirty"] else "clean"
        if task["dirty"] is None:
            dirty = "unavailable"
        registered = "registered" if task["worktree_registered"] else "not-registered"
        lines.extend(
            [
                "",
                f"{task['task_id']} [{task['status']}]",
                f" - run id: {task['run_id'] or '(unknown)'}",
                f" - scope: {scope}",
                f" - branch: {task['branch']}",
                f" - worktree: {task['worktree']} ({registered}, {dirty})",
                f" - metadata: {task['metadata_path']}",
            ]
        )
        if task.get("owner") or task.get("session_id"):
            lines.append(f" - owner/session: {task.get('owner') or '(none)'} / {task.get('session_id') or '(none)'}")
        lines.append(f" - attribution: {render_attribution(task.get('attribution') or attribution_object(source='unknown'))}")
        if task.get("lease_expires_at"):
            lease = "expired" if task.get("lease_expired") else "active"
            lines.append(f" - lease: {lease} until {task['lease_expires_at']}")
        if task.get("final_receipt"):
            lines.append(f" - final receipt: {task['final_receipt']}")
        if task["status_entries"]:
            lines.append(f" - changed files: {len(task['status_entries'])}")
        for warning in task["warnings"]:
            lines.append(f" - warning: {warning}")

    if report["untracked_agent_worktrees"]:
        lines.append("")
        lines.append("Untracked agent worktrees:")
        for item in report["untracked_agent_worktrees"]:
            lines.append(
                f" - {item['path']} ({item.get('branch') or 'unknown branch'}; "
                f"{render_attribution(item.get('attribution') or attribution_object(source='unknown'))})"
            )
    return "\n".join(lines)


def strict_failures(report: dict):
    failures = []
    failures.extend(item["message"] for item in report["hazards"])
    failures.extend(f"{item['task_id']}: {item['message']}" for item in report["stale_tasks"])
    failures.extend(f"{item['task_id']}: {item['message']}" for item in report["unknown_scope_tasks"])
    for item in report["untracked_agent_worktrees"]:
        failures.append(f"untracked agent worktree: {item['path']}")
    return failures


def parse_args():
    parser = argparse.ArgumentParser(description="Report local agent task and worktree coordination state")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--include-closed", action="store_true", help="Include metadata whose status is not in-progress")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when coordination hazards are present")
    return parser.parse_args()


def main():
    args = parse_args()
    report = build_report(repo_root(), args.include_closed)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))

    failures = strict_failures(report)
    if args.strict and failures:
        if not args.json:
            print("")
            print("Strict mode failures:")
            for failure in failures:
                print(f" - {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
