#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Script flow:
# 1. Resolve the current target repo, kit checkout, and workflow source repo.
# 2. Optionally fast-forward the kit checkout.
# 3. Apply the same safe repo-contract-kit update to the target and workflow repos.
# 4. Emit text or JSON results so agents can see both update outcomes.
#
# Function guide:
# - git_output/is_git_repo/ancestor_candidates collect local repo facts.
# - discover_kit/discover_workflow_source find the usual local checkouts.
# - run_step/update_repo/render_text/main orchestrate the stack update.

WORKFLOW_REPO_NAMES = ("Codex_CodeReview", "agent-workflow-kit")
KIT_REPO_PATTERNS = (
    ("Hermes", "doc-contract-kit"),
    ("repo-contract-kit",),
    ("doc-contract-kit",),
)
COMMON_LOCAL_ROOTS = (
    Path("/Volumes/Myrtle/Code/04_Code"),
    Path("/Volumes/Myrtle/Code"),
    Path.home() / "Code",
    Path.home() / "Developer",
    Path.home() / "Projects",
)


def git_output(args, cwd: Path, check=False):
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
    stdout, stderr, code = git_output(["rev-parse", "--show-toplevel"], Path.cwd())
    if code != 0:
        raise SystemExit(stderr or stdout or "kit-update-stack must run inside a git repository")
    return Path(stdout).resolve()


def is_git_repo(path: Path):
    stdout, _, code = git_output(["rev-parse", "--is-inside-work-tree"], path)
    return code == 0 and stdout == "true"


def ancestor_candidates(*paths: Path):
    seen = set()
    roots = []
    for path in paths:
        if not path:
            continue
        resolved = path.expanduser().resolve()
        candidates = [resolved] if resolved.is_dir() else [resolved.parent]
        candidates.extend(candidates[0].parents)
        for candidate in candidates:
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                roots.append(candidate)
    return roots


def search_roots(*paths: Path):
    roots = ancestor_candidates(*paths)
    seen = {str(path) for path in roots}
    for root in COMMON_LOCAL_ROOTS:
        expanded = root.expanduser()
        if expanded.exists():
            resolved = expanded.resolve()
            if str(resolved) not in seen:
                seen.add(str(resolved))
                roots.append(resolved)
    return roots


def looks_like_kit(path: Path):
    return (path / "scripts" / "update.py").is_file() and (path / "templates" / "common" / "kit-makefile.mk").is_file()


def looks_like_workflow_source(path: Path):
    return (path / "workflows" / "prompts").is_dir() and (path / "scripts" / "check_self_dogfood_boundary.py").is_file()


def first_env_path(*names: str):
    for name in names:
        value = os.environ.get(name)
        if value:
            return Path(value).expanduser().resolve()
    return None


def validate_kit(path: Path):
    resolved = path.expanduser().resolve()
    if not looks_like_kit(resolved):
        raise SystemExit(f"KIT does not look like repo-contract-kit: {resolved}")
    return resolved


def validate_workflow(path: Path, explicit: bool):
    resolved = path.expanduser().resolve()
    if not is_git_repo(resolved):
        raise SystemExit(f"Workflow source is not a git repository: {resolved}")
    if not explicit and not looks_like_workflow_source(resolved):
        raise SystemExit(f"Discovered legacy workflow source does not look like the old agent-workflow-kit checkout: {resolved}")
    return resolved


def discover_kit(target: Path, explicit: str):
    if explicit:
        return validate_kit(Path(explicit))
    env_path = first_env_path("REPO_CONTRACT_KIT", "KIT")
    if env_path:
        return validate_kit(env_path)
    for root in search_roots(target, Path.cwd()):
        for pattern in KIT_REPO_PATTERNS:
            candidate = root.joinpath(*pattern)
            if looks_like_kit(candidate):
                return candidate.resolve()
    raise SystemExit("Set KIT=/path/to/kit or REPO_CONTRACT_KIT; no local kit checkout was discovered.")


def discover_workflow_source(target: Path, kit: Path, explicit: str):
    if explicit:
        return validate_workflow(Path(explicit), explicit=True)
    env_path = first_env_path("AGENT_WORKFLOW_KIT", "WORKFLOW")
    if env_path:
        return validate_workflow(env_path, explicit=True)
    if looks_like_workflow_source(target):
        return target.resolve()
    for root in search_roots(target, kit, Path.cwd()):
        for name in WORKFLOW_REPO_NAMES:
            candidate = root / name
            if candidate.exists() and looks_like_workflow_source(candidate):
                return candidate.resolve()
    raise SystemExit(
        "Set WORKFLOW=/path/to/Codex_CodeReview or AGENT_WORKFLOW_KIT; no legacy workflow source checkout was discovered. "
        "Checked parent directories and common local roots."
    )


