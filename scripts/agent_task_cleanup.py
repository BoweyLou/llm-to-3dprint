#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta, timezone
import json
import subprocess
from pathlib import Path

from _agent_scope import paths_overlap

# Script flow:
# 1. Resolve the primary checkout, even when invoked from a linked worktree.
# 2. Inspect registered git worktrees and local task metadata.
# 3. Classify task worktrees, especially nested task-worktree pools.
# 4. Optionally move nested worktrees into the primary checkout's flat pool.
# 5. Optionally close out clean terminal task worktrees after safety checks.
#
# Function guide:
# - git_output/repo_roots/default_worktree_root collect repo topology.
# - parse_worktrees/git_status/task_metadata build the inventory.
# - classify_worktree/closeout_inventory/build_report identify cleanup candidates.
# - move_nested_worktrees/remove_closeout_worktrees/render_text/main apply or report cleanup actions.

TERMINAL_STATUSES = {"done", "blocked", "abandoned"}
TERMINAL_TIME_FIELDS = ("completed_at", "blocked_at", "abandoned_at", "updated_at", "created_at")


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


def current_repo_root():
    stdout, _, _ = git_output(["rev-parse", "--show-toplevel"], Path.cwd())
    return Path(stdout).resolve()


def git_common_dir(root: Path):
    stdout, _, _ = git_output(["rev-parse", "--git-common-dir"], root)
    common = Path(stdout)
    if not common.is_absolute():
        common = root / common
    return common.resolve()


def primary_worktree_root(root: Path):
    common = git_common_dir(root)
    if common.name == ".git":
        return common.parent.resolve()
    return root


def default_worktree_root(root: Path):
    return root.parent / f"{root.name}-agent-worktrees"


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


def git_status(path: Path):
    stdout, stderr, code = git_output(["status", "--short", "--branch"], path, check=False)
    if code != 0:
        return {"available": False, "dirty": None, "entries": [], "error": stderr or stdout or "git status failed"}
    entries = [line for line in stdout.splitlines() if line.strip()]
    dirty_entries = [line for line in entries if not line.startswith("## ")]
    return {"available": True, "dirty": bool(dirty_entries), "entries": entries, "error": None}


def git_status_short(path: Path):
    stdout, stderr, code = git_output(["status", "--short"], path, check=False)
    if code != 0:
        return {"available": False, "dirty": None, "entries": [], "error": stderr or stdout or "git status failed"}
    entries = [line for line in stdout.splitlines() if line.strip()]
    return {"available": True, "dirty": bool(entries), "entries": entries, "error": None}


def git_head(path: Path):
    stdout, stderr, code = git_output(["rev-parse", "HEAD"], path, check=False)
    if code != 0:
        return "", stderr or stdout or "git rev-parse failed"
    return stdout, ""


def branch_merged_into_primary(root: Path, worktree: Path):
    head, error = git_head(worktree)
    if error:
        return False, error
    _, stderr, code = git_output(["merge-base", "--is-ancestor", head, "HEAD"], root, check=False)
    if code == 0:
        return True, ""
    return False, stderr or f"branch head {head[:12]} is not reachable from primary HEAD"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def task_metadata(root: Path):
    tasks = []
    directory = root / ".agent-workflows" / "tasks"
    if not directory.exists():
        return tasks
    for path in sorted(directory.glob("*.json")):
        payload = read_json(path)
        if isinstance(payload, dict):
            payload["_metadata_path"] = str(path.relative_to(root))
            payload["_metadata_abs_path"] = str(path)
            tasks.append(payload)
    return tasks


def is_relative_to(path: Path, parent: Path):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def is_task_branch(branch: str):
    return branch.startswith("refs/heads/codex/task-") or branch.startswith("codex/task-")


def branch_short_name(branch: str):
    return branch.removeprefix("refs/heads/")


def is_nested_agent_worktree(path: Path, root: Path):
    agent_root = default_worktree_root(root).resolve()
    if is_relative_to(path, agent_root):
        rel_parts = path.relative_to(agent_root).parts
        return any(part.endswith("-agent-worktrees") for part in rel_parts[:-1])
    return sum(1 for part in path.parts if part.endswith("-agent-worktrees")) > 1


def metadata_by_worktree(tasks: list[dict]):
    by_path = {}
    for task in tasks:
        value = str(task.get("worktree") or "").strip()
        if value:
            by_path[str(Path(value).expanduser().resolve())] = task
    return by_path


