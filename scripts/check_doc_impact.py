#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

# Script flow:
# 1. Load doc-contract.json and merge it with default documentation rules.
# 2. Collect changed files from staged, working-tree, branch, or explicit input.
# 3. Classify code/config changes and detect matching documentation updates.
# 4. Report whether docs are covered, missing, ignored, or explicitly waived.
#
# Function guide:
# - run/deep_merge/load_config/unique_paths provide shared utilities.
# - diff_name_only/get_*_changed_files collect git changes.
# - normalize_path/matches_pattern/matches_any/all_doc_patterns classify paths.
# - file_exists/is_doc_file/is_ignored_file classify repo files.
# - classify_changes/find_docs_changed/find_covered_categories build evaluation facts.
# - has_no_docs_marker/has_no_docs_declaration detect explicit waivers.
# - evaluate/parse_args/main produce the final result.

CONFIG_FILE = "doc-contract.json"

DEFAULT_CONFIG = {
    "required_files": [
        "docs/documentation-contract.md",
        "AGENTS.md",
    ],
    "doc_paths": [
        "docs/",
        "README.md",
        "AGENTS.md",
        ".github/pull_request_template.md",
    ],
    "ignore_paths": [
        "tests/",
    ],
    "no_docs_needed_markers": [
        "No docs needed:",
    ],
    "impact_rules": {
        "api": ["api/", "openapi/", "schema/"],
        "cli": ["cli/"],
        "config": ["config/", ".env", "settings"],
        "ops": ["deploy/", ".github/workflows/", "infra/", "terraform/", "helm/"],
    },
    "category_doc_paths": {
        "api": ["README.md", "docs/api/", "docs/reference/", "docs/openapi/"],
        "cli": ["README.md", "docs/cli/", "docs/commands/"],
        "config": ["README.md", "docs/config/", "docs/setup/", ".env.example", ".env.sample"],
        "ops": ["docs/ops/", "docs/deploy/", "docs/runbooks/"],
    },
}


