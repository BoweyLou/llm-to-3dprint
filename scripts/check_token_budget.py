#!/usr/bin/env python3
"""Estimate token footprint for agent-facing context files."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_BUDGETS = {
    "AGENTS.md": 2500,
    "REVIEW.md": 2000,
    ".agent-workflows/**/*.md": 4000,
    ".codex/prompts/**/*.md": 8000,
    "docs/ops/**/*.md": 4000,
}


def repo_root() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "not inside a git repository")
    return Path(result.stdout.strip()).resolve()


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def estimate_tokens(text: str) -> int:
    # A deliberately simple local estimate. It is stable, cheap, and good enough
    # for budget drift detection without binding the repo to one tokenizer.
    return max(1, (len(text) + 3) // 4) if text else 0


def read_config(root: Path) -> dict[str, int]:
    path = root / ".agent-workflows" / "token-budgets.json"
    if not path.exists():
        return dict(DEFAULT_BUDGETS)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid token budget config {path}: {exc}") from exc
    budgets = payload.get("budgets") if isinstance(payload, dict) else None
    if not isinstance(budgets, dict):
        raise SystemExit(f"Invalid token budget config {path}: expected object field 'budgets'")
    return {str(key): int(value) for key, value in budgets.items()}


def candidate_files(root: Path, budgets: dict[str, int]) -> list[Path]:
    files: set[Path] = set()
    for pattern in budgets:
        if any(char in pattern for char in "*?["):
            files.update(path for path in root.glob(pattern) if path.is_file())
        else:
            path = root / pattern
            if path.is_file():
                files.add(path)
    return sorted(files)


def budget_for(path: str, budgets: dict[str, int]) -> tuple[str | None, int | None]:
    for pattern, budget in budgets.items():
        if fnmatch.fnmatch(path, pattern):
            return pattern, budget
    return None, None


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = Path(args.repo).expanduser().resolve() if args.repo else repo_root()
    budgets = read_config(root)
    files = []
    failures = []
    for path in candidate_files(root, budgets):
        relative = rel(root, path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        estimated = estimate_tokens(text)
        pattern, budget = budget_for(relative, budgets)
        status = "passed" if budget is None or estimated <= budget else "over-budget"
        item = {
            "path": relative,
            "matched_budget": pattern,
            "estimated_tokens": estimated,
            "budget": budget,
            "status": status,
        }
        files.append(item)
        if status == "over-budget":
            failures.append(item)
    total = sum(item["estimated_tokens"] for item in files)
    report = {
        "schema_version": 1,
        "command": "token-budget",
        "repo_root": str(root),
        "strict": args.strict,
        "file_count": len(files),
        "total_estimated_tokens": total,
        "failure_count": len(failures),
        "files": files,
        "failures": failures,
        "result": "failed" if args.strict and failures else "passed",
    }
    return report, 1 if args.strict and failures else 0


def render_text(report: dict[str, Any]) -> None:
    print("Agent token budget:")
    print(f" - repo: {report['repo_root']}")
    print(f" - files: {report['file_count']}")
    print(f" - estimated tokens: {report['total_estimated_tokens']}")
    print(f" - result: {report['result']}")
    for item in report["failures"]:
        print(f" - over budget: {item['path']} {item['estimated_tokens']}/{item['budget']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="", help="Repository root. Defaults to current git root.")
    parser.add_argument("--strict", action="store_true", help="Fail when configured budgets are exceeded")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, exit_code = build_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        render_text(report)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