def classify_worktree(root: Path, raw: dict, tasks_by_path: dict[str, dict]):
    path = Path(raw["path"]).resolve()
    branch = raw.get("branch", "")
    status = git_status(path)
    is_primary = path == root
    nested = False if is_primary else is_nested_agent_worktree(path, root)
    task_like = is_task_branch(branch)
    agent_root = default_worktree_root(root).resolve()
    flat_target = agent_root / path.name
    known_task = tasks_by_path.get(str(path))
    target_exists = flat_target.exists() and flat_target != path
    if is_primary:
        classification = "primary"
    elif nested:
        classification = "move-flat"
    elif task_like:
        classification = "keep"
    else:
        classification = "investigate"
    return {
        "path": str(path),
        "branch": branch,
        "head": raw.get("HEAD", ""),
        "classification": classification,
        "nested": nested,
        "task_branch": task_like,
        "metadata_path": known_task.get("_metadata_path") if known_task else None,
        "task_id": known_task.get("task_id") or known_task.get("id") if known_task else None,
        "metadata_status": known_task.get("status") if known_task else None,
        "inside_default_pool": is_relative_to(path, agent_root),
        "dirty": status["dirty"],
        "status_entries": status["entries"],
        "status_error": status["error"],
        "flat_target": str(flat_target) if nested else None,
        "target_exists": target_exists if nested else False,
        "warnings": cleanup_warnings(is_primary, nested, status, target_exists, known_task),
    }


def cleanup_warnings(is_primary: bool, nested: bool, status: dict, target_exists: bool, known_task: dict | None):
    warnings = []
    if is_primary:
        return warnings
    if status.get("dirty"):
        warnings.append("worktree has uncommitted changes; inspect before removing")
    if nested and target_exists:
        warnings.append("flat target already exists; move requires a manual target path")
    if nested and not known_task:
        warnings.append("no primary-checkout task metadata references this worktree")
    if status.get("error"):
        warnings.append(status["error"])
    return warnings


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


def terminal_time(task: dict | None):
    if not task:
        return None
    for key in TERMINAL_TIME_FIELDS:
        parsed = parse_datetime(task.get(key))
        if parsed:
            return parsed
    return None


def terminal_time_value(task: dict | None):
    parsed = terminal_time(task)
    return parsed.isoformat() if parsed else None


def active_tasks(tasks: list[dict]):
    return [task for task in tasks if task.get("status") == "in-progress"]


def task_label(task: dict | None):
    if not task:
        return "unknown"
    return task.get("task_id") or task.get("id") or task.get("run_id") or "unknown"


def receipt_state(root: Path, worktree: Path, task: dict | None, allow_no_receipt: bool):
    receipt = str((task or {}).get("final_receipt") or "").strip()
    if not receipt:
        if allow_no_receipt:
            return {"ok": True, "path": "", "resolved_path": "", "waived": True, "reason": ""}
        return {"ok": False, "path": "", "resolved_path": "", "waived": False, "reason": "terminal task has no linked final receipt"}

    receipt_path = Path(receipt).expanduser()
    candidates = [receipt_path] if receipt_path.is_absolute() else [root / receipt_path, worktree / receipt_path]
    existing = [path.resolve() for path in candidates if path.exists()]
    if not existing:
        if allow_no_receipt:
            return {"ok": True, "path": receipt, "resolved_path": "", "waived": True, "reason": "linked final receipt was not found"}
        return {"ok": False, "path": receipt, "resolved_path": "", "waived": False, "reason": "linked final receipt was not found"}

    for path in existing:
        if not is_relative_to(path, worktree.resolve()):
            return {"ok": True, "path": receipt, "resolved_path": str(path), "waived": False, "reason": ""}

    if allow_no_receipt:
        return {
            "ok": True,
            "path": receipt,
            "resolved_path": str(existing[0]),
            "waived": True,
            "reason": "linked final receipt is inside the removable worktree",
        }
    return {
        "ok": False,
        "path": receipt,
        "resolved_path": str(existing[0]),
        "waived": False,
        "reason": "linked final receipt is inside the removable worktree",
    }


