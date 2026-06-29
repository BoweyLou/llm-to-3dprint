#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess


TERMINAL_STATUSES = {"done", "blocked", "abandoned"}


def clean_optional(value: str | None):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def attribution_object(payload: dict, metadata_path: str | None = None):
    final_receipt = clean_optional(payload.get("final_receipt"))
    values = {
        "owner": clean_optional(payload.get("owner")),
        "owner_label": clean_optional(payload.get("owner_label")),
        "session_id": clean_optional(payload.get("session_id")),
        "thread_id": clean_optional(payload.get("thread_id")),
        "automation_id": clean_optional(payload.get("automation_id")),
        "run_id": clean_optional(payload.get("run_id")),
        "metadata_path": clean_optional(metadata_path),
        "latest_receipt": {
            "path": final_receipt,
            "provenance": "metadata" if final_receipt else None,
        },
    }
    identity_fields = ("owner", "owner_label", "session_id", "thread_id", "automation_id", "run_id")
    confidence = "metadata" if any(values.get(field) for field in identity_fields) else "unknown"
    values["confidence"] = confidence
    values["source"] = confidence
    return values


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
    return result.stdout.strip()


def repo_root():
    stdout = git_output(["rev-parse", "--show-toplevel"], Path.cwd())
    return Path(stdout).resolve()


def safe_slug(value: str):
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "task"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def add_minutes(value: str, minutes: int):
    return (datetime.fromisoformat(value) + timedelta(minutes=minutes)).isoformat()


def tasks_dir(root: Path):
    return root / ".agent-workflows" / "tasks"


def task_path(root: Path, task_id: str):
    return tasks_dir(root) / f"{safe_slug(task_id)}.json"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Task metadata not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid task metadata JSON: {path}: {exc}") from exc


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_event(payload: dict, action: str, at: str, args):
    payload.setdefault("lifecycle_events", []).append(
        {
            "event": action,
            "at": at,
            "owner": args.owner or payload.get("owner"),
            "owner_label": args.owner_label or payload.get("owner_label"),
            "session_id": args.session_id or payload.get("session_id"),
            "thread_id": args.thread_id or payload.get("thread_id"),
            "automation_id": args.automation_id or payload.get("automation_id"),
            "reason": args.reason,
            "receipt": args.receipt,
        }
    )


def update_task(root: Path, args):
    path = task_path(root, args.task)
    payload = read_json(path)
    at = now_iso()
    action = args.action

    if args.owner:
        payload["owner"] = args.owner
    if args.owner_label:
        payload["owner_label"] = args.owner_label
    if args.session_id:
        payload["session_id"] = args.session_id
    if args.thread_id:
        payload["thread_id"] = args.thread_id
    if args.automation_id:
        payload["automation_id"] = args.automation_id

    if action == "finish":
        payload["status"] = "done"
        payload["completed_at"] = at
    elif action == "block":
        payload["status"] = "blocked"
        payload["blocked_at"] = at
    elif action == "abandon":
        payload["status"] = "abandoned"
        payload["abandoned_at"] = at
    elif action == "heartbeat":
        payload["status"] = payload.get("status") or "in-progress"
        payload["heartbeat_at"] = at
        payload["lease_minutes"] = args.lease_minutes
        payload["lease_expires_at"] = add_minutes(at, args.lease_minutes)
    elif action == "link-receipt":
        payload["final_receipt"] = args.receipt
    else:
        raise SystemExit(f"Unsupported action for task update: {action}")

    if args.receipt:
        payload["final_receipt"] = args.receipt
    payload["updated_at"] = at
    payload["attribution"] = attribution_object(payload, str(path.relative_to(root)))
    append_event(payload, action, at, args)
    write_json(path, payload)
    return {
        "schema_version": 1,
        "command": "agent-task-lifecycle",
        "action": action,
        "repo_root": str(root),
        "task_id": payload.get("task_id") or args.task,
        "metadata_path": str(path.relative_to(root)),
        "status": payload.get("status"),
        "final_receipt": payload.get("final_receipt"),
        "attribution": payload.get("attribution"),
        "lease_expires_at": payload.get("lease_expires_at"),
    }


def prune_tasks(root: Path, args):
    directory = tasks_dir(root)
    pruned = []
    kept = []
    if directory.exists():
        for path in sorted(directory.glob("*.json")):
            payload = read_json(path)
            status = payload.get("status")
            item = {
                "task_id": payload.get("task_id") or path.stem,
                "metadata_path": str(path.relative_to(root)),
                "status": status,
                "attribution": attribution_object(payload, str(path.relative_to(root))),
            }
            if status in TERMINAL_STATUSES:
                pruned.append(item)
                if args.apply:
                    path.unlink()
            else:
                kept.append(item)
    return {
        "schema_version": 1,
        "command": "agent-task-lifecycle",
        "action": "prune",
        "repo_root": str(root),
        "applied": args.apply,
        "pruned": pruned,
        "kept": kept,
    }


def render_text(payload: dict):
    if payload["action"] == "prune":
        print("Agent task prune:")
        print(f" - repo: {payload['repo_root']}")
        print(f" - applied: {str(payload['applied']).lower()}")
        print(f" - closed metadata candidates: {len(payload['pruned'])}")
        for item in payload["pruned"]:
            print(f"   - {item['task_id']} [{item['status']}] {item['metadata_path']}")
        return
    print("Agent task lifecycle:")
    print(f" - task: {payload['task_id']}")
    print(f" - action: {payload['action']}")
    print(f" - status: {payload['status']}")
    print(f" - metadata: {payload['metadata_path']}")
    if payload.get("final_receipt"):
        print(f" - final receipt: {payload['final_receipt']}")
    attribution = payload.get("attribution") or {}
    if attribution:
        print(
            " - attribution: "
            f"owner={attribution.get('owner') or '(unknown)'} "
            f"label={attribution.get('owner_label') or '(unknown)'} "
            f"session={attribution.get('session_id') or '(unknown)'} "
            f"thread={attribution.get('thread_id') or '(unknown)'} "
            f"automation={attribution.get('automation_id') or '(unknown)'} "
            f"source={attribution.get('source') or 'unknown'}"
        )
    if payload.get("lease_expires_at"):
        print(f" - lease expires: {payload['lease_expires_at']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Update local agent task lifecycle metadata")
    parser.add_argument("action", choices=["finish", "block", "abandon", "heartbeat", "link-receipt", "prune"])
    parser.add_argument("--task", help="Task id to update")
    parser.add_argument("--reason", default="", help="Reason recorded in lifecycle events")
    parser.add_argument("--receipt", default="", help="Final receipt path to link")
    parser.add_argument("--owner", default="", help="Owner to record")
    parser.add_argument("--owner-label", default="", help="Human-readable owner label to record")
    parser.add_argument("--session-id", default="", help="Session/thread id to record")
    parser.add_argument("--thread-id", default="", help="Thread id to record")
    parser.add_argument("--automation-id", default="", help="Automation id to record")
    parser.add_argument("--lease-minutes", type=int, default=240, help="Lease extension for heartbeat")
    parser.add_argument("--apply", action="store_true", help="Apply prune; prune is dry-run by default")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()
    if args.action != "prune" and not args.task:
        raise SystemExit("--task is required unless action is prune")
    if args.action == "link-receipt" and not args.receipt:
        raise SystemExit("--receipt is required for link-receipt")
    return args


def main():
    args = parse_args()
    root = repo_root()
    payload = prune_tasks(root, args) if args.action == "prune" else update_task(root, args)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        render_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
