#!/usr/bin/env python3

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import goal_check
from _agent_scope import normalize_scope_path, paths_overlap
from verify_agent_receipt import validate_receipt

IGNORED_LOCAL_ARTIFACT_PREFIXES = (
    ".agent-workflows/tasks/",
    ".agent-workflows/runs/",
    ".doc-contract-kit/updates/",
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


def git_common_dir(root: Path):
    stdout, _, _ = git_output(["rev-parse", "--git-common-dir"], root)
    common = Path(stdout)
    if not common.is_absolute():
        common = root / common
    return common.resolve()


def primary_checkout(root: Path):
    common = git_common_dir(root)
    if common.name == ".git":
        return common.parent.resolve()
    return root


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"JSON file not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def maybe_read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def safe_slug(value: str):
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "task"


def tasks_dir(root: Path):
    return root / ".agent-workflows" / "tasks"


def metadata_candidates(primary: Path):
    directory = tasks_dir(primary)
    if not directory.exists():
        return []
    items = []
    for path in sorted(directory.glob("*.json")):
        payload = maybe_read_json(path)
        if isinstance(payload, dict):
            payload["_metadata_path"] = path
            items.append(payload)
    return items


def current_branch(root: Path):
    stdout, _, code = git_output(["branch", "--show-current"], root, check=False)
    return stdout if code == 0 else ""


def git_status_entries(root: Path):
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or "Unable to inspect primary checkout status.")
    entries = []
    for raw_line in result.stdout.splitlines():
        if not raw_line:
            continue
        code_value = raw_line[:2]
        path = raw_line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        entries.append({"code": code_value, "path": path})
    return entries


def git_bytes(args, cwd: Path):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.decode("utf-8", "replace").strip() or result.stdout.decode("utf-8", "replace").strip())
    return result.stdout


def dirty_counts(entries: list[dict]):
    tracked = []
    untracked = []
    staged = []
    unstaged = []
    for entry in entries:
        code = entry["code"]
        path = entry["path"]
        if code == "??":
            untracked.append(path)
            continue
        tracked.append(path)
        if code[0] != " ":
            staged.append(path)
        if len(code) > 1 and code[1] != " ":
            unstaged.append(path)
    return {
        "total": len(entries),
        "tracked": len(set(tracked)),
        "untracked": len(set(untracked)),
        "staged": len(set(staged)),
        "unstaged": len(set(unstaged)),
    }