def active_scope_overlap_reasons(task: dict | None, tasks: list[dict]):
    if not task:
        return []
    task_scope = task.get("scope") or []
    reasons = []
    for active in active_tasks(tasks):
        active_id = task_label(active)
        active_scope = active.get("scope") or []
        if not active_scope:
            reasons.append(f"active task {active_id} has unknown scope")
            continue
        for current in task_scope:
            for other in active_scope:
                if paths_overlap(current, other):
                    reasons.append(f"scope {current} overlaps active task {active_id}: {other}")
    return reasons


def closeout_block_reasons(root: Path, item: dict, task: dict | None, tasks: list[dict], allow_no_receipt: bool):
    path = Path(item["path"]).resolve()
    reasons = []
    if item["classification"] == "primary":
        reasons.append("primary checkout is never removed")
    if not item["task_branch"]:
        reasons.append("worktree is not on a codex task branch")
    if item["nested"]:
        reasons.append("nested task worktree must be flattened or inspected first")
    if not item["inside_default_pool"]:
        reasons.append("worktree is outside the default sibling task pool")
    if not task:
        reasons.append("no primary-checkout task metadata references this worktree")
    else:
        if task.get("status") not in TERMINAL_STATUSES:
            reasons.append(f"task status is not terminal: {task.get('status') or 'unknown'}")
        if not task.get("scope"):
            reasons.append("terminal task has unknown scope")
        metadata_branch = branch_short_name(str(task.get("branch") or ""))
        current_branch = branch_short_name(str(item.get("branch") or ""))
        if metadata_branch and current_branch and metadata_branch != current_branch:
            reasons.append(f"metadata branch {metadata_branch} does not match worktree branch {current_branch}")
        receipt = receipt_state(root, path, task, allow_no_receipt)
        if not receipt["ok"]:
            reasons.append(receipt["reason"])
        reasons.extend(active_scope_overlap_reasons(task, tasks))

    status = git_status_short(path)
    if status.get("dirty"):
        reasons.append("worktree has uncommitted changes")
    if status.get("error"):
        reasons.append(status["error"])

    merged, merge_reason = branch_merged_into_primary(root, path)
    if not merged:
        reasons.append(f"task branch is not merged into primary HEAD: {merge_reason}")
    return reasons


def closeout_item(root: Path, item: dict, task: dict | None, receipt: dict | None = None):
    path = Path(item["path"]).resolve()
    task_payload = task or {}
    receipt_payload = receipt if receipt is not None else receipt_state(root, path, task, allow_no_receipt=False)
    return {
        "path": item["path"],
        "branch": branch_short_name(item.get("branch") or ""),
        "head": item.get("head") or "",
        "task_id": task_label(task),
        "run_id": task_payload.get("run_id") or "",
        "metadata_path": item.get("metadata_path"),
        "metadata_status": task_payload.get("status") or item.get("metadata_status") or "unknown",
        "terminal_at": terminal_time_value(task),
        "scope": task_payload.get("scope") or [],
        "final_receipt": task_payload.get("final_receipt") or "",
        "receipt_resolved_path": receipt_payload.get("resolved_path") or "",
        "receipt_waived": bool(receipt_payload.get("waived")),
    }


def closeout_inventory(root: Path, worktrees: list[dict], tasks: list[dict], tasks_by_path: dict[str, dict], args):
    eligible = []
    blocked = []
    for item in worktrees:
        path = str(Path(item["path"]).resolve())
        task = tasks_by_path.get(path)
        receipt = receipt_state(root, Path(item["path"]).resolve(), task, args.allow_no_receipt)
        reasons = closeout_block_reasons(root, item, task, tasks, args.allow_no_receipt)
        payload = closeout_item(root, item, task, receipt)
        if reasons:
            payload["reasons"] = reasons
            blocked.append(payload)
        else:
            eligible.append(payload)

    eligible.sort(
        key=lambda item: parse_datetime(item.get("terminal_at")) or datetime.max.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    candidates = list(eligible)
    retained = []

    if args.older_than_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)
        next_candidates = []
        for item in candidates:
            parsed = parse_datetime(item.get("terminal_at"))
            if parsed and parsed < cutoff:
                next_candidates.append(item)
            else:
                retained_item = dict(item)
                retained_item["reason"] = "within age retention window" if parsed else "missing terminal timestamp for age retention"
                retained.append(retained_item)
        candidates = next_candidates

    if args.keep_count is not None and args.keep_count > 0:
        keep = candidates[: args.keep_count]
        remove = candidates[args.keep_count :]
        for item in keep:
            retained_item = dict(item)
            retained_item["reason"] = f"retained by keep-count {args.keep_count}"
            retained.append(retained_item)
        candidates = remove
    elif args.keep_count is not None and args.keep_count < 0:
        raise SystemExit("--keep-count must be zero or greater")

    return {
        "closeout_enabled": args.closeout,
        "closeout_apply": args.apply and args.closeout,
        "closeout_allow_no_receipt": args.allow_no_receipt,
        "closeout_keep_count": args.keep_count,
        "closeout_older_than_days": args.older_than_days,
        "closeout_eligible_count": len(eligible),
        "closeout_candidate_count": len(candidates),
        "closeout_retained_count": len(retained),
        "closeout_blocked_count": len(blocked),
        "closeout_candidates": candidates,
        "closeout_retained": retained,
        "closeout_blocked": blocked,
    }


