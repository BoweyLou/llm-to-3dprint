#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
from pathlib import Path

from _agent_scope import parse_scope, paths_overlap

# Script flow:
# 1. Validate the requested task, clean checkout state, and declared scope.
# 2. Check local in-flight task metadata for overlapping write scopes.
# 3. Create a task branch and sibling worktree for the write-capable worker.
# 4. Write task packet, receipt template, and in-flight metadata artifacts.
#
# Function guide:
# - git_output/repo_root/git_status collect target repo facts.
# - safe_slug/parse_scope/paths_overlap normalize task ids and scope checks.
# - active_tasks/overlap_warnings read local in-flight metadata.
# - build_task_packet/build_receipt_template/build_metadata create local JSON artifacts.
# - ensure_clean_main/create_worktree/write_json/main orchestrate the command.

VALID_MODES = {
    "bootstrap",
    "drift",
    "pull-request",
    "release-gate",
    "learning-comments",
    "test-first",
    "verification",
}


def git_output(args, cwd: Path):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def repo_root():
    try:
        return Path(git_output(["rev-parse", "--show-toplevel"], Path.cwd())).resolve()
    except SystemExit as exc:
        raise SystemExit(f"agent-task-prepare must run inside a git repository: {exc}") from exc


def git_common_dir(root: Path):
    common = Path(git_output(["rev-parse", "--git-common-dir"], root))
    if not common.is_absolute():
        common = root / common
    return common.resolve()


def primary_worktree_root(root: Path):
    common = git_common_dir(root)
    if common.name == ".git":
        return common.parent.resolve()
    return root


def ensure_primary_checkout(root: Path):
    primary = primary_worktree_root(root)
    if root == primary:
        return
    raise SystemExit(
        "agent-task-prepare must run from the primary checkout, not from an existing task worktree.\n"
        f"Current worktree: {root}\n"
        f"Primary checkout: {primary}\n"
        "Run the prepare command again from the primary checkout so task worktrees stay in one flat pool."
    )


def git_status(root: Path):
    return git_output(["status", "--short"], root)


def safe_slug(value: str):
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-._")
    return slug or "task"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def tasks_dir(root: Path):
    return root / ".agent-workflows" / "tasks"


def ensure_task_gitignore(root: Path):
    path = tasks_dir(root) / ".gitignore"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("*\n!.gitignore\n", encoding="utf-8")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def active_tasks(root: Path):
    directory = tasks_dir(root)
    if not directory.exists():
        return []
    tasks = []
    for path in sorted(directory.glob("*.json")):
        payload = read_json(path)
        if isinstance(payload, dict) and payload.get("status") == "in-progress":
            tasks.append(payload)
    return tasks


def overlap_warnings(scope: list[str], existing_tasks: list[dict]):
    warnings = []
    if not scope:
        warnings.append("Task scope is unknown; overlap checks cannot protect the repo.")
    for task in existing_tasks:
        other_scope = task.get("scope") or []
        task_id = task.get("task_id") or task.get("id") or "unknown"
        if not other_scope:
            warnings.append(f"Existing task {task_id} has unknown scope.")
            continue
        for current in scope:
            for other in other_scope:
                if paths_overlap(current, other):
                    warnings.append(f"Task scope {current} overlaps in-flight task {task_id}: {other}")
    return warnings


def ensure_clean_main(root: Path, allow_dirty: bool):
    status = git_status(root)
    if status and not allow_dirty:
        raise SystemExit(
            "Main checkout must be clean before preparing a write-capable task worktree.\n"
            "Commit, stash, or move unrelated work first, or rerun with --allow-dirty."
        )
    return status


def default_worktree_root(root: Path):
    return root.parent / f"{root.name}-agent-worktrees"


def allocate_paths(root: Path, args, task_slug: str):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    branch = f"codex/task-{task_slug}-{timestamp}"
    worktree_parent = Path(args.worktree_root).expanduser() if args.worktree_root else default_worktree_root(root)
    worktree_path = (worktree_parent / f"{task_slug}-{timestamp}").resolve()
    return branch, worktree_path


def create_worktree(root: Path, branch: str, worktree_path: Path, base_ref: str):
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    git_output(["worktree", "add", "-b", branch, str(worktree_path), base_ref], root)


