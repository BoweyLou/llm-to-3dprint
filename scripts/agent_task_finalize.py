#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import agent_task_ready


SCRIPT_DIR = Path(__file__).resolve().parent
TERMINAL_ACTIONS = {"finish", "block", "abandon"}


def clean_optional(value: str | None):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def attribution_object(metadata: dict, args=None):
    existing = metadata.get("attribution")
    owner = getattr(args, "owner", "") if args else ""
    owner_label = getattr(args, "owner_label", "") if args else ""
    session_id = getattr(args, "session_id", "") if args else ""
    thread_id = getattr(args, "thread_id", "") if args else ""
    automation_id = getattr(args, "automation_id", "") if args else ""
    receipt_arg = clean_optional(getattr(args, "receipt", "") if args else "")
    final_receipt = receipt_arg or clean_optional(metadata.get("final_receipt"))
    if isinstance(existing, dict):
        latest = existing.get("latest_receipt") if isinstance(existing.get("latest_receipt"), dict) else {}
        merged = {
            **existing,
            "owner": clean_optional(owner) or existing.get("owner"),
            "owner_label": clean_optional(owner_label) or existing.get("owner_label"),
            "session_id": clean_optional(session_id) or existing.get("session_id"),
            "thread_id": clean_optional(thread_id) or existing.get("thread_id"),
            "automation_id": clean_optional(automation_id) or existing.get("automation_id"),
            "latest_receipt": {
                **latest,
                "path": final_receipt or latest.get("path"),
                "provenance": "finalize-argument" if receipt_arg else latest.get("provenance") or ("metadata" if final_receipt else None),
            },
            "source": existing.get("source") or "metadata",
            "confidence": existing.get("confidence") or existing.get("source") or "metadata",
        }
        if any(merged.get(field) for field in ("owner", "owner_label", "session_id", "thread_id", "automation_id", "run_id")) and merged["confidence"] == "unknown":
            merged["confidence"] = "metadata"
            merged["source"] = "metadata"
        return merged
    values = {
        "owner": clean_optional(owner) or clean_optional(metadata.get("owner")),
        "owner_label": clean_optional(owner_label) or clean_optional(metadata.get("owner_label")),
        "session_id": clean_optional(session_id) or clean_optional(metadata.get("session_id")),
        "thread_id": clean_optional(thread_id) or clean_optional(metadata.get("thread_id")),
        "automation_id": clean_optional(automation_id) or clean_optional(metadata.get("automation_id")),
        "run_id": clean_optional(metadata.get("run_id")),
        "metadata_path": clean_optional(metadata.get("_metadata_path")),
        "latest_receipt": {
            "path": final_receipt,
            "provenance": "finalize-argument" if receipt_arg else ("metadata" if final_receipt else None),
        },
    }
    confidence = "metadata" if any(values.get(field) for field in ("owner", "owner_label", "session_id", "thread_id", "automation_id", "run_id")) else "unknown"
    values["confidence"] = confidence
    values["source"] = confidence
    return values