def empty_closeout_report():
    return {
        "closeout_enabled": False,
        "closeout_apply": False,
        "closeout_allow_no_receipt": False,
        "closeout_keep_count": None,
        "closeout_older_than_days": None,
        "closeout_eligible_count": 0,
        "closeout_candidate_count": 0,
        "closeout_retained_count": 0,
        "closeout_blocked_count": 0,
        "closeout_candidates": [],
        "closeout_retained": [],
        "closeout_blocked": [],
    }


def build_report(current_root: Path, args=None):
    root = primary_worktree_root(current_root)
    raw_worktrees = git_worktrees(root)
    tasks = task_metadata(root)
    tasks_by_path = metadata_by_worktree(tasks)
    worktrees = [classify_worktree(root, item, tasks_by_path) for item in raw_worktrees]
    move_candidates = [
        item
        for item in worktrees
        if item["classification"] == "move-flat" and not item["target_exists"]
    ]
    closeout = closeout_inventory(root, worktrees, tasks, tasks_by_path, args) if args and args.closeout else empty_closeout_report()
    return {
        "schema_version": 1,
        "invoked_from": str(current_root),
        "primary_checkout": str(root),
        "default_worktree_root": str(default_worktree_root(root).resolve()),
        "task_metadata_count": len(tasks),
        "registered_worktree_count": len(worktrees),
        "move_candidate_count": len(move_candidates),
        "worktrees": worktrees,
        "move_candidates": move_candidates,
        **closeout,
    }


def update_metadata_paths(root: Path, old_path: str, new_path: str):
    changed = []
    for task in task_metadata(root):
        if str(Path(str(task.get("worktree") or "")).expanduser().resolve()) != old_path:
            continue
        metadata_path = Path(task["_metadata_abs_path"])
        task["worktree"] = new_path
        task.pop("_metadata_path", None)
        task.pop("_metadata_abs_path", None)
        write_json(metadata_path, task)
        changed.append(str(metadata_path.relative_to(root)))
    return changed


def move_nested_worktrees(report: dict):
    root = Path(report["primary_checkout"])
    actions = []
    for item in report["move_candidates"]:
        old_path = item["path"]
        new_path = item["flat_target"]
        git_output(["worktree", "move", old_path, new_path], root)
        metadata_updates = update_metadata_paths(root, old_path, new_path)
        actions.append(
            {
                "action": "move",
                "from": old_path,
                "to": new_path,
                "metadata_updates": metadata_updates,
            }
        )
    return actions


def remove_closeout_worktrees(report: dict):
    root = Path(report["primary_checkout"])
    actions = []
    for item in report["closeout_candidates"]:
        path = item["path"]
        git_output(["worktree", "remove", path], root)
        metadata_removed = False
        metadata_path = item.get("metadata_path")
        if metadata_path:
            abs_metadata = root / metadata_path
            if abs_metadata.exists():
                abs_metadata.unlink()
                metadata_removed = True
        actions.append(
            {
                "action": "closeout-remove",
                "path": path,
                "branch": item.get("branch") or "",
                "task_id": item.get("task_id") or "unknown",
                "metadata_path": metadata_path,
                "metadata_removed": metadata_removed,
            }
        )
    return actions