def build_task_packet(args, root: Path, worktree_path: Path, task_slug: str, scope: list[str], created_at: str):
    title = args.title.strip() if args.title.strip() else f"Implement {args.task}"
    return {
        "schema_version": 1,
        "task": {
            "id": args.task,
            "title": title,
            "priority": args.priority,
            "status": "approved",
            "source": {
                "type": args.source_type,
                "reference": args.task,
            },
        },
        "context": {
            "repo_root": str(worktree_path),
            "mode": args.mode,
            "problem_statement": title,
            "background": [
                f"Prepared from {root}",
                f"Created at {created_at}",
            ],
            "non_goals": [
                "Do not edit files outside the approved task scope.",
                "Do not stage, commit, push, or merge without human approval.",
            ],
        },
        "scope": {
            "allowed_files": scope,
            "protected_files": [".git", ".env", ".secrets"],
            "inspect_first": ["AGENTS.md", "REVIEW.md", "docs/ops/agent-workflow.md"],
            "expected_outputs": [
                f".agent-workflows/tasks/{task_slug}/receipt.template.json",
                f".agent-workflows/tasks/{task_slug}/task-packet.json",
            ],
        },
        "acceptance_criteria": [
            {
                "description": "The worker changes only the approved task scope.",
                "verification": "Review git diff and git status in the task worktree.",
            },
            {
                "description": "The worker records validation evidence in the receipt.",
                "verification": f"Update .agent-workflows/tasks/{task_slug}/receipt.template.json or copy it to receipt.json.",
            },
        ],
        "validation": {
            "commands": [
                {"command": "git status --short", "required": True, "expected_result": "Only task-scope files are changed."},
                {"command": "make agent-verify", "required": False, "skip_policy": "Record why this target is unavailable or out of scope."},
            ],
            "evidence_to_capture": ["git diff --stat", "validation command output", "docs impact decision"],
        },
        "docs_impact": {
            "expected": "unknown",
            "paths": [],
            "waiver_allowed": True,
            "notes": "Decide during implementation and record the result in the receipt.",
        },
        "risk": {
            "level": "medium",
            "known_risks": ["parallel task overlap", "unrelated local changes", "missing validation evidence"],
            "stop_conditions": [
                "The task needs files outside allowed_files.",
                "The worktree contains unrelated changes.",
                "Validation cannot run and no skip reason is available.",
            ],
        },
        "approval": {
            "human_approval_required": True,
            "state": "approved",
            "approver": None,
            "notes": "Approval covers preparing the isolated worktree; commit, push, merge, and PR mutation still require human approval.",
        },
        "handoff": {
            "recommended_prompt": "fix-implementer.md",
            "owner": None,
            "dependencies": [],
            "next_packet_hint": None,
        },
    }


def build_receipt_template(args, root: Path, worktree_path: Path, branch: str, scope: list[str], created_at: str):
    return {
        "schema_version": 1,
        "run": {
            "id": f"task-{safe_slug(args.task)}",
            "started_at": created_at,
            "completed_at": None,
            "mode": args.mode,
            "status": "not-run",
        },
        "tooling": {
            "agent_tool": "manual",
            "agent_tool_version": None,
            "local_only": True,
            "network_used": False,
            "notes": "Prepared by make agent-task-prepare for a write-worker task.",
        },
        "scope": {
            "repo_root": str(worktree_path),
            "base_ref": args.base_ref,
            "changed_files": [],
            "allowed_files": scope,
            "protected_files": [".git", ".env", ".secrets"],
        },
        "review_risk": {
            "risk_tier": "medium",
            "trust_profile": "write-worker",
            "triggers": [{"rule_id": "write-capable-task", "reason": f"Prepared branch {branch}"}],
            "network_or_tool_allowlist_checked": False,
            "mutation_boundary_checked": True,
            "data_boundary_checked": False,
            "approved_deviations": [],
        },
        "evidence": {
            "files_inspected": [],
            "commands": [{"command": "git status --short", "result": "not-run", "exit_code": None, "notes": "Run inside the task worktree."}],
            "docs_impact": {"checked": False, "result": "not-run", "categories": [], "waiver_reason": None},
            "tests": {
                "result": "not-run",
                "failing_test_evidence": None,
                "passing_test_evidence": None,
                "generated_test_provenance": None,
                "skip_reason": None,
            },
        },
        "findings": [],
        "disposition": {
            "summary": f"Prepared isolated worktree for {args.task}.",
            "next_actions": [
                "Implement only the approved task scope.",
                "Record validation output and docs impact before closing the task.",
                "Ask before staging, committing, pushing, or mutating pull requests.",
            ],
            "human_approval_required": True,
        },
    }


