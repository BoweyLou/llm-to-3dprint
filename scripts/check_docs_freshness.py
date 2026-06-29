#!/usr/bin/env python3
"""Check docs freshness beyond path-based docs-impact coverage."""

from __future__ import annotations

import argparse
from copy import deepcopy
from fnmatch import fnmatch
import json
import re
import subprocess
from pathlib import Path
from typing import Any

MARKDOWN_GLOBS = ("*.md", "docs/**/*.md", ".agent-workflows/**/*.md", ".codex/**/*.md")
CONFIG_FILE = "doc-contract.json"
DEFAULT_DOCS_FRESHNESS_CONFIG = {
    "exclude_paths": [],
    "historical_paths": [
        "CHANGELOG.md",
        "docs/adr/",
        "docs/adrs/",
        "docs/audit/",
        "docs/audits/",
        "docs/archive/",
        "docs/archives/",
    ],
}
LOCAL_LINK_RE = re.compile(r"\[[^\]]+\]\((?P<link>[^)]+)\)")
MAKE_RE = re.compile(r"(?:^\s*|`)make\s+(?P<target>[A-Za-z0-9_-]+)")
SCRIPT_RE = re.compile(r"(?:python3\s+)?(?P<script>scripts/[A-Za-z0-9_.-]+\.py)")
SCHEMA_RE = re.compile(r"(?P<schema>(?:schemas|\.agent-workflows/schemas)/[A-Za-z0-9_.-]+\.json)")
TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+):(?:\s|$)")
KNOWN_EXTERNAL_MAKE_TARGETS = {"self-check", "stack-status"}


def repo_root() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "not inside a git repository")
    return Path(result.stdout.strip()).resolve()


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def unique_patterns(patterns: list[str]) -> list[str]:
    return sorted({normalize_path(pattern) for pattern in patterns if normalize_path(pattern)})


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON config in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid config in {path}: top-level value must be an object")
    return payload


def read_pattern_list(config: dict[str, Any], key: str) -> list[str]:
    value = config.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SystemExit(f"Invalid docs_freshness.{key}: expected a list of strings")
    return value


def load_docs_freshness_config(root: Path) -> dict[str, list[str]]:
    config = deepcopy(DEFAULT_DOCS_FRESHNESS_CONFIG)
    path = root / CONFIG_FILE
    if not path.exists():
        return config

    contract = read_json(path)
    docs_freshness = contract.get("docs_freshness", {})
    if docs_freshness is None:
        docs_freshness = {}
    if not isinstance(docs_freshness, dict):
        raise SystemExit("Invalid doc-contract.json: docs_freshness must be an object")

    if "exclude_paths" in docs_freshness:
        config["exclude_paths"] = read_pattern_list(docs_freshness, "exclude_paths")
    if "historical_paths" in docs_freshness:
        config["historical_paths"] = read_pattern_list(docs_freshness, "historical_paths")

    config["exclude_paths"] = unique_patterns(
        [*config["exclude_paths"], *read_pattern_list(docs_freshness, "extra_exclude_paths")]
    )
    config["historical_paths"] = unique_patterns(
        [*config["historical_paths"], *read_pattern_list(docs_freshness, "extra_historical_paths")]
    )
    return config


def matches_pattern(path: str, pattern: str) -> bool:
    candidate = normalize_path(path).lower()
    rule = normalize_path(pattern).lower()
    if not rule:
        return False
    if rule.endswith("/"):
        return candidate.startswith(rule)
    if any(marker in rule for marker in "*?[]"):
        return fnmatch(candidate, rule)
    return candidate == rule or candidate.startswith(f"{rule}/")


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(matches_pattern(path, pattern) for pattern in patterns)


def iter_markdown(root: Path, exclude_paths: list[str]):
    seen: set[Path] = set()
    for pattern in MARKDOWN_GLOBS:
        for path in root.glob(pattern):
            if path in seen or not path.is_file():
                continue
            if ".git" in path.parts:
                continue
            relative = rel(root, path)
            if matches_any(relative, exclude_paths):
                continue
            seen.add(path)
            yield path


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def strip_link_target(value: str) -> str:
    target = value.strip().split()[0]
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target.split("#", 1)[0]


