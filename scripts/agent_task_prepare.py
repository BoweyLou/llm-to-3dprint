#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import goal_check
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
# - acquire_launch_lock prevents two launchers from claiming the same task pool at once.
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
    confidence = ("metadata" if source == "unknown" else source) if any(payload.get(field) for field in identity_fields) else "unknown"
    payload["confidence"] = confidence
    payload["source"] = confidence
    return payload


def args_attribution(args, *, run_id: str | None = None, metadata_path: str | None = None, source: str = "metadata"):
    return attribution_object(
        owner=args.owner,
        owner_label=args.owner_label,
        session_id=args.session_id,
        thread_id=args.thread_id,
        automation_id=args.automation_id,
        run_id=run_id,
        metadata_path=metadata_path,
        source=source,
    )


def task_attribution(task: dict):
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


def git_status_entries(root: Path):
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    entries = []
    for raw_line in result.stdout.splitlines():
        if not raw_line:
            continue
        code = raw_line[:2]
        path = raw_line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        entries.append({"code": code, "path": path})
    return entries


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


def checkout_status_snapshot(root: Path, captured_at: str | None = None, entries: list[dict] | None = None):
    status_entries = sorted(entries if entries is not None else git_status_entries(root), key=lambda item: (item["path"], item["code"]))
    counts = dirty_counts(status_entries)
    changed = sorted({entry["path"] for entry in status_entries})
    head = git_output(["rev-parse", "HEAD"], root)
    branch = git_output(["rev-parse", "--abbrev-ref", "HEAD"], root)
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
        "captured_at": captured_at or now_iso(),
        "head": head,
        "branch": branch,
        "dirty": bool(status_entries),
        "counts": counts,
        "changed_files": changed,
        "status_entries": status_entries,
        "staged_diff_sha256": hashlib.sha256(staged_diff).hexdigest(),
        "unstaged_diff_sha256": hashlib.sha256(unstaged_diff).hexdigest(),
        "untracked_content": untracked_hashes,
        "state_sha256": digest.hexdigest(),
    }


def dirty_checkout_payload(root: Path, task_id: str, entries: list[dict]):
    counts = dirty_counts(entries)
    recommendations = [
        "make agent-preflight",
        "make agent-task-status",
        "make agent-task-closeout",
        "git status --short",
        f"DIRTY_PRIMARY_BASELINE=1 make agent-task-prepare TASK={task_id}",
    ]
    return {
        "schema_version": 1,
        "command": "agent-task-prepare",
        "result": "blocked",
        "blockers": ["Main checkout must be clean before preparing a write-capable task worktree."],
        "repo": str(root),
        "dirty": {
            "count": len(entries),
            "entries": entries,
            "tracked_count": counts["tracked"],
            "untracked_count": counts["untracked"],
            "staged_count": counts["staged"],
            "unstaged_count": counts["unstaged"],
            "attribution": attribution_object(source="unknown"),
        },
        "recommendations": recommendations,
        "exit_code": 1,
    }


def untracked_scope_blockers(entries: list[dict], scope: list[str]) -> list[dict]:
    if not scope:
        return [
            {
                "path": entry["path"],
                "code": entry["code"],
                "reason": "task scope is unknown",
            }
            for entry in entries
            if entry["code"] == "??"
        ]
    blockers = []
    for entry in entries:
        if entry["code"] != "??":
            continue
        for item in scope:
            if paths_overlap(entry["path"], item):
                blockers.append(
                    {
                        "path": entry["path"],
                        "code": entry["code"],
                        "scope": item,
                        "reason": "untracked primary file overlaps task scope",
                    }
                )
                break
    return blockers