@dataclass(frozen=True)
class Evaluation:
    changed_files: list[str]
    categories: dict[str, list[str]]
    docs_changed: list[str]
    covered_categories: set[str]
    missing_categories: set[str]
    no_docs_declaration: bool

    @property
    def failed(self) -> bool:
        return bool(self.missing_categories) and not self.no_docs_declaration


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def deep_merge(base, override):
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path=CONFIG_FILE):
    path = Path(config_path)
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)

    try:
        with path.open(encoding="utf-8") as f:
            loaded = json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON config in {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise SystemExit(f"Invalid config in {path}: top-level value must be an object")

    return deep_merge(DEFAULT_CONFIG, loaded)


def unique_paths(paths):
    return sorted({normalize_path(path) for path in paths if normalize_path(path)})


def diff_name_only(args):
    output = run(["git", "diff", "--name-only", *args])
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_staged_changed_files():
    try:
        return diff_name_only(["--cached"])
    except Exception:
        return []


def get_unstaged_changed_files():
    try:
        return diff_name_only([])
    except Exception:
        return []


def get_untracked_files():
    try:
        output = run(["git", "ls-files", "--others", "--exclude-standard"])
        return [line.strip() for line in output.splitlines() if line.strip()]
    except Exception:
        return []


def get_branch_changed_files():
    attempts = [
        ["git", "merge-base", "HEAD", "origin/main"],
        ["git", "merge-base", "HEAD", "origin/master"],
    ]

    for merge_base_cmd in attempts:
        try:
            base = run(merge_base_cmd)
            output = run(["git", "diff", "--name-only", f"{base}...HEAD"])
            files = [line.strip() for line in output.splitlines() if line.strip()]
            if files:
                return files
        except Exception:
            pass

    try:
        output = run(["git", "diff", "--name-only", "HEAD~1..HEAD"])
        files = [line.strip() for line in output.splitlines() if line.strip()]
        if files:
            return files
    except Exception:
        pass

    return []


def get_changed_files():
    files = []
    files.extend(get_branch_changed_files())
    files.extend(get_staged_changed_files())
    files.extend(get_unstaged_changed_files())
    files.extend(get_untracked_files())
    return unique_paths(files)


def normalize_path(path):
    return path.replace("\\", "/").strip()


def matches_pattern(path, pattern):
    candidate = normalize_path(path).lower()
    rule = normalize_path(pattern).lower()

    if rule.endswith("/"):
        return candidate.startswith(rule)
    if candidate == rule:
        return True
    if candidate.startswith(f"{rule}/"):
        return True
    return rule in candidate


def matches_any(path, patterns):
    return any(matches_pattern(path, pattern) for pattern in patterns)


def all_doc_patterns(config):
    patterns = list(config["doc_paths"])
    for category_patterns in config["category_doc_paths"].values():
        patterns.extend(category_patterns)
    return patterns


def file_exists(path):
    return Path(path).exists()


def is_doc_file(path, config):
    return matches_any(path, all_doc_patterns(config))


def is_ignored_file(path, config):
    return matches_any(path, config["ignore_paths"])


def classify_changes(files, config):
    categories = {}
    for path in files:
        if is_doc_file(path, config) or is_ignored_file(path, config):
            continue

        for category, patterns in config["impact_rules"].items():
            if matches_any(path, patterns):
                categories.setdefault(category, []).append(path)

    return categories


def find_docs_changed(files, config):
    return [path for path in files if is_doc_file(path, config)]


def find_covered_categories(categories, docs_changed, config):
    covered = set()
    for category in categories:
        expected_doc_paths = config["category_doc_paths"].get(category, config["doc_paths"])
        if any(matches_any(path, expected_doc_paths) for path in docs_changed):
            covered.add(category)
    return covered


def has_no_docs_marker(text, markers):
    for line in text.splitlines():
        lowered = line.lower()
        for marker in markers:
            marker_lower = marker.lower()
            index = lowered.find(marker_lower)
            if index == -1:
                continue

            reason = line[index + len(marker) :].strip()
            if reason and not reason.startswith("<!--"):
                return True

    return False


def has_no_docs_declaration(no_docs_needed, config):
    markers = config["no_docs_needed_markers"]

    direct_reason = no_docs_needed or os.environ.get("DOC_CONTRACT_NO_DOCS_NEEDED")
    if direct_reason and direct_reason.strip():
        return True

    pr_body = os.environ.get("DOC_CONTRACT_PR_BODY", "")
    return has_no_docs_marker(pr_body, markers)


def evaluate(changed_files, config, no_docs_declaration=False):
    changed_files = [normalize_path(path) for path in changed_files]
    categories = classify_changes(changed_files, config)
    docs_changed = find_docs_changed(changed_files, config)
    covered_categories = find_covered_categories(categories, docs_changed, config)
    missing_categories = set(categories) - covered_categories

    return Evaluation(
        changed_files=changed_files,
        categories=categories,
        docs_changed=docs_changed,
        covered_categories=covered_categories,
        missing_categories=missing_categories,
        no_docs_declaration=no_docs_declaration,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Check whether doc-impacting changes updated docs")
    parser.add_argument(
        "--config",
        default=CONFIG_FILE,
        help=f"Path to doc-contract config file. Defaults to {CONFIG_FILE}.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        dest="changed_files",
        help="Changed file path. Repeat to bypass git detection, mainly for tests or CI adapters.",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check only staged files. Intended for pre-commit hooks.",
    )
    parser.add_argument(
        "--working-tree",
        action="store_true",
        help="Check staged and unstaged working-tree files without branch/commit diff detection.",
    )
    parser.add_argument(
        "--no-docs-needed",
        help="Explicit no-docs-needed reason for this change.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)

    for path in config["required_files"]:
        if not file_exists(path):
            print(f"Missing required file: {path}")
            sys.exit(1)

    if args.changed_files:
        changed_files = args.changed_files
    elif args.staged:
        changed_files = get_staged_changed_files()
    elif args.working_tree:
        changed_files = unique_paths(
            get_staged_changed_files() + get_unstaged_changed_files() + get_untracked_files()
        )
    else:
        changed_files = get_changed_files()
    if not changed_files:
        print("No changed files detected.")
        return

    no_docs_declaration = has_no_docs_declaration(args.no_docs_needed, config)
    result = evaluate(changed_files, config, no_docs_declaration)

    print("Changed files:")
    for path in result.changed_files:
        print(f" - {path}")

    if not result.categories:
        print("No doc-impacting paths detected.")
        print("If this is an internal-only change, make sure the PR says so.")
        return

    print("Detected possible doc-impact categories:")
    for category, files in sorted(result.categories.items()):
        print(f" - {category}: {', '.join(files)}")

    if result.failed:
        print("\nDocumentation impact detected without matching documentation updates.")
        print(f"Missing documentation coverage for: {', '.join(sorted(result.missing_categories))}")
        print("Update the expected docs, or declare an explicit no-docs-needed reason.")
        sys.exit(1)

    if result.missing_categories and result.no_docs_declaration:
        print("Documentation impact waived by explicit no-docs-needed declaration.")
        return

    print("Documentation impact check passed.")


if __name__ == "__main__":
    main()