def is_external_link(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:", "tel:"))


def check_links(root: Path, docs: list[Path]) -> list[dict[str, Any]]:
    failures = []
    for path in docs:
        text = read_text(path)
        for line_index, line in enumerate(text.splitlines(), start=1):
            for match in LOCAL_LINK_RE.finditer(line):
                target = strip_link_target(match.group("link"))
                if not target or target.startswith("#") or is_external_link(target):
                    continue
                candidate = (path.parent / target).resolve()
                if not candidate.exists():
                    failures.append(
                        {
                            "type": "missing-local-link",
                            "path": rel(root, path),
                            "line": line_index,
                            "target": match.group("link"),
                        }
                    )
    return failures


def make_targets(root: Path) -> set[str]:
    targets: set[str] = set()
    for path in [
        root / "Makefile",
        root / ".doc-contract-kit" / "make" / "repo-contract.mk",
        root / "templates" / "common" / "kit-makefile.mk",
    ]:
        if not path.exists():
            continue
        for line in read_text(path).splitlines():
            match = TARGET_RE.match(line)
            if match and not match.group(1).startswith("."):
                targets.add(match.group(1))
    return targets


def target_exists(root: Path, target: str) -> bool:
    path = root / target
    if path.exists():
        return True
    if target.startswith("schemas/"):
        return (root / "templates" / "common" / Path(target).name).exists()
    if target.startswith(".agent-workflows/schemas/"):
        return (root / "templates" / "common" / Path(target).name).exists()
    return False


def check_command_refs(root: Path, docs: list[Path], historical_paths: list[str]) -> list[dict[str, Any]]:
    failures = []
    targets = make_targets(root)
    for path in docs:
        if matches_any(rel(root, path), historical_paths):
            continue
        text = read_text(path)
        for line_index, line in enumerate(text.splitlines(), start=1):
            for match in MAKE_RE.finditer(line):
                target = match.group("target")
                if target in KNOWN_EXTERNAL_MAKE_TARGETS or target.endswith("-"):
                    continue
                if target not in targets:
                    failures.append(
                        {
                            "type": "missing-make-target",
                            "path": rel(root, path),
                            "line": line_index,
                            "target": target,
                        }
                    )
            for match in SCRIPT_RE.finditer(line):
                script = match.group("script")
                if not target_exists(root, script):
                    failures.append(
                        {
                            "type": "missing-script-reference",
                            "path": rel(root, path),
                            "line": line_index,
                            "target": script,
                        }
                    )
            for match in SCHEMA_RE.finditer(line):
                schema = match.group("schema")
                if not target_exists(root, schema):
                    failures.append(
                        {
                            "type": "missing-schema-reference",
                            "path": rel(root, path),
                            "line": line_index,
                            "target": schema,
                        }
                    )
    return failures


def semantic_receipt_status(args: argparse.Namespace) -> dict[str, Any]:
    if not args.require_semantic_receipt:
        return {"required": False, "path": args.semantic_receipt, "passed": True}
    if not args.semantic_receipt:
        return {"required": True, "path": None, "passed": False, "error": "semantic receipt path is required"}
    path = Path(args.semantic_receipt).expanduser()
    if not path.is_absolute():
        path = repo_root() / path
    return {
        "required": True,
        "path": args.semantic_receipt,
        "passed": path.exists(),
        "error": None if path.exists() else "semantic receipt path does not exist",
    }


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = Path(args.repo).expanduser().resolve() if args.repo else repo_root()
    docs_freshness = load_docs_freshness_config(root)
    docs = sorted(iter_markdown(root, docs_freshness["exclude_paths"]))
    docs_checked = [rel(root, path) for path in docs]
    historical_docs = [path for path in docs_checked if matches_any(path, docs_freshness["historical_paths"])]
    excluded_docs = sorted(
        rel(root, path)
        for pattern in MARKDOWN_GLOBS
        for path in root.glob(pattern)
        if path.is_file() and ".git" not in path.parts and matches_any(rel(root, path), docs_freshness["exclude_paths"])
    )
    failures = []
    if args.links:
        failures.extend(check_links(root, docs))
    if args.commands:
        failures.extend(check_command_refs(root, docs, docs_freshness["historical_paths"]))
    semantic = semantic_receipt_status(args)
    if not semantic["passed"]:
        failures.append({"type": "missing-semantic-receipt", "target": semantic.get("path"), "error": semantic.get("error")})
    report = {
        "schema_version": 1,
        "command": "docs-freshness",
        "repo_root": str(root),
        "docs_checked": docs_checked,
        "checks": {
            "links": args.links,
            "commands": args.commands,
            "semantic_receipt": semantic,
            "scope": {
                "exclude_paths": docs_freshness["exclude_paths"],
                "historical_paths": docs_freshness["historical_paths"],
                "excluded_docs": sorted(set(excluded_docs)),
                "historical_docs": historical_docs,
            },
        },
        "failure_count": len(failures),
        "failures": failures,
        "result": "failed" if failures else "passed",
    }
    return report, 1 if failures else 0


def render_text(report: dict[str, Any]) -> None:
    print("Docs freshness:")
    print(f" - repo: {report['repo_root']}")
    print(f" - docs checked: {len(report['docs_checked'])}")
    print(f" - result: {report['result']}")
    for failure in report["failures"]:
        location = f"{failure.get('path', '(global)')}:{failure.get('line', '')}".rstrip(":")
        print(f" - {failure['type']}: {location} -> {failure.get('target') or failure.get('error')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local docs freshness surfaces")
    parser.add_argument("--repo", default="", help="Repository root. Defaults to current git root.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--links", action=argparse.BooleanOptionalAction, default=True, help="Check local Markdown links")
    parser.add_argument("--commands", action=argparse.BooleanOptionalAction, default=True, help="Check documented make/script/schema references")
    parser.add_argument("--require-semantic-receipt", action="store_true", help="Require an explicit semantic docs/code review receipt")
    parser.add_argument("--semantic-receipt", default="", help="Path to semantic docs/code review receipt")
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