def run_command(args: list[str], cwd: Path):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    return {
        "command": " ".join(args),
        "cwd": str(cwd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def git_output(args: list[str], cwd: Path, check=True):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def repo_root():
    return Path(git_output(["rev-parse", "--show-toplevel"], Path.cwd())).resolve()


def git_common_dir(root: Path):
    common = Path(git_output(["rev-parse", "--git-common-dir"], root))
    if not common.is_absolute():
        common = root / common
    return common.resolve()


def primary_checkout(root: Path):
    common = git_common_dir(root)
    if common.name == ".git":
        return common.parent.resolve()
    return root


def safe_slug(value: str):
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "task"


def tasks_dir(root: Path):
    return root / ".agent-workflows" / "tasks"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Task metadata not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid task metadata JSON: {path}: {exc}") from exc


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def task_metadata(primary: Path, task_id: str):
    path = tasks_dir(primary) / f"{safe_slug(task_id)}.json"
    payload = read_json(path)
    payload["_metadata_path"] = str(path.relative_to(primary))
    return payload


def resolve_worktree(primary: Path, metadata: dict):
    value = str(metadata.get("worktree") or "").strip()
    if not value:
        return primary
    return Path(value).expanduser().resolve()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def readiness_command(args, worktree: Path):
    command = [sys.executable, str(SCRIPT_DIR / "agent_task_ready.py"), "--task", args.task, "--json"]
    if args.receipt:
        command.extend(["--receipt", args.receipt])
    if args.base_ref:
        command.extend(["--base-ref", args.base_ref])
    return run_command(command, worktree)


def lifecycle_command(args, primary: Path):
    command = [sys.executable, str(SCRIPT_DIR / "agent_task_lifecycle.py"), args.action, "--task", args.task, "--json"]
    if args.reason:
        command.extend(["--reason", args.reason])
    if args.receipt:
        command.extend(["--receipt", args.receipt])
    if args.owner:
        command.extend(["--owner", args.owner])
    if args.owner_label:
        command.extend(["--owner-label", args.owner_label])
    if args.session_id:
        command.extend(["--session-id", args.session_id])
    if args.thread_id:
        command.extend(["--thread-id", args.thread_id])
    if args.automation_id:
        command.extend(["--automation-id", args.automation_id])
    return run_command(command, primary)


def task_status_command(primary: Path):
    return run_command([sys.executable, str(SCRIPT_DIR / "agent_task_status.py"), "--json", "--include-closed"], primary)


def closeout_command(args, primary: Path):
    command = [sys.executable, str(SCRIPT_DIR / "agent_task_cleanup.py"), "--closeout", "--json"]
    if args.closeout_apply:
        command.append("--apply")
    return run_command(command, primary)


def parse_json_output(step: dict):
    if step["returncode"] != 0 or not step["stdout"].strip():
        return None
    try:
        return json.loads(step["stdout"])
    except json.JSONDecodeError:
        return None


def finalizer_receipt_path(primary: Path, task_id: str):
    return tasks_dir(primary) / safe_slug(task_id) / "finalize-receipt.json"


def build_payload(args, primary: Path, worktree: Path, metadata: dict, steps: dict, result: str, exit_code: int):
    return {
        "schema_version": 1,
        "command": "agent-task-finalize",
        "created_at": now_iso(),
        "repo_root": str(primary),
        "task_id": args.task,
        "action": args.action,
        "result": result,
        "exit_code": exit_code,
        "worktree": str(worktree),
        "metadata_path": metadata.get("_metadata_path"),
        "final_receipt": args.receipt,
        "attribution": attribution_object(metadata, args),
        "ready": parse_json_output(steps["readiness"]) if steps.get("readiness") else None,
        "primary_checkout_baseline": parse_json_output(steps["primary_baseline"]) if steps.get("primary_baseline") else None,
        "lifecycle": parse_json_output(steps["lifecycle"]) if steps.get("lifecycle") else None,
        "task_status": parse_json_output(steps["task_status"]) if steps.get("task_status") else None,
        "closeout": parse_json_output(steps["closeout"]) if steps.get("closeout") else None,
        "steps": steps,
        "closeout_apply": args.closeout_apply,
        "skip_ready": args.skip_ready,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Finalize one prepared agent task with readiness, lifecycle, status, and closeout evidence")
    parser.add_argument("--task", required=True, help="Task id to finalize")
    parser.add_argument("--action", choices=sorted(TERMINAL_ACTIONS), default="finish")
    parser.add_argument("--receipt", default="", help="Final task receipt path")
    parser.add_argument("--base-ref", default="", help="Base ref passed through to agent-task-ready")
    parser.add_argument("--reason", default="", help="Lifecycle reason")
    parser.add_argument("--owner", default="", help="Owner to record in lifecycle metadata")
    parser.add_argument("--owner-label", default="", help="Human-readable owner label to record in lifecycle metadata")
    parser.add_argument("--session-id", default="", help="Session/thread id to record in lifecycle metadata")
    parser.add_argument("--thread-id", default="", help="Thread id to record in lifecycle metadata")
    parser.add_argument("--automation-id", default="", help="Automation id to record in lifecycle metadata")
    parser.add_argument("--skip-ready", action="store_true", help="Skip readiness check before finish")
    parser.add_argument("--closeout-apply", action="store_true", help="Apply closeout removal for eligible finished worktrees")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def render_text(payload: dict):
    lines = [
        "Agent task finalizer:",
        f" - task: {payload['task_id']}",
        f" - action: {payload['action']}",
        f" - result: {payload['result']}",
        f" - worktree: {payload['worktree']}",
        f" - finalizer receipt: {payload.get('finalizer_receipt', '(not written)')}",
    ]
    for name in ("primary_baseline", "readiness", "lifecycle", "task_status", "closeout"):
        step = payload["steps"].get(name)
        if step:
            lines.append(f" - {name}: exit {step['returncode']}")
    return "\n".join(lines)


def main():
    args = parse_args()
    if args.action == "finish" and not args.receipt:
        raise SystemExit("--receipt is required when --action finish")

    current = repo_root()
    primary = primary_checkout(current)
    metadata = task_metadata(primary, args.task)
    worktree = resolve_worktree(primary, metadata)
    steps: dict[str, dict] = {}

    baseline_report, baseline_blockers = agent_task_ready.primary_baseline_guard(metadata, primary)
    if baseline_report:
        steps["primary_baseline"] = {
            "command": "primary dirty baseline guard",
            "cwd": str(primary),
            "returncode": 1 if baseline_blockers else 0,
            "stdout": json.dumps(
                {
                    "primary_checkout_baseline": baseline_report,
                    "blockers": baseline_blockers,
                },
                indent=2,
                sort_keys=True,
            ),
            "stderr": "\n".join(baseline_blockers),
        }
    if baseline_blockers:
        payload = build_payload(args, primary, worktree, metadata, steps, "blocked", 1)
        receipt = finalizer_receipt_path(primary, args.task)
        payload["finalizer_receipt"] = str(receipt)
        write_json(receipt, payload)
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else render_text(payload))
        return 1

    if args.action == "finish" and not args.skip_ready:
        steps["readiness"] = readiness_command(args, worktree)
        if steps["readiness"]["returncode"] != 0:
            payload = build_payload(args, primary, worktree, metadata, steps, "blocked", 1)
            receipt = finalizer_receipt_path(primary, args.task)
            payload["finalizer_receipt"] = str(receipt)
            write_json(receipt, payload)
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else render_text(payload))
            return 1

    steps["lifecycle"] = lifecycle_command(args, primary)
    steps["task_status"] = task_status_command(primary)
    steps["closeout"] = closeout_command(args, primary)
    exit_code = 0 if all(step["returncode"] == 0 for step in steps.values()) else 1
    payload = build_payload(args, primary, worktree, metadata, steps, "passed" if exit_code == 0 else "blocked", exit_code)
    receipt = finalizer_receipt_path(primary, args.task)
    payload["finalizer_receipt"] = str(receipt)
    write_json(receipt, payload)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else render_text(payload))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