def untracked_scope_payload(root: Path, task_id: str, scope: list[str], blockers: list[dict]):
    recommendations = [
        "commit the untracked source files before preparing the task worktree",
        "or park/remove them from the primary checkout before preparing the task",
        f"then rerun: make agent-task-prepare TASK={task_id} SCOPE=\"{' '.join(scope)}\"",
    ]
    return {
        "schema_version": 1,
        "command": "agent-task-prepare",
        "result": "blocked",
        "repo": str(root),
        "blockers": [
            "Dirty primary baseline contains untracked files inside the task scope; a new task worktree would not contain those files."
        ],
        "scope": scope,
        "untracked_scope_files": blockers,
        "recommendations": recommendations,
        "exit_code": 1,
    }


def render_untracked_scope_block(payload: dict):
    lines = [
        "Dirty primary baseline contains untracked files inside the task scope.",
        "A new task worktree starts from HEAD and would not contain those files.",
        "",
        "Untracked scoped files:",
    ]
    lines.extend(
        f" - {item['path']} ({item.get('reason')}; scope={item.get('scope', 'unknown')})"
        for item in payload["untracked_scope_files"]
    )
    lines.extend(["", "Next safe commands:"])
    lines.extend(f" - {command}" for command in payload["recommendations"])
    return "\n".join(lines)


def ensure_dirty_baseline_scope_is_materialized(root: Path, task_id: str, scope: list[str], entries: list[dict], json_output: bool):
    blockers = untracked_scope_blockers(entries, scope)
    if not blockers:
        return
    payload = untracked_scope_payload(root, task_id, scope, blockers)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        raise SystemExit(1)
    raise SystemExit(render_untracked_scope_block(payload))


def render_dirty_checkout(payload: dict):
    lines = [
        "Main checkout must be clean before preparing a write-capable task worktree.",
        "",
        f"Changed files: {payload['dirty']['count']}",
        f"Tracked/untracked: {payload['dirty']['tracked_count']} / {payload['dirty']['untracked_count']}",
        f"Staged/unstaged: {payload['dirty']['staged_count']} / {payload['dirty']['unstaged_count']}",
    ]
    if payload["dirty"]["entries"]:
        lines.append("")
        lines.append("Dirty entries:")
        lines.extend(f" - {entry['code']} {entry['path']}" for entry in payload["dirty"]["entries"])
    lines.append("")
    lines.append("Attribution: unknown (current checkout dirt has no local task metadata).")
    lines.extend(
        [
            "",
            "Next safe commands:",
            *[f" - {command}" for command in payload["recommendations"]],
            "",
            "Use DIRTY_PRIMARY_BASELINE=1 only when the operator accepts recording the current dirty primary state.",
        ]
    )
    return "\n".join(lines)


def safe_slug(value: str):
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-._")
    return slug or "task"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def add_minutes_iso(value: str, minutes: int):
    started = datetime.fromisoformat(value)
    return (started + timedelta(minutes=minutes)).isoformat()


def tasks_dir(root: Path):
    return root / ".agent-workflows" / "tasks"


def ensure_task_gitignore(root: Path):
    path = tasks_dir(root) / ".gitignore"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("*\n!.gitignore\n", encoding="utf-8")


def lock_path(root: Path):
    return tasks_dir(root) / ".prepare.lock"