def render_text(report: dict, actions: list[dict]):
    lines = [
        "Agent task cleanup:",
        f" - primary checkout: {report['primary_checkout']}",
        f" - default task pool: {report['default_worktree_root']}",
        f" - invoked from: {report['invoked_from']}",
        f" - registered worktrees: {report['registered_worktree_count']}",
        f" - task metadata records: {report['task_metadata_count']}",
        f" - nested move candidates: {report['move_candidate_count']}",
    ]
    if actions:
        lines.append("")
        lines.append("Applied actions:")
        for action in actions:
            if action["action"] == "move":
                lines.append(f" - moved {action['from']} -> {action['to']}")
                for metadata in action["metadata_updates"]:
                    lines.append(f"   updated metadata: {metadata}")
            elif action["action"] == "closeout-remove":
                lines.append(f" - removed {action['path']} ({action['task_id']})")
                if action.get("metadata_removed"):
                    lines.append(f"   removed metadata: {action['metadata_path']}")
    lines.append("")
    lines.append("Worktrees:")
    for item in report["worktrees"]:
        marker = "*" if item["classification"] == "move-flat" else "-"
        dirty = "dirty" if item["dirty"] else "clean"
        lines.append(f" {marker} {item['classification']}: {item['path']} ({dirty})")
        if item.get("branch"):
            lines.append(f"   branch: {item['branch']}")
        if item.get("flat_target"):
            lines.append(f"   flat target: {item['flat_target']}")
        for warning in item["warnings"]:
            lines.append(f"   warning: {warning}")
    if report["move_candidate_count"]:
        lines.append("")
        lines.append("To move nested worktrees into the flat pool:")
        lines.append("  make agent-task-cleanup TASK_CLEANUP_MOVE_NESTED=1 TASK_CLEANUP_APPLY=1")
    if report.get("closeout_enabled"):
        lines.append("")
        lines.append("Closeout preview:")
        lines.append(f" - eligible after safety checks: {report['closeout_eligible_count']}")
        lines.append(f" - removal candidates after retention: {report['closeout_candidate_count']}")
        lines.append(f" - retained by policy: {report['closeout_retained_count']}")
        lines.append(f" - blocked/investigate: {report['closeout_blocked_count']}")
        for item in report["closeout_candidates"]:
            lines.append(f" * remove: {item['path']} ({item['task_id']}, {item['metadata_status']})")
            if item.get("final_receipt"):
                lines.append(f"   receipt: {item['final_receipt']}")
        for item in report["closeout_retained"]:
            lines.append(f" - retain: {item['path']} ({item['task_id']})")
            lines.append(f"   reason: {item['reason']}")
        for item in report["closeout_blocked"]:
            lines.append(f" - block: {item['path']} ({item['task_id']})")
            for reason in item["reasons"]:
                lines.append(f"   reason: {reason}")
        if report["closeout_candidate_count"]:
            lines.append("")
            lines.append("To remove eligible finished worktrees:")
            lines.append("  make agent-task-closeout TASK_CLOSEOUT_APPLY=1")
    else:
        lines.append("")
        lines.append("For finished clean task worktree closeout:")
        lines.append("  make agent-task-closeout")
    lines.append("")
    lines.append("Closeout uses `git worktree remove` without force and keeps blocked items for manual inspection.")
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect and clean up local agent task worktrees")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--apply", action="store_true", help="apply requested cleanup actions")
    parser.add_argument("--move-nested", action="store_true", help="move nested task worktrees into the primary flat pool")
    parser.add_argument("--closeout", action="store_true", help="preview or remove eligible finished task worktrees")
    parser.add_argument("--prune", action="store_true", help="run git worktree prune after applied cleanup")
    parser.add_argument("--keep-count", type=int, default=None, help="retain the newest N eligible finished worktrees")
    parser.add_argument("--older-than-days", type=int, default=None, help="only close out eligible worktrees older than N days")
    parser.add_argument("--allow-no-receipt", action="store_true", help="allow closeout without durable final receipt evidence")
    return parser.parse_args()


def main():
    args = parse_args()
    current_root = current_repo_root()
    report = build_report(current_root, args)
    actions = []
    if args.apply and args.move_nested:
        actions.extend(move_nested_worktrees(report))
    if args.apply and args.closeout:
        actions.extend(remove_closeout_worktrees(report))
    if args.apply and (args.move_nested or args.closeout):
        if args.prune:
            git_output(["worktree", "prune"], Path(report["primary_checkout"]))
        report = build_report(current_root, args)
    elif args.apply:
        raise SystemExit("No cleanup action selected. Use --move-nested or --closeout with --apply, or run without --apply for audit.")

    if args.json:
        payload = dict(report)
        payload["applied_actions"] = actions
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(report, actions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