def build_metadata(args, root: Path, worktree_path: Path, branch: str, scope: list[str], created_at: str, warnings: list[str]):
    return {
        "schema_version": 1,
        "task_id": args.task,
        "title": args.title.strip() or f"Implement {args.task}",
        "status": "in-progress",
        "created_at": created_at,
        "source_repo": str(root),
        "base_ref": args.base_ref,
        "branch": branch,
        "worktree": str(worktree_path),
        "scope": scope,
        "overlap_warnings": warnings,
        "task_packet": f".agent-workflows/tasks/{safe_slug(args.task)}/task-packet.json",
        "receipt_template": f".agent-workflows/tasks/{safe_slug(args.task)}/receipt.template.json",
    }


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare an isolated worktree for one write-capable agent task")
    parser.add_argument("--task", required=True, help="Task id, issue id, or backlog row id")
    parser.add_argument("--title", default="", help="Human-readable task title")
    parser.add_argument("--scope", default="", help="Comma-separated files or directories the task may edit")
    parser.add_argument("--priority", default="P1", choices=["P0", "P1", "P2", "P3"])
    parser.add_argument("--source-type", default="backlog", choices=["backlog", "issue", "review-finding", "decision", "human-request"])
    parser.add_argument("--mode", default="test-first", choices=sorted(VALID_MODES))
    parser.add_argument("--base-ref", default="HEAD", help="Git ref to branch the task worktree from")
    parser.add_argument("--worktree-root", default="", help="Directory that should contain task worktrees")
    parser.add_argument("--overlap-policy", default="warn", choices=["warn", "block", "ignore"])
    parser.add_argument("--allow-dirty", action="store_true", help="Allow preparing from a dirty main checkout")
    return parser.parse_args()


def main():
    args = parse_args()
    root = repo_root()
    ensure_primary_checkout(root)
    task_slug = safe_slug(args.task)
    scope = parse_scope(args.scope)
    created_at = now_iso()

    ensure_task_gitignore(root)
    main_status = ensure_clean_main(root, args.allow_dirty)
    warnings = overlap_warnings(scope, active_tasks(root))
    blocking = warnings and args.overlap_policy == "block"
    if blocking:
        raise SystemExit("Task scope overlaps an in-flight task:\n" + "\n".join(f"- {warning}" for warning in warnings))

    branch, worktree_path = allocate_paths(root, args, task_slug)
    create_worktree(root, branch, worktree_path, args.base_ref)

    artifact_dir = worktree_path / ".agent-workflows" / "tasks" / task_slug
    task_packet_path = artifact_dir / "task-packet.json"
    receipt_path = artifact_dir / "receipt.template.json"
    metadata_path = tasks_dir(root) / f"{task_slug}.json"

    write_json(task_packet_path, build_task_packet(args, root, worktree_path, task_slug, scope, created_at))
    write_json(receipt_path, build_receipt_template(args, root, worktree_path, branch, scope, created_at))
    write_json(metadata_path, build_metadata(args, root, worktree_path, branch, scope, created_at, warnings))

    print("Agent task worktree prepared:")
    print(f" - task: {args.task}")
    print(f" - branch: {branch}")
    print(f" - worktree: {worktree_path}")
    print(f" - task packet: {task_packet_path.relative_to(worktree_path)}")
    print(f" - receipt template: {receipt_path.relative_to(worktree_path)}")
    print(f" - metadata: {metadata_path.relative_to(root)}")
    if main_status and args.allow_dirty:
        print(" - warning: main checkout was dirty when the task was prepared")
    for warning in warnings:
        print(f" - warning: {warning}")
    print("\nNext steps:")
    print(f"  cd {worktree_path}")
    print(f"  read {task_packet_path.relative_to(worktree_path)}")
    print("  run validation commands and update the receipt before handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