def acquire_launch_lock(root: Path, task_id: str):
    path = lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": task_id,
        "pid": os.getpid(),
        "created_at": now_iso(),
    }
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise SystemExit(
            f"Another agent-task-prepare launch appears to be active: {path.relative_to(root)}\n"
            "Remove the lock only after confirming no launcher is running."
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def release_launch_lock(path: Path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass


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
            payload["_metadata_path"] = str(path.relative_to(root))
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


def ensure_clean_main(root: Path, task_id: str, allow_dirty: bool, json_output: bool):
    status = git_status_entries(root)
    if status and not allow_dirty:
        payload = dirty_checkout_payload(root, task_id, status)
        if json_output:
            print(json.dumps(payload, indent=2, sort_keys=True))
            raise SystemExit(1)
        raise SystemExit(render_dirty_checkout(payload))
    return status


def default_worktree_root(root: Path):
    return root.parent / f"{root.name}-agent-worktrees"


def allocate_paths(root: Path, args, task_slug: str):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_id = f"{task_slug}-{timestamp}"
    branch = f"codex/task-{run_id}"
    worktree_parent = Path(args.worktree_root).expanduser() if args.worktree_root else default_worktree_root(root)
    worktree_path = (worktree_parent / run_id).resolve()
    return branch, worktree_path, run_id


def create_worktree(root: Path, branch: str, worktree_path: Path, base_ref: str):
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    git_output(["worktree", "add", "-b", branch, str(worktree_path), base_ref], root)


def active_task_context(existing_tasks: list[dict], warnings: list[str]):
    return {
        "active_task_count": len(existing_tasks),
        "active_tasks": [
            {
                "task_id": task.get("task_id") or task.get("id") or "unknown",
                "status": task.get("status") or "unknown",
                "scope": task.get("scope") or [],
                "branch": task.get("branch") or "",
                "worktree": task.get("worktree") or "",
                "owner": task.get("owner"),
                "owner_label": task.get("owner_label"),
                "session_id": task.get("session_id"),
                "thread_id": task.get("thread_id"),
                "automation_id": task.get("automation_id"),
                "attribution": task.get("attribution") if isinstance(task.get("attribution"), dict) else task_attribution(task),
                "lease_expires_at": task.get("lease_expires_at"),
            }
            for task in existing_tasks
        ],
        "overlap_warnings": warnings,
    }


def build_task_packet(
    args,
    root: Path,
    worktree_path: Path,
    task_slug: str,
    scope: list[str],
    created_at: str,
    existing_tasks: list[dict],
    warnings: list[str],
    primary_baseline: dict | None,
):
    title = args.title.strip() if args.title.strip() else f"Implement {args.task}"
    goal_report = goal_check.build_goal_check_report(worktree_path, scope)
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
                "Primary checkout dirty baseline recorded." if primary_baseline else "Primary checkout was clean at preparation.",
            ],
            "non_goals": [
                "Do not edit files outside the approved task scope.",
                "Do not stage, commit, push, or merge without human approval.",
            ],
        },
        "story": {
            "type": "operator-story",
            "actor": "write-capable implementation agent",
            "need": title,
            "outcome": "Complete the approved task within the prepared worktree and declared scope.",
            "acceptance_summary": "The diff stays inside allowed_files and validation evidence is recorded in the receipt.",
            "source": args.task,
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
        "goal_alignment": goal_check.goal_alignment_from_report(goal_report),
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
        "closeout_requirements": {
            "final_receipt_path": f".agent-workflows/tasks/{task_slug}/receipt.json",
            "readiness_check": {
                "command": "make agent-task-ready TASK_READY_JSON=1",
                "expected_result": "readiness passes or blockers are recorded before handoff",
            },
            "lifecycle_action": {
                "action": "finish",
                "command": (
                    f"make agent-task-finalize TASK={args.task} "
                    f"TASK_RECEIPT=.agent-workflows/tasks/{task_slug}/receipt.json TASK_FINALIZE_JSON=1"
                ),
                "expected_result": "task metadata is terminal and the final receipt is linked",
            },
            "final_task_status": {
                "command": "make agent-task-status TASK_STATUS_INCLUDE_CLOSED=1 TASK_STATUS_JSON=1",
                "expected_result": "terminal task metadata, final receipt, and active overlap state are visible",
            },
            "closeout_preview": {
                "command": "make agent-task-closeout TASK_CLOSEOUT_JSON=1",
                "expected_result": "finished worktree cleanup is eligible, retained, or blocked with reasons",
                "apply_requires_explicit_approval": True,
            },
            "dirty_state_explanation": (
                "Record whether the task worktree is clean, contains only expected task artifacts, "
                "or preserves unrelated dirty work."
            ),
            "primary_checkout_baseline": {
                "required": bool(primary_baseline),
                "expected_result": "Readiness/finalize must block if the primary checkout changed after the stored dirty baseline.",
            },
        },
        "docs_impact": {
            "expected": "unknown",
            "paths": [],
            "waiver_allowed": True,
            "documentation_surfaces": [
                "README.md",
                "docs/cli-reference.md",
                "docs/rollout-guide.md",
                "docs/harness-engineering.md",
                "templates/common/ops-agent-workflow.md",
            ],
            "release_metadata": ["VERSION", "CHANGELOG.md"],
            "generated_docs": ["docs/cli-reference.md"],
            "contract_references": [
                "schemas/*.schema.json or workflows/schemas/*.schema.json when public JSON/schema contracts change",
                ".agent-workflows/docs-as-tests.json when docs-as-tests claims cover the change",
            ],
            "verification_commands": [
                "make docs-check",
                "make docs-freshness",
                "make version-check",
                "make agent-changelog-update CHANGELOG_UPDATE_CHECK=1 when release-note work may be required",
                "make docs-as-tests when docs-as-tests claims apply",
            ],
            "notes": "Decide during implementation and record exact docs, release metadata, and validation evidence in the receipt.",
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
        "coordination": active_task_context(existing_tasks, warnings),
        "primary_checkout_baseline": primary_baseline,
        "handoff": {
            "recommended_prompt": "fix-implementer.md",
            "owner": None,
            "dependencies": [],
            "next_packet_hint": None,
        },
    }


def build_receipt_template(
    args,
    root: Path,
    worktree_path: Path,
    branch: str,
    scope: list[str],
    created_at: str,
    run_id: str,
    existing_tasks: list[dict],
    warnings: list[str],
    primary_baseline: dict | None,
):
    return {
        "schema_version": 1,
        "run": {
            "id": run_id,
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
            "behavior_change": None,
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
        "coordination": {
            **active_task_context(existing_tasks, warnings),
            "owner": args.owner,
            "owner_label": args.owner_label,
            "session_id": args.session_id,
            "thread_id": args.thread_id,
            "automation_id": args.automation_id,
            "attribution": args_attribution(
                args,
                run_id=run_id,
                metadata_path=f".agent-workflows/tasks/{safe_slug(args.task)}.json",
            ),
            "heartbeat_at": created_at,
            "lease_expires_at": add_minutes_iso(created_at, args.lease_minutes),
        },
        "primary_checkout_baseline": primary_baseline,
        "harness_metrics": {
            "context_file_count": 0,
            "commands_run_count": 0,
            "changed_file_count": 0,
            "token_budget": {
                "estimated_tokens": None,
                "budget": None,
                "result": "not-run",
            },
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


def build_metadata(
    args,
    root: Path,
    worktree_path: Path,
    branch: str,
    scope: list[str],
    created_at: str,
    warnings: list[str],
    run_id: str,
    primary_baseline: dict | None,
):
    metadata_relpath = f".agent-workflows/tasks/{safe_slug(args.task)}.json"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "task_id": args.task,
        "title": args.title.strip() or f"Implement {args.task}",
        "status": "in-progress",
        "created_at": created_at,
        "updated_at": created_at,
        "owner": args.owner,
        "owner_label": args.owner_label,
        "session_id": args.session_id,
        "thread_id": args.thread_id,
        "automation_id": args.automation_id,
        "attribution": args_attribution(args, run_id=run_id, metadata_path=metadata_relpath),
        "heartbeat_at": created_at,
        "lease_minutes": args.lease_minutes,
        "lease_expires_at": add_minutes_iso(created_at, args.lease_minutes),
        "final_receipt": None,
        "source_repo": str(root),
        "base_ref": args.base_ref,
        "primary_checkout_baseline": primary_baseline,
        "branch": branch,
        "worktree": str(worktree_path),
        "scope": scope,
        "overlap_warnings": warnings,
        "lifecycle_events": [
            {
                "event": "prepared",
                "at": created_at,
                "owner": args.owner,
                "owner_label": args.owner_label,
                "session_id": args.session_id,
                "thread_id": args.thread_id,
                "automation_id": args.automation_id,
            }
        ],
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
    parser.add_argument("--dirty-primary-baseline", action="store_true", help="Allow a dirty primary checkout by recording a baseline that readiness/finalize must later compare")
    parser.add_argument("--allow-dirty", action="store_true", help="Deprecated alias for --dirty-primary-baseline")
    parser.add_argument("--owner", default="", help="Human or agent owner recorded in task metadata")
    parser.add_argument("--owner-label", default="", help="Human-readable owner label recorded in task attribution")
    parser.add_argument("--session-id", default="", help="Calling session/thread id recorded in task metadata")
    parser.add_argument("--thread-id", default="", help="Calling thread id recorded in task attribution")
    parser.add_argument("--automation-id", default="", help="Automation id recorded in task attribution")
    parser.add_argument("--lease-minutes", type=int, default=240, help="Minutes before the task lease should be treated as stale")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable blocker details when preparation cannot start")
    return parser.parse_args()


def main():
    args = parse_args()
    root = repo_root()
    ensure_primary_checkout(root)
    task_slug = safe_slug(args.task)
    scope = parse_scope(args.scope)
    created_at = now_iso()

    ensure_task_gitignore(root)
    dirty_primary_baseline = args.dirty_primary_baseline or args.allow_dirty
    main_status = ensure_clean_main(root, args.task, dirty_primary_baseline, args.json)
    if main_status and dirty_primary_baseline:
        ensure_dirty_baseline_scope_is_materialized(root, args.task, scope, main_status, args.json)
    primary_baseline = checkout_status_snapshot(root, created_at, main_status) if main_status and dirty_primary_baseline else None
    existing_tasks = active_tasks(root)
    warnings = overlap_warnings(scope, existing_tasks)
    blocking = warnings and args.overlap_policy == "block"
    if blocking:
        raise SystemExit("Task scope overlaps an in-flight task:\n" + "\n".join(f"- {warning}" for warning in warnings))

    lock = acquire_launch_lock(root, args.task)
    try:
        branch, worktree_path, run_id = allocate_paths(root, args, task_slug)
        create_worktree(root, branch, worktree_path, args.base_ref)

        artifact_dir = worktree_path / ".agent-workflows" / "tasks" / task_slug
        task_packet_path = artifact_dir / "task-packet.json"
        receipt_path = artifact_dir / "receipt.template.json"
        metadata_path = tasks_dir(root) / f"{task_slug}.json"

        write_json(task_packet_path, build_task_packet(args, root, worktree_path, task_slug, scope, created_at, existing_tasks, warnings, primary_baseline))
        write_json(receipt_path, build_receipt_template(args, root, worktree_path, branch, scope, created_at, run_id, existing_tasks, warnings, primary_baseline))
        write_json(metadata_path, build_metadata(args, root, worktree_path, branch, scope, created_at, warnings, run_id, primary_baseline))
    finally:
        release_launch_lock(lock)

    print("Agent task worktree prepared:")
    print(f" - task: {args.task}")
    print(f" - run id: {run_id}")
    print(f" - branch: {branch}")
    print(f" - worktree: {worktree_path}")
    print(f" - task packet: {task_packet_path.relative_to(worktree_path)}")
    print(f" - receipt template: {receipt_path.relative_to(worktree_path)}")
    print(f" - metadata: {metadata_path.relative_to(root)}")
    if primary_baseline:
        print(" - warning: primary checkout dirty baseline recorded")
        print(f" - primary baseline hash: {primary_baseline['state_sha256']}")
    for warning in warnings:
        print(f" - warning: {warning}")
    print("\nNext steps:")
    print(f"  cd {worktree_path}")
    print(f"  read {task_packet_path.relative_to(worktree_path)}")
    print("  run validation commands and update the receipt before handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