def command_text(command: list[str]):
    return " ".join(command)


def run_step(label: str, command: list[str], cwd: Path):
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "label": label,
        "cwd": str(cwd),
        "command": command_text(command),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def update_repo(label: str, repo: Path, kit: Path, force_managed: bool, runtime_adapters: str):
    command = [sys.executable, str(kit / "scripts" / "update.py"), str(repo), "--apply"]
    if force_managed:
        command.append("--force-managed")
    if runtime_adapters:
        command.extend(["--runtime-adapters", runtime_adapters])
    return run_step(label, command, repo)


def refresh_kit(kit: Path):
    status = run_step("check repo-contract-kit cleanliness", ["git", "status", "--porcelain"], kit)
    if status["returncode"] != 0 or status["stdout"].strip():
        status["returncode"] = status["returncode"] or 1
        if status["stdout"].strip():
            status["stderr"] = "Kit checkout has local changes; commit, stash, or use kit-update-stack explicitly.\n"
        return [status]
    pull = run_step("fast-forward repo-contract-kit", ["git", "pull", "--ff-only"], kit)
    return [status, pull]


def render_text(payload: dict):
    print("Stack kit update:")
    print(f" - target repo: {payload['target_repo']}")
    print(f" - workflow source: {payload['workflow_source']}")
    print(f" - repo-contract-kit: {payload['kit']}")
    print(f" - refresh kit first: {str(payload['refresh']).lower()}")
    for step in payload["steps"]:
        print("")
        print(f"{step['label']}:")
        print(f" - command: {step['command']}")
        print(f" - cwd: {step['cwd']}")
        print(f" - exit: {step['returncode']}")
        if step["stdout"].strip():
            print(step["stdout"].rstrip())
        if step["stderr"].strip():
            print(step["stderr"].rstrip(), file=sys.stderr)
    print("")
    print("Stack update complete." if payload["ok"] else "Stack update failed.")


def parse_args():
    parser = argparse.ArgumentParser(description="Deprecated: update a target repo and a legacy external workflow-source checkout from one kit checkout")
    parser.add_argument("--target", default="", help="Target repo to update. Defaults to the current git repo.")
    parser.add_argument("--kit", default="", help="kit checkout. Defaults to KIT/REPO_CONTRACT_KIT or local discovery.")
    parser.add_argument("--workflow", default="", help="Legacy agent-workflow-kit/Codex_CodeReview checkout. Defaults to WORKFLOW/AGENT_WORKFLOW_KIT or local discovery.")
    parser.add_argument("--refresh", action="store_true", help="Fast-forward pull the kit checkout before updating repos")
    parser.add_argument("--force-managed", action="store_true", help="Forward --force-managed to update.py for both repos")
    parser.add_argument("--runtime-adapters", default="", help="Forward --runtime-adapters to update.py for both repos")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    target = Path(args.target).expanduser().resolve() if args.target else current_repo_root()
    if not is_git_repo(target):
        raise SystemExit(f"Target is not a git repository: {target}")
    kit = discover_kit(target, args.kit)
    workflow = discover_workflow_source(target, kit, args.workflow)

    steps = []
    if args.refresh:
        steps.extend(refresh_kit(kit))
        if any(step["returncode"] != 0 for step in steps):
            payload = build_payload(target, workflow, kit, args.refresh, steps)
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                render_text(payload)
            return 1

    steps.append(update_repo("update target repo", target, kit, args.force_managed, args.runtime_adapters))
    if workflow != target:
        steps.append(update_repo("update workflow source repo", workflow, kit, args.force_managed, args.runtime_adapters))
    else:
        steps.append(
            {
                "label": "update workflow source repo",
                "cwd": str(workflow),
                "command": "skipped: target repo is the workflow source",
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            }
        )

    payload = build_payload(target, workflow, kit, args.refresh, steps)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        render_text(payload)
    return 0 if payload["ok"] else 1


def build_payload(target: Path, workflow: Path, kit: Path, refresh: bool, steps: list[dict]):
    return {
        "schema_version": 1,
        "command": "kit-update-stack",
        "target_repo": str(target),
        "workflow_source": str(workflow),
        "kit": str(kit),
        "refresh": refresh,
        "ok": all(step["returncode"] == 0 for step in steps),
        "steps": steps,
    }


if __name__ == "__main__":
    raise SystemExit(main())