def untracked_content_hashes(root: Path, entries: list[dict]):
    hashes = []
    for entry in sorted(entries, key=lambda item: item["path"]):
        if entry["code"] != "??":
            continue
        path = root / entry["path"]
        if path.is_file() or path.is_symlink():
            try:
                hashes.append({"path": entry["path"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            except OSError:
                hashes.append({"path": entry["path"], "sha256": None, "error": "unreadable"})
    return hashes


def checkout_status_snapshot(root: Path):
    status_entries = sorted(git_status_entries(root), key=lambda item: (item["path"], item["code"]))
    head, _, _ = git_output(["rev-parse", "HEAD"], root)
    branch, _, _ = git_output(["rev-parse", "--abbrev-ref", "HEAD"], root)
    staged_diff = git_bytes(["diff", "--binary", "--cached"], root)
    unstaged_diff = git_bytes(["diff", "--binary"], root)
    untracked_hashes = untracked_content_hashes(root, status_entries)

    digest = hashlib.sha256()
    digest.update(head.encode("utf-8", "surrogateescape"))
    digest.update(b"\0")
    for entry in status_entries:
        digest.update(f"{entry['code']}\0{entry['path']}\0".encode("utf-8", "surrogateescape"))
    digest.update(hashlib.sha256(staged_diff).hexdigest().encode("ascii"))
    digest.update(b"\0")
    digest.update(hashlib.sha256(unstaged_diff).hexdigest().encode("ascii"))
    digest.update(b"\0")
    for item in untracked_hashes:
        digest.update(f"{item['path']}\0{item.get('sha256')}\0".encode("utf-8", "surrogateescape"))

    return {
        "schema_version": 1,
        "mode": "dirty-primary-baseline",
        "root": str(root),
        "head": head,
        "branch": branch,
        "dirty": bool(status_entries),
        "counts": dirty_counts(status_entries),
        "changed_files": sorted({entry["path"] for entry in status_entries}),
        "status_entries": status_entries,
        "staged_diff_sha256": hashlib.sha256(staged_diff).hexdigest(),
        "unstaged_diff_sha256": hashlib.sha256(unstaged_diff).hexdigest(),
        "untracked_content": untracked_hashes,
        "state_sha256": digest.hexdigest(),
    }


def compare_primary_baseline(current: dict, baseline: dict):
    current_entries = {f"{entry['code']}\0{entry['path']}" for entry in current.get("status_entries", [])}
    baseline_entries = {f"{entry['code']}\0{entry['path']}" for entry in baseline.get("status_entries", [])}
    current_paths = set(current.get("changed_files", []))
    baseline_paths = set(baseline.get("changed_files", []))
    state_match = current.get("state_sha256") == baseline.get("state_sha256")
    return {
        "state_sha256_match": state_match,
        "head_match": current.get("head") == baseline.get("head"),
        "changed_since_baseline": not state_match,
        "new_changed_files": sorted(current_paths - baseline_paths),
        "removed_changed_files": sorted(baseline_paths - current_paths),
        "new_status_entries": sorted(current_entries - baseline_entries),
        "removed_status_entries": sorted(baseline_entries - current_entries),
    }


def baseline_summary(snapshot: dict):
    return {
        "root": snapshot.get("root"),
        "captured_at": snapshot.get("captured_at"),
        "head": snapshot.get("head"),
        "branch": snapshot.get("branch"),
        "dirty": snapshot.get("dirty"),
        "counts": snapshot.get("counts"),
        "changed_files": snapshot.get("changed_files", []),
        "state_sha256": snapshot.get("state_sha256"),
    }


def primary_baseline_guard(metadata: dict, primary: Path):
    baseline = metadata.get("primary_checkout_baseline")
    if not baseline:
        return None, []
    if not isinstance(baseline, dict):
        return {"baseline": None, "current": None, "comparison": None}, ["Task metadata primary checkout baseline is invalid."]
    blockers = []
    baseline_root = str(baseline.get("root") or "").strip()
    try:
        root_matches = bool(baseline_root) and Path(baseline_root).expanduser().resolve() == primary
    except OSError:
        root_matches = False
    current = checkout_status_snapshot(primary)
    comparison = compare_primary_baseline(current, baseline)
    if not root_matches:
        blockers.append("Primary checkout baseline root does not match the current primary checkout.")
    if comparison["changed_since_baseline"]:
        blockers.append("Primary checkout changed since dirty baseline; inspect the primary checkout before handoff or finalize.")
    return {
        "baseline": baseline_summary(baseline),
        "current": baseline_summary(current),
        "comparison": comparison,
    }, blockers


def detect_metadata(primary: Path, current_root: Path, explicit_task: str):
    if explicit_task:
        path = tasks_dir(primary) / f"{safe_slug(explicit_task)}.json"
        payload = read_json(path)
        payload["_metadata_path"] = path
        return payload

    candidates = metadata_candidates(primary)
    worktree_matches = []
    branch_matches = []
    branch = current_branch(current_root)
    for item in candidates:
        recorded_worktree = str(item.get("worktree") or "").strip()
        if recorded_worktree:
            try:
                if Path(recorded_worktree).expanduser().resolve() == current_root:
                    worktree_matches.append(item)
                    continue
            except OSError:
                pass
        if branch and item.get("branch") == branch:
            branch_matches.append(item)
    if len(worktree_matches) == 1:
        return worktree_matches[0]
    if len(worktree_matches) > 1:
        raise SystemExit("Multiple task metadata entries match this worktree. Pass --task explicitly.")
    if len(branch_matches) == 1:
        return branch_matches[0]
    if len(branch_matches) > 1:
        raise SystemExit("Multiple task metadata entries match this branch. Pass --task explicitly.")
    raise SystemExit("No task metadata matches this worktree. Pass --task explicitly or run from a prepared task worktree.")


def ref_exists(root: Path, ref: str):
    _, _, code = git_output(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], root, check=False)
    return code == 0


def default_base_ref(root: Path):
    stdout, _, code = git_output(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], root, check=False)
    if code == 0 and stdout and ref_exists(root, stdout):
        return stdout
    for candidate in ("origin/main", "origin/master", "main", "master"):
        if ref_exists(root, candidate):
            return candidate
    return None


def resolve_base_ref(root: Path, metadata: dict, explicit: str):
    for candidate in (explicit, metadata.get("base_ref"), default_base_ref(root)):
        value = str(candidate or "").strip()
        if value and value != "HEAD" and ref_exists(root, value):
            return value
    return None


def changed_files(root: Path, base_ref: str | None):
    files = set()
    if base_ref:
        stdout, _, code = git_output(["diff", "--name-only", f"{base_ref}...HEAD"], root, check=False)
        if code == 0:
            files.update(line.strip() for line in stdout.splitlines() if line.strip())
    for args in (
        ["diff", "--name-only", "--cached"],
        ["diff", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        stdout, _, _ = git_output(args, root, check=False)
        files.update(line.strip() for line in stdout.splitlines() if line.strip())
    normalized = []
    for path in files:
        value = normalize_scope_path(path)
        if not value:
            continue
        if any(value.startswith(prefix) for prefix in IGNORED_LOCAL_ARTIFACT_PREFIXES):
            continue
        normalized.append(value)
    return sorted(set(normalized))


def scope_drift(changed: list[str], scope: list[str]):
    if not scope:
        return changed
    return [path for path in changed if not any(paths_overlap(path, allowed) for allowed in scope)]


def resolve_receipt_path(path_value: str, current_root: Path, primary: Path):
    value = str(path_value or "").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    for base in (current_root, primary):
        candidate = (base / path).resolve()
        if candidate.exists():
            return candidate
    return (current_root / path).resolve()


def receipt_candidates(metadata: dict, current_root: Path, primary: Path, explicit_receipt: str):
    slug = safe_slug(metadata.get("task_id") or metadata.get("id") or "task")
    values = []
    if explicit_receipt:
        values.append(explicit_receipt)
    if metadata.get("final_receipt"):
        values.append(metadata["final_receipt"])
    values.extend(
        [
            f".agent-workflows/tasks/{slug}/receipt.json",
            f".agent-workflows/tasks/{slug}/receipt.template.json",
        ]
    )
    resolved = []
    seen = set()
    for value in values:
        path = resolve_receipt_path(value, current_root, primary)
        if not path:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(path)
    return resolved


def validate_receipt_file(path: Path):
    try:
        payload = read_json(path)
    except SystemExit as exc:
        return None, [str(exc)]
    errors = validate_receipt(payload, strict=True)
    return payload, errors


def branch_freshness(root: Path, base_ref: str | None):
    if not base_ref:
        return {"checked": False, "base_ref": None, "fresh": False, "message": "No usable base ref found for freshness check."}
    _, stderr, code = git_output(["merge-base", "--is-ancestor", base_ref, "HEAD"], root, check=False)
    if code == 0:
        return {"checked": True, "base_ref": base_ref, "fresh": True, "message": f"HEAD contains {base_ref}."}
    if code == 1:
        return {"checked": True, "base_ref": base_ref, "fresh": False, "message": f"HEAD does not contain the latest {base_ref}."}
    return {"checked": True, "base_ref": base_ref, "fresh": False, "message": stderr or "merge-base check failed"}


def active_overlap(metadata: dict, primary: Path, changed: list[str]):
    current_task = metadata.get("task_id") or metadata.get("id") or "unknown"
    current_scope = metadata.get("scope") or []
    overlaps = []
    unknown_scope_tasks = []
    for item in metadata_candidates(primary):
        task_id = item.get("task_id") or item.get("id") or "unknown"
        if task_id == current_task or item.get("status") != "in-progress":
            continue
        other_scope = item.get("scope") or []
        if not other_scope:
            unknown_scope_tasks.append(task_id)
            continue
        for path in changed or current_scope:
            for other in other_scope:
                if paths_overlap(path, other):
                    overlaps.append(
                        {
                            "task_id": task_id,
                            "current_path": path,
                            "other_scope": other,
                            "message": f"{path} overlaps in-flight task {task_id}: {other}",
                        }
                    )
    return overlaps, unknown_scope_tasks


def build_report(args, current_root: Path):
    primary = primary_checkout(current_root)
    metadata = detect_metadata(primary, current_root, args.task)
    primary_baseline, primary_baseline_blockers = primary_baseline_guard(metadata, primary)
    base_ref = resolve_base_ref(current_root, metadata, args.base_ref)
    changed = changed_files(current_root, base_ref)
    declared_scope = metadata.get("scope") or []
    drift = scope_drift(changed, declared_scope)
    freshness = branch_freshness(current_root, base_ref)
    overlaps, unknown_scope_tasks = active_overlap(metadata, primary, changed)
    goal_report = goal_check.build_goal_check_report(current_root, changed)
    goal_summary = goal_check.compact_goal_summary(goal_report)

    receipt_path = None
    receipt_payload = None
    receipt_errors = ["No receipt file found for this task worktree."]
    for candidate in receipt_candidates(metadata, current_root, primary, args.receipt):
        if not candidate.exists():
            continue
        receipt_payload, receipt_errors = validate_receipt_file(candidate)
        receipt_path = candidate
        break

    blockers = []
    warnings = []
    if not declared_scope:
        blockers.append("Task metadata has no declared scope.")
    blockers.extend(primary_baseline_blockers)
    if drift:
        blockers.append("Changed files fall outside the declared task scope.")
    if not freshness["fresh"]:
        blockers.append(freshness["message"])
    if unknown_scope_tasks:
        blockers.append("Another in-progress task has unknown scope, so overlap safety cannot be proven.")
    if overlaps:
        blockers.extend(item["message"] for item in overlaps)
    if receipt_errors:
        blockers.append("Receipt validation failed.")
    if goal_summary["summary"].get("conflict"):
        blockers.append("Goal-check found changed paths marked as conflict with the repo goal.")
    if metadata.get("status") not in {"in-progress", "done"}:
        blockers.append(f"Task status {metadata.get('status')!r} is not handoff-ready.")
    if not changed:
        warnings.append("No branch or working-tree changes were detected relative to the resolved base ref.")
    if not goal_summary["config"].get("exists"):
        warnings.append("Area-contract config is missing; goal-check paths are unknown.")
    if goal_summary["summary"].get("unknown"):
        warnings.append("Goal-check found changed paths with no matching area contract.")
    if not metadata.get("final_receipt") and receipt_path and receipt_path.name != "receipt.template.json":
        warnings.append("Receipt is present but not yet linked in task metadata; run make agent-task-finish TASK=<id> TASK_RECEIPT=<path> before closeout.")

    docs_impact = {}
    if isinstance(receipt_payload, dict):
        docs_impact = (
            receipt_payload.get("evidence", {}).get("docs_impact", {})
            if isinstance(receipt_payload.get("evidence"), dict)
            else {}
        )

    return {
        "schema_version": 1,
        "repo_root": str(current_root),
        "primary_checkout": str(primary),
        "task_id": metadata.get("task_id") or metadata.get("id") or "unknown",
        "task_status": metadata.get("status"),
        "metadata_path": str(Path(metadata["_metadata_path"]).relative_to(primary)),
        "branch": current_branch(current_root),
        "base_ref": base_ref,
        "ready": not blockers,
        "changed_files": changed,
        "goal_check": goal_summary,
        "declared_scope": declared_scope,
        "scope_drift_files": drift,
        "branch_freshness": freshness,
        "active_overlap": overlaps,
        "unknown_scope_tasks": unknown_scope_tasks,
        "receipt_validation": {
            "path": str(receipt_path) if receipt_path else None,
            "passed": not receipt_errors,
            "errors": receipt_errors,
            "docs_impact": docs_impact,
        },
        "primary_checkout_baseline": primary_baseline,
        "blockers": blockers,
        "warnings": warnings,
    }


def render_text(report: dict):
    lines = [
        "Agent task readiness:",
        f" - task: {report['task_id']}",
        f" - status: {'ready' if report['ready'] else 'not-ready'}",
        f" - task metadata: {report['metadata_path']}",
        f" - branch: {report['branch'] or '(detached)'}",
        f" - base ref: {report['base_ref'] or '(unknown)'}",
        f" - changed files: {len(report['changed_files'])}",
    ]
    if report["declared_scope"]:
        lines.append(f" - declared scope: {', '.join(report['declared_scope'])}")
    else:
        lines.append(" - declared scope: (unknown)")
    lines.append(f" - receipt: {report['receipt_validation']['path'] or '(missing)'}")
    if report["branch_freshness"]["checked"]:
        lines.append(f" - freshness: {'fresh' if report['branch_freshness']['fresh'] else 'stale'}")
    else:
        lines.append(" - freshness: not checked")
    if report.get("primary_checkout_baseline"):
        comparison = report["primary_checkout_baseline"]["comparison"]
        lines.append(
            " - primary dirty baseline: "
            f"{'changed' if comparison.get('changed_since_baseline') else 'unchanged'}"
        )
    goal_summary = report.get("goal_check", {}).get("summary", {})
    if goal_summary:
        lines.append(
            " - goal check: "
            f"{report['goal_check'].get('result')} "
            f"(aligned {goal_summary.get('aligned', 0)}, extends {goal_summary.get('extends', 0)}, "
            f"conflict {goal_summary.get('conflict', 0)}, unknown {goal_summary.get('unknown', 0)})"
        )
    if report["scope_drift_files"]:
        lines.append(f" - scope drift: {', '.join(report['scope_drift_files'])}")
    if report["blockers"]:
        lines.append(" - blockers:")
        for item in report["blockers"]:
            lines.append(f"   - {item}")
    if report["warnings"]:
        lines.append(" - warnings:")
        for item in report["warnings"]:
            lines.append(f"   - {item}")
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Check whether a task worktree is ready for PR update or merge handoff")
    parser.add_argument("--task", default="", help="Task id when not running from the task worktree")
    parser.add_argument("--base-ref", default="", help="Base ref to compare branch freshness and changed files against")
    parser.add_argument("--receipt", default="", help="Receipt file to validate instead of metadata/default task paths")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    report = build_report(args, repo_root())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
