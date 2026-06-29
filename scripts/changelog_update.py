#!/usr/bin/env python3
"""Build deterministic changelog proposals from docs-impact context."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import check_doc_impact
import version as versioning


def io_record(performed: bool, reason: str, paths: list[str] | None = None) -> dict[str, Any]:
    return {
        "performed": performed,
        "paths": paths or [],
        "reason": reason,
    }


def normalize_path(path: str) -> str:
    return check_doc_impact.normalize_path(path)


def repo_relative_config(repo: Path, config: str) -> Path:
    config_path = Path(config).expanduser()
    if not config_path.is_absolute():
        config_path = repo / config_path
    return config_path


def run_git(repo: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def git_changed_files(repo: Path, mode: str) -> list[str]:
    files: list[str] = []
    if mode in {"branch", "working-tree", "staged"}:
        if mode == "staged":
            files.extend(run_git(repo, ["diff", "--name-only", "--cached"]))
        elif mode == "working-tree":
            files.extend(run_git(repo, ["diff", "--name-only", "--cached"]))
            files.extend(run_git(repo, ["diff", "--name-only"]))
            files.extend(run_git(repo, ["ls-files", "--others", "--exclude-standard"]))
        else:
            for base_ref in ("origin/main", "origin/master"):
                merge_base = run_git(repo, ["merge-base", "HEAD", base_ref])
                if merge_base:
                    files.extend(run_git(repo, ["diff", "--name-only", f"{merge_base[0]}...HEAD"]))
                    break
            files.extend(run_git(repo, ["diff", "--name-only", "--cached"]))
            files.extend(run_git(repo, ["diff", "--name-only"]))
            files.extend(run_git(repo, ["ls-files", "--others", "--exclude-standard"]))
    return sorted({normalize_path(path) for path in files if normalize_path(path)})


def category_records(evaluation: check_doc_impact.Evaluation, config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "category": category,
            "changed_files": sorted(paths),
            "suggested_doc_paths": config["category_doc_paths"].get(category, config["doc_paths"]),
            "covered": category in evaluation.covered_categories,
        }
        for category, paths in sorted(evaluation.categories.items())
    ]


def load_docs_impact_json(repo: Path, path: str) -> dict[str, Any]:
    json_path = Path(path).expanduser()
    if not json_path.is_absolute():
        json_path = repo / json_path
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing docs-impact JSON: {json_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid docs-impact JSON in {json_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid docs-impact JSON in {json_path}: top-level value must be an object")
    return payload


def normalize_docs_impact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    categories = []
    for item in payload.get("categories") or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        if not category:
            continue
        categories.append(
            {
                "category": category,
                "changed_files": sorted(
                    normalize_path(str(path))
                    for path in item.get("changed_files") or []
                    if normalize_path(str(path))
                ),
                "suggested_doc_paths": list(item.get("suggested_doc_paths") or []),
                "covered": bool(item.get("covered")),
            }
        )

    changed_files = sorted(
        normalize_path(str(path))
        for path in payload.get("changed_files") or []
        if normalize_path(str(path))
    )
    docs_changed = sorted(
        normalize_path(str(path))
        for path in payload.get("docs_changed") or []
        if normalize_path(str(path))
    )
    missing_categories = sorted(str(item) for item in payload.get("missing_categories") or [])
    result = payload.get("result") or ("missing-docs" if missing_categories else "covered-or-no-impact")
    return {
        "changed_files": changed_files,
        "docs_changed": docs_changed,
        "categories": categories,
        "missing_categories": missing_categories,
        "no_docs_declaration": bool(payload.get("no_docs_declaration")),
        "result": result,
    }


def build_docs_impact(
    repo: Path,
    *,
    config: str,
    changed_files: list[str] | None,
    staged: bool,
    working_tree: bool,
    docs_impact_json: str | None,
) -> dict[str, Any]:
    if docs_impact_json:
        impact = normalize_docs_impact_payload(load_docs_impact_json(repo, docs_impact_json))
        impact["source"] = "docs-impact-json"
        return impact

    if changed_files:
        files = sorted({normalize_path(path) for path in changed_files if normalize_path(path)})
        mode = "explicit"
    elif staged:
        files = git_changed_files(repo, "staged")
        mode = "staged"
    elif working_tree:
        files = git_changed_files(repo, "working-tree")
        mode = "working-tree"
    else:
        files = git_changed_files(repo, "branch")
        mode = "branch"

    loaded_config = check_doc_impact.load_config(repo_relative_config(repo, config))
    evaluation = check_doc_impact.evaluate(files, loaded_config, no_docs_declaration=False)
    return {
        "source": mode,
        "changed_files": evaluation.changed_files,
        "docs_changed": evaluation.docs_changed,
        "categories": category_records(evaluation, loaded_config),
        "missing_categories": sorted(evaluation.missing_categories),
        "no_docs_declaration": evaluation.no_docs_declaration,
        "result": "missing-docs" if evaluation.failed else "covered-or-no-impact",
    }


def version_state(repo: Path, changed_files: list[str]) -> dict[str, Any]:
    version_file = versioning.version_path(repo)
    changelog_file = versioning.changelog_path(repo)
    version_value = None
    version_valid = False
    version_error = None
    if version_file.exists():
        version_value = version_file.read_text(encoding="utf-8").strip()
        try:
            versioning.validate_version(version_value)
            version_valid = True
        except SystemExit as exc:
            version_error = str(exc)

    return {
        "version_path": "VERSION",
        "version_present": version_file.exists(),
        "version": version_value,
        "version_valid": version_valid,
        "version_error": version_error,
        "version_changed": "VERSION" in changed_files,
        "changelog_path": "CHANGELOG.md",
        "changelog_present": changelog_file.exists(),
        "changelog_changed": "CHANGELOG.md" in changed_files,
        "target_owned": True,
    }


def clean_summary(value: str) -> str:
    value = value.strip()
    while value.startswith("-"):
        value = value[1:].strip()
    return value


def candidate_heading(args: argparse.Namespace, state: dict[str, Any]) -> str:
    if args.section:
        section = args.section.strip()
        if section.startswith("#"):
            return section
        return f"## {section}"
    if args.version:
        return f"## {args.version.strip()} - <date>"
    if args.bump and state["version"] and state["version_valid"]:
        return f"## {versioning.bump_version(state['version'], args.bump)} - <date>"
    if state["version"] and state["version_valid"]:
        return f"## {state['version']} - Unreleased"
    return "## Unreleased"


def candidate_bullets(args: argparse.Namespace, impact: dict[str, Any], state: dict[str, Any]) -> list[str]:
    summaries = [clean_summary(item) for item in args.summary or [] if clean_summary(item)]
    if summaries:
        return [f"- {summary}" for summary in summaries]

    bullets = []
    for category in impact["categories"]:
        files = ", ".join(f"`{path}`" for path in category["changed_files"])
        if files:
            bullets.append(f"- TODO: Summarize {category['category']} impact from {files}.")
        else:
            bullets.append(f"- TODO: Summarize {category['category']} impact.")
    if not bullets and state["version_changed"]:
        bullets.append("- TODO: Summarize the release-impacting version change.")
    if not bullets and (args.bump or args.version or args.section):
        bullets.append("- TODO: Summarize the accepted release-note scope.")
    return bullets


def release_note_reasons(args: argparse.Namespace, impact: dict[str, Any], state: dict[str, Any]) -> list[str]:
    reasons = []
    if impact["categories"]:
        categories = ", ".join(item["category"] for item in impact["categories"])
        reasons.append(f"docs-impact categories detected: {categories}")
    if state["version_changed"]:
        reasons.append("VERSION changed")
    if args.summary:
        reasons.append("explicit changelog summary supplied")
    if args.bump:
        reasons.append(f"explicit bump requested: {args.bump}")
    if args.version:
        reasons.append(f"explicit version requested: {args.version}")
    if args.section:
        reasons.append("explicit changelog section supplied")
    return reasons


def next_commands(args: argparse.Namespace, needed: bool, state: dict[str, Any]) -> dict[str, list[str]]:
    check_command = "make agent-changelog-update CHANGELOG_UPDATE_CHECK=1"
    commands = {
        "safe": [check_command, "make docs-check", "git diff --check"],
        "explicit_write_only": [],
    }
    if state["version_present"]:
        commands["safe"].insert(1, "make version-check")
    if needed and args.bump:
        commands["explicit_write_only"].append(f"make version-bump BUMP={args.bump}")
    if needed:
        commands["explicit_write_only"].append("edit CHANGELOG.md under accepted release-note scope")
    return commands


def build_report(args: argparse.Namespace, repo: Path) -> tuple[dict[str, Any], int]:
    repo = repo.expanduser().resolve()
    impact = build_docs_impact(
        repo,
        config=args.config,
        changed_files=args.changed_files,
        staged=args.staged,
        working_tree=args.working_tree,
        docs_impact_json=args.docs_impact_json,
    )
    changed_files = sorted(set(impact["changed_files"]))
    state = version_state(repo, changed_files)
    reasons = release_note_reasons(args, impact, state)
    needed = bool(reasons)
    required = needed and (not state["changelog_present"] or not state["changelog_changed"])
    bullets = candidate_bullets(args, impact, state) if needed else []
    heading = candidate_heading(args, state) if needed else None
    text = f"{heading}\n\n" + "\n".join(bullets) + "\n" if heading and bullets else ""
    result = "no-release-note-needed"
    if needed and state["changelog_changed"]:
        result = "changelog-present"
    elif needed:
        result = "changelog-update-required"
    exit_code = 1 if args.check and required else 0
    payload = {
        "schema_version": 1,
        "command": "changelog-update",
        "repo": str(repo),
        "mode": "check" if args.check else "propose",
        "target_repo_writes": io_record(False, "proposal/check only; target version files are never written"),
        "sidecar_writes": io_record(False, "non-mutating command"),
        "docs_impact": impact,
        "changed_files": changed_files,
        "versioning": state,
        "release_note": {
            "needed": needed,
            "required": required,
            "reasons": reasons,
            "changelog_changed": state["changelog_changed"],
        },
        "candidate_changelog_entry": {
            "needed": needed,
            "heading": heading,
            "bullets": bullets,
            "text": text,
        },
        "next_commands": next_commands(args, needed, state),
        "result": result,
        "exit_code": exit_code,
    }
    return payload, exit_code


def render_text(payload: dict[str, Any]) -> str:
    versioning_state = payload["versioning"]
    version_label = f" ({versioning_state['version']})" if versioning_state["version"] else ""
    lines = [
        f"Changelog update: {payload['result']}",
        f"Target writes performed: {str(payload['target_repo_writes']['performed']).lower()}",
        "",
        "Changed files:",
    ]
    for path in payload["changed_files"] or ["(none)"]:
        lines.append(f" - {path}")
    categories = payload["docs_impact"]["categories"]
    lines.extend(["", "Docs-impact categories:"])
    if categories:
        for category in categories:
            files = ", ".join(category["changed_files"])
            lines.append(f" - {category['category']}: {files or '(none)'}")
    else:
        lines.append(" - none")

    lines.extend(
        [
            "",
            "Versioning state:",
            f" - VERSION: {'present' if versioning_state['version_present'] else 'missing'}"
            f"{version_label}",
            f" - CHANGELOG.md: {'present' if versioning_state['changelog_present'] else 'missing'}",
            f" - CHANGELOG.md changed: {str(versioning_state['changelog_changed']).lower()}",
            "",
        ]
    )

    candidate = payload["candidate_changelog_entry"]
    if candidate["needed"]:
        lines.append("Candidate changelog entry:")
        lines.append("")
        lines.append(candidate["text"].rstrip())
    else:
        lines.append("No changelog entry proposed.")
    lines.extend(["", "Next safe commands:"])
    for command in payload["next_commands"]["safe"]:
        lines.append(f" - {command}")
    explicit = payload["next_commands"]["explicit_write_only"]
    if explicit:
        lines.extend(["", "Explicit write-only follow-up:"])
        for command in explicit:
            lines.append(f" - {command}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Propose or check changelog work from docs-impact context")
    parser.add_argument("--repo", default=".", help="Target git repository. Defaults to the current directory.")
    parser.add_argument("--config", default=check_doc_impact.CONFIG_FILE)
    parser.add_argument("--changed-file", action="append", dest="changed_files")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--working-tree", action="store_true")
    parser.add_argument("--docs-impact-json", help="Existing docs-impact JSON to consume instead of deriving changed files.")
    parser.add_argument("--summary", action="append", help="Candidate changelog bullet. Can be repeated.")
    parser.add_argument("--section", help="Candidate changelog section heading.")
    parser.add_argument("--version", help="Candidate release version heading.")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], help="Candidate SemVer bump to mention.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when changelog work appears required.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload, exit_code = build_report(args, Path(args.repo))
    if args.json or args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload), end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
