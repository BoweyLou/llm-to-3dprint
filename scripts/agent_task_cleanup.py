#!/usr/bin/env python3

import argparse
import json
import subprocess
from pathlib import Path

# Script flow:
# 1. Resolve the primary checkout, even when invoked from a linked worktree.
# 2. Inspect registered git worktrees and local task metadata.
# 3. Classify task worktrees, especially nested task-worktree pools.
# 4. Optionally move nested worktrees into the primary checkout's flat pool.
#
# Function guide:
# - git_output/repo_roots/default_worktree_root collect repo topology.
# - parse_worktrees/git_status/task_metadata build the inventory.
# - classify_worktree/build_report identify cleanup candidates.
# - move_nested_worktrees/render_text/main apply or report cleanup actions.


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
        "metadata_status": known_task.get("status") if known_task else None,
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


def build_report(current_root: Path):
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
            lines.append(f" - moved {action['from']} -> {action['to']}")
            for metadata in action["metadata_updates"]:
                lines.append(f"   updated metadata: {metadata}")
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
    lines.append("")
    lines.append("For removals, inspect each clean finished worktree, then use `git worktree remove <path>` explicitly.")
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect and clean up local agent task worktrees")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--apply", action="store_true", help="apply requested cleanup actions")
    parser.add_argument("--move-nested", action="store_true", help="move nested task worktrees into the primary flat pool")
    parser.add_argument("--prune", action="store_true", help="run git worktree prune after applied cleanup")
    return parser.parse_args()


def main():
    args = parse_args()
    current_root = current_repo_root()
    report = build_report(current_root)
    actions = []
    if args.apply and args.move_nested:
        actions = move_nested_worktrees(report)
        if args.prune:
            git_output(["worktree", "prune"], Path(report["primary_checkout"]))
        report = build_report(current_root)
    elif args.apply:
        raise SystemExit("No cleanup action selected. Use --move-nested with --apply, or run without --apply for audit.")

    if args.json:
        payload = dict(report)
        payload["applied_actions"] = actions
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(report, actions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
